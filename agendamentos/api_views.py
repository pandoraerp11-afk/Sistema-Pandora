import contextlib

from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.utils import get_current_tenant
from shared.permissions_servicos import CLINICAL_SCHEDULING_DENIED_MESSAGE, can_schedule_clinical_service

from .models import Agendamento, AuditoriaAgendamento, Disponibilidade, Slot
from .serializers import (
    AgendamentoSerializer,
    AuditoriaAgendamentoSerializer,
    DisponibilidadeSerializer,
    SlotSerializer,
)


class IsAgendamentoProfissionalOuSecretaria(permissions.BasePermission):
    """Permite acesso a superuser, grupo secretaria ou profissional (is_staff).
    Grupo AGENDAMENTOS_VISUALIZAR tem acesso SOMENTE LEITURA (SAFE_METHODS) global.
    """

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        if u.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists():
            return True
        # Grupo de visualização global somente leitura
        if u.groups.filter(name="AGENDAMENTOS_VISUALIZAR").exists():
            return request.method in permissions.SAFE_METHODS
        allowed = u.is_staff
        # Enforcement opcional de permissões nativas Django
        try:
            from django.conf import settings as dj_settings

            if getattr(dj_settings, "ENABLE_AGENDAMENTOS_MODEL_PERMS", False):
                # Determina modelo alvo do viewset
                model = None
                if hasattr(view, "queryset") and getattr(view.queryset, "model", None):
                    model = view.queryset.model
                # Se não conseguiu inferir modelo, usa fallback (mantém allowed)
                if model is not None:
                    action_map = {
                        "GET": "view",
                        "HEAD": "view",
                        "OPTIONS": "view",
                        "POST": "add",
                        "PUT": "change",
                        "PATCH": "change",
                        "DELETE": "delete",
                    }
                    needed = action_map.get(request.method, "view")
                    app_label = model._meta.app_label
                    codename = f"{needed}_{model._meta.model_name}"
                    if not u.has_perm(f"{app_label}.{codename}"):
                        return False
                return allowed
        except Exception:
            return allowed
        return allowed


class IsAgendamentoAuditoria(permissions.BasePermission):
    """Restringe acesso à auditoria: somente superuser ou grupo secretaria."""

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        return u.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()


class IsClientePortal(permissions.BasePermission):
    """Permite acesso a usuários autenticados que tenham vínculo de portal com algum Cliente no tenant atual."""

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        # Staff e secretaria já atendidos pelas outras permissões; aqui é especificamente cliente portal
        if u.is_staff or u.is_superuser:
            return False
        tenant = get_current_tenant(request)
        # Tentativa de inferir tenant a partir do slot (pk na rota) se ainda não definido
        if not tenant:
            try:
                pk = getattr(view, "kwargs", {}).get("pk") or getattr(
                    getattr(view, "kwargs", None), "get", lambda *_: None
                )("pk")
                if pk:
                    from agendamentos.models import Slot as _Slot

                    sl = _Slot.objects.filter(id=pk).select_related("tenant").first()
                    if sl and sl.tenant and hasattr(request, "session"):
                        request.session["tenant_id"] = sl.tenant_id
                        tenant = sl.tenant
            except Exception:
                pass
        from clientes.models import AcessoCliente

        # Se ainda sem tenant: aceitar se usuário tem qualquer acesso ativo (a view lidará com validação específica depois)
        if not tenant:
            return AcessoCliente.objects.filter(usuario=u, cliente__status="active").exists()
        return AcessoCliente.objects.filter(usuario=u, cliente__tenant=tenant, cliente__status="active").exists()


def _resolver_cliente_do_usuario(request):
    """Retorna o Cliente associado ao usuário autenticado no tenant atual via AcessoCliente.
    Se múltiplos, aceita request.data['cliente_id'] contanto que pertença ao conjunto permitido.
    """
    from clientes.models import Cliente

    tenant = get_current_tenant(request)
    if not tenant:
        return None
    user = request.user
    # Opcional: permitir escolher cliente específico entre os acessíveis
    cid = request.data.get("cliente_id") or request.query_params.get("cliente_id")
    base_qs = Cliente.objects.filter(tenant=tenant, acessos__usuario=user, status="active").distinct()
    if cid:
        return base_qs.filter(id=cid).first()
    return base_qs.first()


