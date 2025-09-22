import contextlib

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.contrib.sessions.models import Session
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from shared.services.permission_resolver import permission_resolver
from user_management.services.logging_service import log_activity
from user_management.services.profile_service import ensure_profile, sync_status

from .models import LogAtividadeUsuario, PerfilUsuarioEstendido, SessaoUsuario, StatusUsuario
from .realtime import broadcast_session_event

try:  # Import condicional para evitar falhas em migrações iniciais
    from core.models import TenantUser
except Exception:  # pragma: no cover
    TenantUser = None  # type: ignore

User = get_user_model()


@receiver(post_save, sender=User)
def perfil_estendido_handler(sender, instance, created, **kwargs):
    """Handler unificado idempotente para criação e sincronização de perfil."""
    if created:
        ensure_profile(instance)
    sync_status(instance)


@receiver(post_save, sender=PerfilUsuarioEstendido)
def perfil_reverse_sync_user_active(sender, instance, **kwargs):  # pragma: no cover - simples
    """Sincroniza user.is_active a partir do status do perfil.
    Regras:
      - status INATIVO / BLOQUEADO / SUSPENSO => user.is_active=False
      - status ATIVO => user.is_active=True (mantém se já True)
      - status PENDENTE não força alteração (permite fluxo de aprovação separado)
    Evita loop pois o handler de User só ajusta perfil quando status em {ATIVO, INATIVO}.
    """
    desired_active = True
    if instance.status in {StatusUsuario.INATIVO, StatusUsuario.BLOQUEADO, StatusUsuario.SUSPENSO}:
        desired_active = False
    elif instance.status == StatusUsuario.PENDENTE:
        # Não altera user.is_active para permitir aprovação manual
        return
    user = instance.user
    if user.is_active != desired_active:
        user.is_active = desired_active
        # Utiliza save() para garantir coerência de instância e possíveis outros sinais (mesmo que mínimos).
        user.save(update_fields=["is_active"])
        with contextlib.suppress(Exception):
            log_activity(
                user,
                "USER_ACTIVE_SYNC",
                "user_management",
                f"Ajuste user.is_active={desired_active} por perfil.status={instance.status}",
                ip="",
                user_agent="",
            )


@receiver(user_logged_in)
def usuario_logou(sender, request, user, **kwargs):
    """Registrar login do usuário"""

    # Obter informações da requisição
    ip_address = request.META.get("REMOTE_ADDR", "127.0.0.1")  # IP padrão se não encontrado
    user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")

    # Criar ou atualizar sessão
    session_key = request.session.session_key
    if session_key:
        sessao, created = SessaoUsuario.objects.get_or_create(
            session_key=session_key,
            defaults={
                "user": user,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "ativa": True,
            },
        )

        if not created:
            sessao.user = user
            sessao.ip_address = ip_address
            sessao.user_agent = user_agent
            sessao.ativa = True
            sessao.ultima_atividade = timezone.now()
            sessao.save()
            broadcast_session_event("updated", sessao)
        else:
            broadcast_session_event("created", sessao)

    # Atualizar perfil estendido
    if hasattr(user, "perfil_estendido"):
        perfil = user.perfil_estendido
        perfil.ultimo_login_ip = ip_address
        perfil.tentativas_login_falhadas = 0  # Resetar tentativas falhadas
        perfil.save()

    # Log da atividade
    log_activity(user, "LOGIN", "user_management", "Usuário fez login no sistema", ip=ip_address, user_agent=user_agent)

    # Aquecimento de cache do PermissionResolver para ações comuns (opcional via flag)
    try:
        if getattr(settings, "PERMISSION_WARMUP_ON_LOGIN", True):
            from core.utils import get_current_tenant

            tenant = get_current_tenant(request)
            # Fallbacks: se tenant ainda não estiver disponível neste instante do sinal,
            # tenta recuperar via sessão ou primeiro vínculo TenantUser do usuário.
            if tenant is None:
                try:
                    from core.models import Tenant  # import local para evitar ciclos

                    tid = None
                    sess = getattr(request, "session", None)
                    if sess and "tenant_id" in sess:
                        tid = sess.get("tenant_id")
                    if tid and isinstance(tid, int):
                        try:
                            tenant = Tenant.objects.get(id=tid)
                        except Tenant.DoesNotExist:
                            tenant = None
                    if tenant is None and TenantUser is not None:
                        tid = TenantUser.objects.filter(user=user).values_list("tenant_id", flat=True).first()
                        if tid:
                            try:
                                tenant = Tenant.objects.get(id=tid)
                            except Tenant.DoesNotExist:
                                tenant = None
                except Exception:
                    tenant = None
            if tenant is not None:
                # Lista mínima padrão para não interferir com testes sensíveis (ex.: VIEW_COTACAO)
                common_actions = getattr(settings, "PERMISSION_WARMUP_ACTIONS", ["VIEW_DASHBOARD_PUBLIC"])
                for act in common_actions:
                    try:
                        # resolve() já popula o cache com TTL padrão
                        permission_resolver.resolve(user, tenant, act)
                    except Exception:
                        pass
    except Exception:
        # Nunca impacta o fluxo de login
        pass

    @receiver(user_logged_out)
    def usuario_deslogou(sender, request, user, **kwargs):
        """Registrar logout do usuário"""
        ip_address = request.META.get("REMOTE_ADDR", "")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        if user and user.is_authenticated:
            # Obter informações da requisição

            # Desativar sessão
            session_key = request.session.session_key
            if session_key:
                try:
                    sessao = SessaoUsuario.objects.get(session_key=session_key)
                    sessao.ativa = False
                    sessao.save()
                    broadcast_session_event("terminated", sessao)
                except SessaoUsuario.DoesNotExist:
                    pass

        # Log da atividade
        log_activity(
            user, "LOGOUT", "user_management", "Usuário fez logout do sistema", ip=ip_address, user_agent=user_agent
        )


