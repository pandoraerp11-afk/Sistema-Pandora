import uuid

from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

User = get_user_model()


# Adicionar propriedade avatar ao modelo User
def user_avatar(self):
    """Propriedade para acessar avatar através do perfil estendido"""
    try:
        return self.perfil_estendido.avatar
    except Exception:
        return None


def user_avatar_url(self):
    """Propriedade para acessar URL do avatar"""
    try:
        return self.perfil_estendido.avatar_url
    except Exception:
        return None


# Adicionar as propriedades ao modelo User
User.add_to_class("avatar", property(user_avatar))
User.add_to_class("avatar_url", property(user_avatar_url))


class TipoUsuario(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Administrador"
    ADMIN_EMPRESA = "admin_empresa", "Administrador de Empresa"
    FUNCIONARIO = "funcionario", "Funcionário"
    CLIENTE = "cliente", "Cliente"
    FORNECEDOR = "fornecedor", "Fornecedor"
    PRESTADOR = "prestador", "Prestador de Serviço"


class StatusUsuario(models.TextChoices):
    ATIVO = "ativo", "Ativo"
    INATIVO = "inativo", "Inativo"
    SUSPENSO = "suspenso", "Suspenso"
    BLOQUEADO = "bloqueado", "Bloqueado"
    PENDENTE = "pendente", "Pendente"


class PerfilUsuarioEstendido(models.Model):
    """Perfil estendido para todos os usuários do sistema"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil_estendido")

    # Informações básicas
    tipo_usuario = models.CharField(max_length=20, choices=TipoUsuario.choices, default=TipoUsuario.FUNCIONARIO)
    status = models.CharField(max_length=20, choices=StatusUsuario.choices, default=StatusUsuario.PENDENTE)

    # Informações pessoais
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True, help_text="Foto do perfil do usuário")
    cpf = models.CharField(
        max_length=14,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", "CPF deve estar no formato XXX.XXX.XXX-XX")],
    )
    rg = models.CharField(max_length=20, null=True, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    celular = models.CharField(max_length=20, null=True, blank=True)

    # Endereço
    endereco = models.CharField(max_length=255, null=True, blank=True)
    numero = models.CharField(max_length=10, null=True, blank=True)
    complemento = models.CharField(max_length=100, null=True, blank=True)
    bairro = models.CharField(max_length=100, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    cep = models.CharField(max_length=10, null=True, blank=True)

    # Informações profissionais
    cargo = models.CharField(max_length=100, null=True, blank=True)
    departamento = models.CharField(max_length=100, null=True, blank=True)
    data_admissao = models.DateField(null=True, blank=True)
    salario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Configurações de segurança
    autenticacao_dois_fatores = models.BooleanField(default=False)
    # Segredo TOTP (Base32). Somente preenchido se 2FA habilitado; renovado ao resetar.
    totp_secret = models.CharField(max_length=64, null=True, blank=True)
    # Data/hora de confirmação (após primeiro token válido)
    totp_confirmed_at = models.DateTimeField(null=True, blank=True)
    # Lista de códigos de recuperação (hashes) JSONField; armazenar hashes para não expor em claro
    totp_recovery_codes = models.JSONField(default=list, blank=True)
    # Tentativas de 2FA falhas (pode servir para rate limiting futuro)
    failed_2fa_attempts = models.IntegerField(default=0)
    # Lockout temporário de 2FA
    twofa_locked_until = models.DateTimeField(null=True, blank=True)
    # Flag indicando se totp_secret está criptografado (para futura migração gradual)
    twofa_secret_encrypted = models.BooleanField(default=False)
    # Métricas 2FA
    twofa_success_count = models.PositiveIntegerField(default=0)
    twofa_failure_count = models.PositiveIntegerField(default=0)
    twofa_recovery_use_count = models.PositiveIntegerField(default=0)
    twofa_rate_limit_block_count = models.PositiveIntegerField(default=0)
    ultimo_login_ip = models.GenericIPAddressField(null=True, blank=True)
    tentativas_login_falhadas = models.IntegerField(default=0)
    bloqueado_ate = models.DateTimeField(null=True, blank=True)

    # Configurações de notificação
    receber_email_notificacoes = models.BooleanField(default=True)
    receber_sms_notificacoes = models.BooleanField(default=False)
    receber_push_notificacoes = models.BooleanField(default=True)

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios_criados",
    )

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["status"], name="perfil_status_idx"),
            models.Index(fields=["tipo_usuario"], name="perfil_tipo_idx"),
            models.Index(fields=["twofa_locked_until"], name="perfil_twofa_locked_idx"),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_tipo_usuario_display()}"

    @property
    def nome_completo(self):
        return self.user.get_full_name() or self.user.username

    @property
    def esta_ativo(self):
        return self.status == StatusUsuario.ATIVO and self.user.is_active

    @property
    def pode_fazer_login(self):
        if self.bloqueado_ate and self.bloqueado_ate > timezone.now():
            return False
        return self.esta_ativo

    @property
    def avatar_url(self):
        """Retorna URL do avatar ou placeholder"""
        if self.avatar:
            return self.avatar.url
        return None

    def get_avatar_display(self):
        """Retorna HTML para exibir avatar ou iniciais"""
        if self.avatar:
            return f'<img src="{self.avatar.url}" alt="{self.nome_completo}" class="rounded-circle" width="40" height="40">'
        iniciais = ""
        if self.user.first_name:
            iniciais += self.user.first_name[0].upper()
        if self.user.last_name:
            iniciais += self.user.last_name[0].upper()
        if not iniciais and self.user.username:
            iniciais = self.user.username[0].upper()
        return f'<div class="bg-primary rounded-circle d-flex align-items-center justify-content-center text-white" style="width: 40px; height: 40px;">{iniciais}</div>'


class ConviteUsuario(models.Model):
    """Sistema de convites para novos usuários"""

    email = models.EmailField()
    tipo_usuario = models.CharField(max_length=20, choices=TipoUsuario.choices)
    token = models.UUIDField(default=uuid.uuid4, unique=True)

    # Informações do convite
    nome_completo = models.CharField(max_length=255, null=True, blank=True)
    cargo = models.CharField(max_length=100, null=True, blank=True)
    departamento = models.CharField(max_length=100, null=True, blank=True)
    mensagem_personalizada = models.TextField(null=True, blank=True)

    # Status do convite
    enviado_em = models.DateTimeField(auto_now_add=True)
    aceito_em = models.DateTimeField(null=True, blank=True)
    expirado_em = models.DateTimeField()
    usado = models.BooleanField(default=False)

    # Relacionamentos
    enviado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name="convites_enviados")
    usuario_criado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="convite_origem",
    )
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="convites", null=True, blank=True)

    class Meta:
        verbose_name = "Convite de Usuário"
        verbose_name_plural = "Convites de Usuários"
        ordering = ["-enviado_em"]

    def __str__(self):
        return f"Convite para {self.email} - {self.get_tipo_usuario_display()}"

    @property
    def esta_expirado(self):
        return timezone.now() > self.expirado_em

    @property
    def pode_ser_usado(self):
        return not self.usado and not self.esta_expirado


class SessaoUsuario(models.Model):
    """Controle de sessões ativas dos usuários"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessoes")
    session_key = models.CharField(max_length=40, unique=True)
    # Ajuste: permitir null para satisfazer SystemCheck (fields.E150) quando blank
    ip_address = models.GenericIPAddressField(null=True, blank=True, default=None)
    user_agent = models.TextField()

    # Informações da sessão
    criada_em = models.DateTimeField(auto_now_add=True)
    ultima_atividade = models.DateTimeField(auto_now=True)
    ativa = models.BooleanField(default=True)

    # Localização (opcional)
    pais = models.CharField(max_length=100, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Sessão de Usuário"
        verbose_name_plural = "Sessões de Usuários"
        ordering = ["-ultima_atividade"]

    def __str__(self):
        return f"Sessão de {self.user.username} - {self.ip_address}"


class LogAtividadeUsuario(models.Model):
    """Log de atividades dos usuários para auditoria"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="logs_atividade")

    # Informações da atividade
    acao = models.CharField(max_length=100)
    descricao = models.TextField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    # Campo opcional para dados extras serializados (JSON compactado)
    extra_json = models.TextField(null=True, blank=True)

    # Metadados
    timestamp = models.DateTimeField(auto_now_add=True)
    modulo = models.CharField(max_length=50, null=True, blank=True)
    objeto_id = models.CharField(max_length=50, null=True, blank=True)
    objeto_tipo = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        verbose_name = "Log de Atividade"
        verbose_name_plural = "Logs de Atividades"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["acao", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.acao} - {self.timestamp}"


class PermissaoPersonalizada(models.Model):
    """Permissões personalizadas para usuários específicos"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="permissoes_personalizadas")
    # Escopo opcional por tenant (permite que a mesma combinação módulo/ação exista em tenants diferentes)
    # Mantido null/blank para suportar permissões globais (aplicáveis a todos os tenants do usuário)
    scope_tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="permissoes_personalizadas",
    )

    # Definição da permissão
    modulo = models.CharField(max_length=50)
    acao = models.CharField(max_length=50)  # create, read, update, delete, etc.
    recurso = models.CharField(max_length=100, null=True, blank=True)  # recurso específico

    # Status da permissão
    concedida = models.BooleanField(default=True)
    data_concessao = models.DateTimeField(auto_now_add=True)
    data_expiracao = models.DateTimeField(null=True, blank=True)

    # Metadados
    concedida_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="permissoes_concedidas",
    )
    observacoes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Permissão Personalizada"
        verbose_name_plural = "Permissões Personalizadas"
        # Agora a unicidade considera também o escopo (tenant) permitindo variações por tenant ou globais
        unique_together = ["user", "modulo", "acao", "recurso", "scope_tenant"]
        ordering = ["-data_concessao"]

    def __str__(self):
        status = "Concedida" if self.concedida else "Negada"
        return f"{self.user.username} - {self.modulo}.{self.acao} - {status}"

    @property
    def esta_ativa(self):
        if not self.concedida:
            return False
        return not (self.data_expiracao and timezone.now() > self.data_expiracao)


## Signals de criação de perfil duplicados removidos.

# Signals para invalidar cache de permissões
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


@receiver(post_save, sender=PermissaoPersonalizada)
def invalidate_perm_cache_save(sender, instance, **kwargs):
    """Usa API de invalidação do novo permission_resolver para versões específicas.
    Preferimos invalidar somente o tenant alvo (se houver) e o escopo global do usuário.
    """
    try:
        from shared.services.permission_resolver import permission_resolver

        if instance.scope_tenant_id:
            permission_resolver.invalidate_cache(user_id=instance.user_id, tenant_id=instance.scope_tenant_id)
        else:
            # Global do user (todos tenants do user)
            permission_resolver.invalidate_cache(user_id=instance.user_id)
    except Exception:
        pass


@receiver(post_delete, sender=PermissaoPersonalizada)
def invalidate_perm_cache_delete(sender, instance, **kwargs):
    try:
        from shared.services.permission_resolver import permission_resolver

        if instance.scope_tenant_id:
            permission_resolver.invalidate_cache(user_id=instance.user_id, tenant_id=instance.scope_tenant_id)
        else:
            permission_resolver.invalidate_cache(user_id=instance.user_id)
    except Exception:
        pass