class DisponibilidadeViewSet(viewsets.ModelViewSet):
    queryset = Disponibilidade.objects.all()
    serializer_class = DisponibilidadeSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgendamentoProfissionalOuSecretaria]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        from django.core.cache import cache

        from agendamentos.services import get_slots_cache_version

        qs_base = Disponibilidade.objects.filter(tenant=tenant, ativo=True)
        user = self.request.user
        # Cache somente para leitura (não para superuser com alterações frequentes) – chave inclui papel e tenant
        cache_key = None
        if tenant and self.request.method == "GET" and user.is_authenticated:
            papel = (
                "adm" if (user.is_superuser or user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()) else "prof"
            )
            cache_key = f"ag:disp:{tenant.id}:{papel}:{get_slots_cache_version()}"
        if cache_key:
            data_ids = cache.get(cache_key)
            if data_ids is not None:
                return qs_base.filter(id__in=data_ids)
        qs = qs_base
        user = self.request.user
        if (
            user.is_superuser
            or user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()
            or user.groups.filter(name="AGENDAMENTOS_VISUALIZAR").exists()
        ):
            final_qs = qs
        else:
            final_qs = qs.filter(profissional=user)
        if cache_key:
            with contextlib.suppress(Exception):
                cache.set(cache_key, list(final_qs.values_list("id", flat=True)), 30)
        return final_qs

    def perform_create(self, serializer):
        tenant = get_current_tenant(self.request)
        user = self.request.user
        if not tenant:
            raise permissions.PermissionDenied("Tenant inválido")
        serializer.save(
            tenant=tenant,
            profissional=user if not user.is_superuser else serializer.validated_data.get("profissional", user),
        )
        # Geração de slots pode ser feita por serviço externo futuro
        # (placeholder para consistência com prontuarios)

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"])
    def gerar_slots(self, request, pk=None):
        disp = self.get_object()
        from .services import SlotService

        criados, existentes = SlotService.gerar_slots(disp)
        return Response({"disponibilidade": disp.id, "criados": criados, "ja_existentes": existentes})


class SlotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Slot.objects.select_related("profissional", "disponibilidade").all()
    serializer_class = SlotSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgendamentoProfissionalOuSecretaria]

    def get_queryset(self):
        from django.utils import timezone

        tenant = get_current_tenant(self.request)
        now = timezone.now()
        if tenant is None:
            qs = Slot.objects.filter(ativo=True, horario__gte=now).select_related("profissional", "disponibilidade")
        else:
            qs = Slot.objects.filter(tenant=tenant, ativo=True, horario__gte=now).select_related(
                "profissional", "disponibilidade"
            )
        user = self.request.user
        profissional_id = self.request.query_params.get("profissional")
        data = self.request.query_params.get("data")
        disponivel = self.request.query_params.get("disponivel")
        servico_id = self.request.query_params.get("servico") or self.request.query_params.get("servico_id")
        # Cache chaveada por filtros básicos
        from django.core.cache import cache

        from agendamentos.services import get_slots_cache_version

        cache_key = None
        if tenant and self.request.method == "GET":
            cache_key = f"ag:slots:{tenant.id}:{profissional_id or '-'}:{data or '-'}:{disponivel or '-'}:{servico_id or '-'}:{get_slots_cache_version()}"
            cached_ids = cache.get(cache_key)
            if cached_ids is not None:
                base = qs.filter(id__in=cached_ids)
                # Aplicar regras de escopo de usuário após cache (ids já filtrados por tenant/filtros)
                user_scoped = base
                if not (
                    user.is_superuser
                    or user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()
                    or user.groups.filter(name="AGENDAMENTOS_VISUALIZAR").exists()
                ):
                    if not user.is_staff:
                        user_scoped = base.filter(capacidade_utilizada__lt=F("capacidade_total"))
                    else:
                        user_scoped = base.filter(profissional=user)
                return user_scoped.order_by("horario", "id")
        if profissional_id:
            qs = qs.filter(profissional_id=profissional_id)
        if data:
            qs = qs.filter(horario__date=data)
        if disponivel == "1":
            qs = qs.filter(capacidade_utilizada__lt=F("capacidade_total"))
        # Filtro opcional por competência Profissional x Serviço
        if servico_id and tenant is not None:
            try:
                from django.conf import settings as dj_settings

                if getattr(dj_settings, "ENFORCE_COMPETENCIA", False):
                    from .models import ProfissionalProcedimento

                    qs = qs.filter(
                        profissional_id__in=ProfissionalProcedimento.objects.filter(
                            tenant=tenant, servico_id=servico_id, ativo=True
                        ).values_list("profissional_id", flat=True)
                    )
            except Exception:
                # Não falhar silenciosamente a listagem caso app/migração ainda não aplicados
                pass
        qs = qs.order_by("horario", "id")
        if (
            user.is_superuser
            or user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()
            or user.groups.filter(name="AGENDAMENTOS_VISUALIZAR").exists()
        ):
            final_qs = qs
        elif not user.is_staff:
            final_qs = qs.filter(capacidade_utilizada__lt=F("capacidade_total"))
        else:
            final_qs = qs.filter(profissional=user)
        if cache_key:
            with contextlib.suppress(Exception):
                cache.set(cache_key, list(final_qs.values_list("id", flat=True)), 15)
        return final_qs

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            # Fallback: tenta localizar slot ignorando filtros de tenant/horario
            pk = self.kwargs.get(self.lookup_field or "pk")
            slot = Slot.objects.filter(pk=pk).select_related("profissional", "disponibilidade").first()
            if not slot:
                raise
            # Ajusta tenant em sessão se ausente
            req = self.request
            if not hasattr(req, "session"):
                req.session = {}
            if slot.tenant_id and req.session.get("tenant_id") != slot.tenant_id:
                req.session["tenant_id"] = slot.tenant_id
            return slot

    @action(detail=True, methods=["post"])
    def reservar(self, request, pk=None):
        slot = self.get_object()
        # Fallback: se tenant não resolvido (ex: request sem session em testes), usa tenant do slot
        if not hasattr(request, "session"):
            request.session = {}
        if "tenant_id" not in request.session and slot.tenant_id:
            request.session["tenant_id"] = slot.tenant_id
        from .services import AgendamentoService

        cliente_id = request.data.get("cliente_id")
        if not cliente_id:
            return Response({"detail": _("cliente_id obrigatório")}, status=400)
        from clientes.models import Cliente

        try:
            cliente = Cliente.objects.get(id=cliente_id, tenant=slot.tenant)
        except Cliente.DoesNotExist:
            return Response({"detail": _("cliente inválido")}, status=400)
        servico_id = request.data.get("servico_id")
        if servico_id:
            from servicos.models import Servico as _Servico

            try:
                _serv = _Servico.objects.select_related("perfil_clinico").get(id=servico_id)
            except _Servico.DoesNotExist:
                return Response({"detail": _("Serviço inválido")}, status=400)
            if _serv.is_clinical and not can_schedule_clinical_service(request.user, _serv):
                return Response({"detail": str(CLINICAL_SCHEDULING_DENIED_MESSAGE)}, status=403)
        # Criar agendamento (service fará a reserva do slot uma única vez)
        try:
            ag = AgendamentoService.criar(
                tenant=slot.tenant,
                cliente=cliente,
                profissional=slot.profissional,
                data_inicio=slot.horario,
                data_fim=None,  # permite cálculo automático se serviço
                origem="OPERADOR" if request.user.is_staff else "CLIENTE",
                slot=slot,
                servico=servico_id,
                metadata={"atalho_reserva": True},
                user=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        ser = AgendamentoSerializer(ag)
        return Response({"slot": slot.id, "agendamento": ser.data})

    @action(detail=True, methods=["post"])
    def waitlist(self, request, pk=None):
        slot = self.get_object()
        from clientes.models import Cliente

        from .services import AgendamentoService

        cliente_id = request.data.get("cliente_id")
        prioridade = int(request.data.get("prioridade", 100))
        if not cliente_id:
            return Response({"detail": _("cliente_id obrigatório")}, status=400)
        try:
            cliente = Cliente.objects.get(id=cliente_id, tenant=slot.tenant)
        except Cliente.DoesNotExist:
            return Response({"detail": _("cliente inválido")}, status=400)
        try:
            wl = AgendamentoService.inscrever_waitlist(slot, cliente=cliente, prioridade=prioridade)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"waitlist_id": wl.id, "prioridade": wl.prioridade})


