"""Modelos do Portal Cliente.

Inclui modelos de vínculo de contas e documentos exibidos no portal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimestampedModel

User = get_user_model()


class ContaCliente(TimestampedModel):
    """Relaciona um usuário interno a um cliente externo para acesso portal.

    Também provê propriedades utilitárias de acesso e compatibilidade legada.
    """

    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.CASCADE, related_name="contas_portal")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contas_cliente")
    ativo = models.BooleanField(default=True)
    is_admin_portal = models.BooleanField(default=False)
    data_concessao = models.DateTimeField(default=timezone.now)
    data_ultimo_acesso = models.DateTimeField(null=True, blank=True)
    concedido_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contas_cliente_concedidas",
    )
    observacoes = models.TextField(blank=True)

    # ------------------------------------------------------------------
    # COMPATIBILIDADE LEGADA
    # Alguns trechos antigos (e novos testes) tentam criar ContaCliente
    # passando 'tenant=' diretamente, embora o vínculo já seja derivado
    # via cliente. Para não quebrar chamadas existentes, aceitamos
    # 'tenant' em __init__ e validamos consistência se também vier 'cliente'.
    # ------------------------------------------------------------------
    def __init__(self, *args: object, **kwargs: object) -> None:
        """Aceita kw legacy 'tenant' (derivado de cliente)."""
        tenant = kwargs.pop("tenant", None)  # ignorado se divergente de cliente.tenant
        super().__init__(*args, **kwargs)
        if tenant is not None:
            cli = getattr(self, "cliente", None)
            if cli is not None and getattr(cli, "tenant_id", None) != getattr(tenant, "id", None):
                msg = "tenant passado não corresponde ao tenant do cliente"
                raise ValueError(msg)
            # Se cliente ainda não definido, será consistente após atribuição.

    @property
    def tenant(self) -> Tenant | None:
        """Retorna o tenant derivado do cliente associado (compatibilidade).

        Returns:
            Tenant | None: Instância do tenant ou ``None`` se cliente ainda
            não foi associado.

        """
        cli = getattr(self, "cliente", None)
        return getattr(cli, "tenant", None)

    class Meta:
        """Configurações de metadados do Django (tabelas, índices, etc.)."""

        db_table = "portal_cliente_conta"
        unique_together: ClassVar[tuple[str, str]] = ("cliente", "usuario")
        ordering: ClassVar[tuple[str, ...]] = ("-created_at",)
        indexes: ClassVar[tuple[models.Index, ...]] = (
            models.Index(fields=["cliente", "ativo"]),
            models.Index(fields=["usuario", "ativo"]),
        )
        verbose_name = _("Conta Cliente")
        verbose_name_plural = _("Contas Cliente")

    def __str__(self) -> str:
        """Representação textual curta."""
        return f"{self.usuario} -> {self.cliente}"

    def pode_acessar_portal(self) -> bool:
        """Indica se a conta tem permissão de acesso ao portal no momento.

        Considera flags de atividade da conta, usuário e cliente.
        """
        return bool(self.ativo and self.usuario.is_active and getattr(self.cliente, "portal_ativo", True))

    def registrar_acesso(self) -> None:
        """Atualiza a data/hora do último acesso efetuado."""
        self.data_ultimo_acesso = timezone.now()
        self.save(update_fields=["data_ultimo_acesso"])


class DocumentoPortalCliente(TimestampedModel):
    """Mapa de documentos (referência a DocumentoVersao) liberados a uma conta cliente.

    Permite controle explícito do que é visível no portal sem expor tudo.
    """

    conta = models.ForeignKey(ContaCliente, on_delete=models.CASCADE, related_name="documentos")
    documento_versao = models.ForeignKey(
        "documentos.DocumentoVersao",
        on_delete=models.CASCADE,
        related_name="exposicoes_cliente",
    )
    titulo_externo = models.CharField(max_length=160, blank=True)
    descricao_externa = models.TextField(blank=True)
    expiracao_visualizacao = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        """Metadados do Django para Documentos do Portal."""

        db_table = "portal_cliente_doc"
        ordering: ClassVar[tuple[str, ...]] = ("-created_at",)
        indexes: ClassVar[tuple[models.Index, ...]] = (
            models.Index(fields=["conta", "ativo"]),
            models.Index(fields=["ativo"]),
        )
        verbose_name = _("Documento Portal Cliente")
        verbose_name_plural = _("Documentos Portal Cliente")
        constraints: ClassVar[tuple[models.UniqueConstraint, ...]] = (
            models.UniqueConstraint(fields=["conta", "documento_versao"], name="unique_doc_portal_cliente"),
        )

    def esta_visivel(self) -> bool:
        """Retorna ``True`` se o documento está ativo e dentro do prazo de visualização."""
        if not self.ativo:
            return False
        return not (self.expiracao_visualizacao and self.expiracao_visualizacao < timezone.now())


class PortalClienteConfiguracao(TimestampedModel):
    """Parâmetros configuráveis por tenant para o Portal Cliente.

    Se um registro não existir para um tenant, os defaults globais (settings / conf getters)
    são utilizados. Mantemos apenas campos atualmente necessários; novos podem ser adicionados
    sem quebrar consumidores.
    """

    tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE, related_name="portal_config")
    checkin_antecedencia_min = models.PositiveIntegerField(default=30)
    checkin_tolerancia_pos_min = models.PositiveIntegerField(default=60)
    finalizacao_tolerancia_horas = models.PositiveIntegerField(default=6)
    cancelamento_limite_horas = models.PositiveIntegerField(default=24)
    throttle_checkin = models.PositiveIntegerField(default=12)
    throttle_finalizar = models.PositiveIntegerField(default=10)
    throttle_avaliar = models.PositiveIntegerField(default=10)

    class Meta:
        """Metadados Django para configuração multi-tenant do portal."""

        verbose_name = "Config Portal Cliente"
        verbose_name_plural = "Configs Portal Cliente"

    def __str__(self) -> str:  # pragma: no cover - representação simples
        """Retorna representação curta indicando o tenant."""
        return f"PortalClienteConfiguracao(tenant={self.tenant_id})"


if TYPE_CHECKING:  # Import somente para tipagem para evitar ciclos em runtime
    from core.models import Tenant