@receiver(user_login_failed)
def login_falhado(sender, credentials, request, **kwargs):
    """Registrar tentativas de login falhadas"""

    username = credentials.get("username", "")
    # Em chamadas authenticate() sem request (testes ou fluxos internos) request pode ser None
    if request is not None:
        ip_address = request.META.get("REMOTE_ADDR", "")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
    else:
        ip_address = ""
        user_agent = ""

    # Tentar encontrar o usuário
    try:
        user = User.objects.get(username=username)
        if hasattr(user, "perfil_estendido"):
            perfil = user.perfil_estendido
            perfil.tentativas_login_falhadas += 1
            fail_threshold = getattr(settings, "LOGIN_FAIL_THRESHOLD", 5)
            block_minutes = getattr(settings, "LOGIN_BLOCK_MINUTES", 30)
            if perfil.tentativas_login_falhadas >= fail_threshold:
                perfil.bloqueado_ate = timezone.now() + timezone.timedelta(minutes=block_minutes)
                perfil.status = StatusUsuario.BLOQUEADO
            perfil.save()
        log_activity(
            user,
            "LOGIN_FAILED",
            "user_management",
            f"Tentativa de login falhada (tentativa #{user.perfil_estendido.tentativas_login_falhadas if hasattr(user, 'perfil_estendido') else '?'})",
            ip=ip_address,
            user_agent=user_agent,
        )
    except User.DoesNotExist:
        try:
            sistema_user, _ = User.objects.get_or_create(
                username="__sistema_log__",
                defaults={
                    "email": "sistema@log.internal",
                    "first_name": "Sistema",
                    "last_name": "Log",
                    "is_active": False,
                    "is_staff": False,
                },
            )
            log_activity(
                sistema_user,
                "LOGIN_FAILED_UNKNOWN_USER",
                "user_management",
                f"Tentativa de login com usuário inexistente: {username}",
                ip=ip_address,
                user_agent=user_agent,
            )
        except Exception as e:  # pragma: no cover - fallback
            print(
                f"Erro ao registrar tentativa de login com usuário inexistente: {username} - IP: {ip_address} - Erro: {e}"
            )


def limpar_sessoes_expiradas():
    """Função para limpar sessões expiradas (pode ser chamada por um cron job)"""

    # Obter todas as sessões ativas do Django
    sessoes_django = Session.objects.filter(expire_date__lt=timezone.now())
    session_keys_expiradas = list(sessoes_django.values_list("session_key", flat=True))

    # Desativar sessões correspondentes no nosso modelo
    SessaoUsuario.objects.filter(session_key__in=session_keys_expiradas, ativa=True).update(ativa=False)

    # Remover sessões do Django
    sessoes_django.delete()


def limpar_logs_antigos(dias=90):
    """Função para limpar logs antigos (pode ser chamada por um cron job)"""

    data_limite = timezone.now() - timezone.timedelta(days=dias)
    logs_removidos = LogAtividadeUsuario.objects.filter(timestamp__lt=data_limite).count()
    LogAtividadeUsuario.objects.filter(timestamp__lt=data_limite).delete()

    return logs_removidos


def desbloquear_usuarios():
    """Função para desbloquear usuários automaticamente (pode ser chamada por um cron job)"""

    agora = timezone.now()
    perfis_bloqueados = PerfilUsuarioEstendido.objects.filter(status=StatusUsuario.BLOQUEADO, bloqueado_ate__lt=agora)

    count = perfis_bloqueados.count()
    perfis_bloqueados.update(status=StatusUsuario.ATIVO, bloqueado_ate=None, tentativas_login_falhadas=0)

    return count


# =============================
# Invalidação de cache de permissões quando vínculo TenantUser é salvo
# =============================
if TenantUser:  # pragma: no branch - simples

    @receiver(post_save, sender=TenantUser)
    def invalidate_perm_cache_tenantuser(sender, instance, **kwargs):  # pragma: no cover (efeito indireto)
        with contextlib.suppress(Exception):
            permission_resolver.invalidate_cache(user_id=instance.user_id, tenant_id=instance.tenant_id)


# ============================================================================
# Signals de PermissaoPersonalizada para invalidar cache de permissões
# ============================================================================
try:
    from user_management.models import PermissaoPersonalizada

    @receiver(post_save, sender=PermissaoPersonalizada)
    def invalida_cache_perm_save(sender, instance, **kwargs):  # pragma: no cover - efeito colateral simples
        with contextlib.suppress(Exception):
            permission_resolver.invalidate_cache(
                user_id=instance.user_id, tenant_id=getattr(instance.scope_tenant, "id", None)
            )

    @receiver(post_delete, sender=PermissaoPersonalizada)
    def invalida_cache_perm_delete(sender, instance, **kwargs):  # pragma: no cover
        with contextlib.suppress(Exception):
            permission_resolver.invalidate_cache(
                user_id=instance.user_id, tenant_id=getattr(instance.scope_tenant, "id", None)
            )
except Exception:
    pass