class AgendamentoViewSet(viewsets.ModelViewSet):
    queryset = Agendamento.objects.all()
    serializer_class = AgendamentoSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgendamentoProfissionalOuSecretaria]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        qs = Agendamento.objects.filter(tenant=tenant).order_by("data_inicio", "id")
        user = self.request.user
        if (
            user.is_superuser
            or user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()
            or user.groups.filter(name="AGENDAMENTOS_VISUALIZAR").exists()
        ):
            return qs
        if user.is_staff:
            return qs.filter(profissional=user)
        # cliente final (futuro): filtrar por cliente vinculado ao user
        return qs.none()

    def perform_create(self, serializer):
        """Criação centralizada usando service para garantir regras e preenchimento de tenant.
        Replica lógica essencial da v2 evitando duplicação de regras de negócio.
        """
        from rest_framework import serializers as drf_serializers

        from .services import AgendamentoService

        tenant = get_current_tenant(self.request)
        # Fallback explícito caso utilitário não resolva (ex.: testes) usando session
        if tenant is None:
            try:
                sid = getattr(self.request, "session", {}).get("tenant_id")
                if sid:
                    from core.models import Tenant as _Tenant

                    tenant = _Tenant.objects.filter(id=sid).first()
            except Exception:
                tenant = None
        user = self.request.user
        if not tenant:
            raise permissions.PermissionDenied("Tenant inválido")
        slot = serializer.validated_data.get("slot")
        data_inicio = serializer.validated_data.get("data_inicio")
        data_fim = serializer.validated_data.get("data_fim")
        if not slot and (not data_inicio or not data_fim):
            raise permissions.PermissionDenied("Para agendamento manual informe data_inicio e data_fim")
        cliente = serializer.validated_data.get("cliente")
        profissional = serializer.validated_data.get("profissional") or (slot.profissional if slot else user)
        origem = serializer.validated_data.get("origem") or ("PROFISSIONAL" if user.is_staff else "CLIENTE")
        servico_id = self.request.data.get("servico_id")
        metadata = serializer.validated_data.get("metadata")
        # Enforce permissão clínica
        if servico_id:
            from servicos.models import Servico as _Servico

            try:
                _serv = _Servico.objects.select_related("perfil_clinico").get(id=servico_id)
            except _Servico.DoesNotExist:
                raise permissions.PermissionDenied(_("Serviço inválido"))
            if _serv.is_clinical and not can_schedule_clinical_service(user, _serv):
                raise permissions.PermissionDenied(str(CLINICAL_SCHEDULING_DENIED_MESSAGE))
        try:
            with transaction.atomic():
                ag = AgendamentoService.criar(
                    tenant=tenant,
                    cliente=cliente,
                    profissional=profissional,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    origem=origem,
                    slot=slot,
                    servico=servico_id,
                    metadata=metadata,
                    user=user,
                )
        except ValueError as e:
            raise drf_serializers.ValidationError({"detail": str(e)})
        serializer.instance = ag

    # ==== AÇÕES (base – compartilhadas com v2) ====
    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        from .services import AgendamentoService

        ag = self.get_object()
        motivo = request.data.get("motivo") or "Cancelado via API"
        try:
            AgendamentoService.cancelar(ag, motivo=motivo, user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"status": "ok", "novo_status": ag.status})

    @action(detail=True, methods=["post"])
    def reagendar(self, request, pk=None):
        from .services import AgendamentoService

        ag = self.get_object()
        novo_slot_id = request.data.get("novo_slot")
        nova_data_inicio = request.data.get("nova_data_inicio")
        nova_data_fim = request.data.get("nova_data_fim")
        motivo = request.data.get("motivo") or "Reagendamento via API"
        novo_slot = None
        if novo_slot_id:
            novo_slot = Slot.objects.filter(id=novo_slot_id, tenant=ag.tenant, ativo=True).first()
            if not novo_slot:
                return Response({"detail": "novo_slot inválido"}, status=400)
        if nova_data_inicio:
            from django.utils.dateparse import parse_datetime

            nova_data_inicio = parse_datetime(nova_data_inicio)
        if nova_data_fim:
            from django.utils.dateparse import parse_datetime

            nova_data_fim = parse_datetime(nova_data_fim)
        try:
            novo = AgendamentoService.reagendar(
                ag,
                novo_slot=novo_slot,
                nova_data_inicio=nova_data_inicio,
                nova_data_fim=nova_data_fim,
                user=request.user,
                motivo=motivo,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        ser = self.get_serializer(novo)
        return Response(ser.data)

    @action(detail=True, methods=["post"])
    def checkin(self, request, pk=None):
        from .services import AgendamentoService

        ag = self.get_object()
        try:
            AgendamentoService.checkin(ag, user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"status": ag.status})

    @action(detail=True, methods=["post"])
    def concluir(self, request, pk=None):
        from .services import AgendamentoService

        ag = self.get_object()
        try:
            AgendamentoService.concluir(ag, user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"status": ag.status})

    @action(detail=True, methods=["post"])
    def resolver_pendencias(self, request, pk=None):
        from .services import AgendamentoService

        ag = self.get_object()
        AgendamentoService.resolver_pendencias(ag, user=request.user)
        return Response({"status": ag.status, "metadata": ag.metadata})

    @action(detail=True, methods=["post"])
    def sync_evento(self, request, pk=None):
        """Força sincronização manual do evento espelho (feature flag ENABLE_EVENT_MIRROR).
        Retorna o id do evento criado/atualizado ou null se desabilitado.
        """
        from .services import SchedulingService

        ag = self.get_object()
        evento_id = SchedulingService.sync_evento(ag)
        return Response({"agendamento": ag.id, "evento_id": evento_id})


class AgendamentoV2ViewSet(AgendamentoViewSet):
    """Versão 2 (scaffold) – atualmente herda totalmente a lógica de v1.
    Permite evolução de payloads/serializers sem quebrar clientes antigos.
    Controlado por flag USE_NOVO_AGENDAMENTO para ativação gradual nas rotas.
    """

    def get_queryset(self):  # possibilidade de filtros/otimizações futuras
        qs = super().get_queryset()
        from django.conf import settings as _s

        if not getattr(_s, "USE_NOVO_AGENDAMENTO", False):
            return qs.none()  # rota ativa mas retorna vazio se flag off
        return qs

    def get_serializer_class(self):
        from .serializers import (
            AgendamentoV2CreateSerializer,
            AgendamentoV2DetailSerializer,
            AgendamentoV2ListSerializer,
        )

        if self.action in ("list", "stats", "capacidade"):
            return AgendamentoV2ListSerializer
        if self.action in ("retrieve",):
            return AgendamentoV2DetailSerializer
        if self.action in ("create",):
            return AgendamentoV2CreateSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=["get"])
    def stats(self, request):
        from django.utils import timezone

        tenant = get_current_tenant(request)
        now = timezone.now()
        qs = Agendamento.objects.filter(tenant=tenant)
        futuro = qs.filter(data_inicio__gte=now)
        no_show = qs.filter(status="NO_SHOW").count()
        return Response(
            {
                "total": qs.count(),
                "futuros": futuro.count(),
                "confirmados_futuros": futuro.filter(status="CONFIRMADO").count(),
                "pendentes_futuros": futuro.filter(status="PENDENTE").count(),
                "no_show_total": no_show,
            }
        )

    @action(detail=False, methods=["get"])
    def capacidade(self, request):
        """Capacidade agregada por profissional e data (filtros opcionais data_start, data_end)."""
        from django.db.models import Count, Sum

        tenant = get_current_tenant(request)
        data_start = request.query_params.get("data_start")
        data_end = request.query_params.get("data_end")
        qs = Slot.objects.filter(tenant=tenant, ativo=True)
        if data_start:
            qs = qs.filter(horario__date__gte=data_start)
        if data_end:
            qs = qs.filter(horario__date__lte=data_end)
        agg = qs.values("profissional_id").annotate(
            slots=Count("id"),
            capacidade_total=Sum("capacidade_total"),
            capacidade_utilizada=Sum("capacidade_utilizada"),
        )
        return Response(list(agg))

    def perform_create(self, serializer):
        # Substitui lógica de v1 para usar service e depois serializar
        from rest_framework import serializers as drf_serializers

        from .services import AgendamentoService

        tenant = get_current_tenant(self.request)
        user = self.request.user
        if not tenant:
            raise permissions.PermissionDenied("Tenant inválido")
        slot = serializer.validated_data.get("slot")
        data_inicio = serializer.validated_data.get("data_inicio")
        data_fim = serializer.validated_data.get("data_fim")
        cliente = serializer.validated_data.get("cliente")
        profissional = serializer.validated_data.get("profissional") or (slot.profissional if slot else user)
        origem = serializer.validated_data.get("origem") or ("PROFISSIONAL" if user.is_staff else "CLIENTE")
        servico = serializer.validated_data.get("servico")
        metadata = serializer.validated_data.get("metadata") or {}
        if not slot and (not data_inicio or not data_fim):
            raise permissions.PermissionDenied("Para agendamento manual informe data_inicio e data_fim")
        if not slot:
            metadata.setdefault("manual_sem_slot", True)
        try:
            with transaction.atomic():
                ag = AgendamentoService.criar(
                    tenant=tenant,
                    cliente=cliente,
                    profissional=profissional,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    origem=origem,
                    slot=slot,
                    servico=servico,
                    metadata=metadata,
                    user=user,
                )
        except ValueError as e:
            raise drf_serializers.ValidationError({"detail": str(e)})
        serializer.instance = ag

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Re-serializa com detail serializer para incluir campos derivados (id, auditoria vazia)
        from .serializers import AgendamentoV2DetailSerializer

        if response.status_code == 201 and isinstance(response.data, dict) and "id" not in response.data:
            (
                getattr(getattr(response, "data", None), "get", lambda *_: None)("id")
                or getattr(self, "object", None)
                or None
            )
        # Simples: pegar último criado pelo instance do serializer
        instance = getattr(self, "serializer_instance", None) or getattr(self, "object", None)
        if not instance:
            # fallback: recuperar pelo maior id do tenant (baixo volume durante criação isolada)
            try:
                instance = Agendamento.objects.filter(tenant=get_current_tenant(request)).latest("id")
            except Exception:  # pragma: no cover
                return response
        ser = AgendamentoV2DetailSerializer(instance, context=self.get_serializer_context())
        response.data = ser.data
        return response


class ClienteSlotViewSet(viewsets.ReadOnlyModelViewSet):
    """Listagem de slots para clientes (portal), somente disponíveis e futuros.
    Suporta filtro por serviço e aplica competência do profissional quando flag ativa.
    """

    queryset = Slot.objects.select_related("profissional", "disponibilidade").all()
    serializer_class = SlotSerializer
    permission_classes = [permissions.IsAuthenticated, IsClientePortal]

    def get_queryset(self):
        from django.utils import timezone

        tenant = get_current_tenant(self.request)
        now = timezone.now()
        qs = Slot.objects.filter(tenant=tenant, ativo=True, horario__gte=now).select_related(
            "profissional", "disponibilidade"
        )
        qs = qs.filter(capacidade_utilizada__lt=F("capacidade_total"))  # somente com vaga
        profissional_id = self.request.query_params.get("profissional")
        data = self.request.query_params.get("data")
        servico_id = self.request.query_params.get("servico") or self.request.query_params.get("servico_id")
        if profissional_id:
            qs = qs.filter(profissional_id=profissional_id)
        if data:
            qs = qs.filter(horario__date=data)
        if servico_id and tenant is not None:
            try:
                from django.conf import settings as dj_settings

                if getattr(dj_settings, "ENFORCE_COMPETENCIA", False):
                    from .models import ProfissionalProcedimento

                    qs = qs.filter(
                        profissional_id__in=ProfissionalProcedimento.objects.filter(
                            tenant=tenant,
                            servico_id=servico_id,
                            ativo=True,
                        ).values_list("profissional_id", flat=True)
                    )
            except Exception:
                pass
        from django.core.cache import cache

        from agendamentos.services import get_slots_cache_version

        cache_key = f"ag:slots_cli:{tenant.id if tenant else '-'}:{profissional_id or '-'}:{data or '-'}:{servico_id or '-'}:{get_slots_cache_version()}"
        cached_ids = cache.get(cache_key)
        if cached_ids is not None:
            return qs.filter(id__in=cached_ids).order_by("horario", "id")
        ordered = qs.order_by("horario", "id")
        with contextlib.suppress(Exception):
            cache.set(cache_key, list(ordered.values_list("id", flat=True)), 20)
        return ordered

    @action(detail=True, methods=["post"])
    def reservar(self, request, pk=None):
        """Cliente reserva um slot: cliente é inferido do vínculo do portal; origem=CLIENTE."""
        slot = self.get_object()
        if not hasattr(request, "session"):
            request.session = {}
        if "tenant_id" not in request.session and slot.tenant_id:
            request.session["tenant_id"] = slot.tenant_id
        from .services import AgendamentoService

        cliente = _resolver_cliente_do_usuario(request)
        if not cliente:
            return Response({"detail": "Acesso de cliente não encontrado para este tenant"}, status=403)
        servico_id = request.data.get("servico_id")
        if servico_id:
            from servicos.models import Servico as _Servico

            try:
                _serv = _Servico.objects.select_related("perfil_clinico").get(id=servico_id)
            except _Servico.DoesNotExist:
                return Response({"detail": _("Serviço inválido")}, status=400)
            if _serv.is_clinical and not can_schedule_clinical_service(request.user, _serv):
                return Response({"detail": str(CLINICAL_SCHEDULING_DENIED_MESSAGE)}, status=403)
        try:
            ag = AgendamentoService.criar(
                tenant=slot.tenant,
                cliente=cliente,
                profissional=slot.profissional,
                data_inicio=slot.horario,
                data_fim=None,
                origem="CLIENTE",
                slot=slot,
                servico=servico_id,
                metadata={"portal_cliente": True},
                user=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        ser = AgendamentoSerializer(ag)
        return Response({"slot": slot.id, "agendamento": ser.data})


class ClienteAgendamentoViewSet(viewsets.ModelViewSet):
    """Agendamentos do cliente (portal): lista e cria para o Cliente associado ao usuário.
    Ações de cancelar/reagendar disponíveis com regras de negócio do serviço.
    """

    queryset = Agendamento.objects.all()
    serializer_class = AgendamentoSerializer
    permission_classes = [permissions.IsAuthenticated, IsClientePortal]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        cliente = _resolver_cliente_do_usuario(self.request)
        if not tenant or not cliente:
            return Agendamento.objects.none()
        qs = Agendamento.objects.filter(tenant=tenant, cliente=cliente)
        # Filtros opcionais
        status_f = self.request.query_params.get("status")
        dstart = self.request.query_params.get("data_start")
        dend = self.request.query_params.get("data_end")
        if status_f:
            qs = qs.filter(status=status_f)
        if dstart:
            qs = qs.filter(data_inicio__date__gte=dstart)
        if dend:
            qs = qs.filter(data_fim__date__lte=dend)
        return qs.order_by("data_inicio", "id")

    def perform_create(self, serializer):
        from rest_framework import serializers as drf_serializers

        from .services import AgendamentoService

        tenant = get_current_tenant(self.request)
        user = self.request.user
        cliente = _resolver_cliente_do_usuario(self.request)
        if not tenant or not cliente:
            raise permissions.PermissionDenied("Acesso de cliente não encontrado para este tenant")
        slot = serializer.validated_data.get("slot")
        data_inicio = serializer.validated_data.get("data_inicio")
        data_fim = serializer.validated_data.get("data_fim")
        if not slot and (not data_inicio or not data_fim):
            raise permissions.PermissionDenied("Informe slot ou data_inicio/data_fim")
        profissional = serializer.validated_data.get("profissional") or (slot.profissional if slot else None)
        if not profissional:
            raise permissions.PermissionDenied("Profissional obrigatório")
        servico = self.request.data.get("servico_id")
        if servico:
            from servicos.models import Servico as _Servico

            try:
                _serv = _Servico.objects.select_related("perfil_clinico").get(id=servico)
            except _Servico.DoesNotExist:
                raise permissions.PermissionDenied(_("Serviço inválido"))
            if _serv.is_clinical and not can_schedule_clinical_service(user, _serv):
                raise permissions.PermissionDenied(str(CLINICAL_SCHEDULING_DENIED_MESSAGE))
        metadata = serializer.validated_data.get("metadata")
        try:
            with transaction.atomic():
                ag = AgendamentoService.criar(
                    tenant=tenant,
                    cliente=cliente,
                    profissional=profissional,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    origem="CLIENTE",
                    slot=slot,
                    servico=servico,
                    metadata={**(metadata or {}), "portal_cliente": True},
                    user=user,
                )
        except ValueError as e:
            raise drf_serializers.ValidationError({"detail": str(e)})
        serializer.instance = ag

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        from .services import AgendamentoService

        ag = self.get_object()
        motivo = request.data.get("motivo") or "Cancelado pelo Cliente"
        try:
            AgendamentoService.cancelar(ag, motivo=motivo, user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"status": "ok", "novo_status": ag.status})

    @action(detail=True, methods=["post"])
    def reagendar(self, request, pk=None):
        from .services import AgendamentoService

        ag = self.get_object()
        novo_slot_id = request.data.get("novo_slot")
        nova_data_inicio = request.data.get("nova_data_inicio")
        nova_data_fim = request.data.get("nova_data_fim")
        motivo = request.data.get("motivo") or "Reagendamento pelo Cliente"
        novo_slot = None
        if novo_slot_id:
            novo_slot = Slot.objects.filter(id=novo_slot_id, tenant=ag.tenant, ativo=True).first()
            if not novo_slot:
                return Response({"detail": "novo_slot inválido"}, status=400)
        if nova_data_inicio:
            from django.utils.dateparse import parse_datetime

            nova_data_inicio = parse_datetime(nova_data_inicio)
        if nova_data_fim:
            from django.utils.dateparse import parse_datetime

            nova_data_fim = parse_datetime(nova_data_fim)
        try:
            novo = AgendamentoService.reagendar(
                ag,
                novo_slot=novo_slot,
                nova_data_inicio=nova_data_inicio,
                nova_data_fim=nova_data_fim,
                user=request.user,
                motivo=motivo,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        ser = self.get_serializer(novo)
        return Response(ser.data)


class AuditoriaAgendamentoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditoriaAgendamento.objects.select_related("agendamento", "user").all()
    serializer_class = AuditoriaAgendamentoSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgendamentoAuditoria]

    def get_queryset(self):
        tenant = get_current_tenant(self.request)
        return AuditoriaAgendamento.objects.filter(agendamento__tenant=tenant)
