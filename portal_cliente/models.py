"""Modelos do Portal Cliente."""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimestampedModel

User = get_user_model()


class ContaCliente(TimestampedModel):
    """Relaciona um usuário interno a um cliente externo para acesso portal."""

    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.CASCADE, related_name="contas_portal")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contas_cliente")
    ativo = models.BooleanField(default=True)
    is_admin_portal = models.BooleanField(default=False)
    data_concessao = models.DateTimeField(default=timezone.now)
    data_ultimo_acesso = models.DateTimeField(null=True, blank=True)
    concedido_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="contas_cliente_concedidas"
    )
    observacoes = models.TextField(blank=True)

    class Meta:
        db_table = "portal_cliente_conta"
        unique_together = ("cliente", "usuario")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["cliente", "ativo"]),
            models.Index(fields=["usuario", "ativo"]),
        ]
        verbose_name = _("Conta Cliente")
        verbose_name_plural = _("Contas Cliente")

    def __str__(self):
        return f"{self.usuario} -> {self.cliente}"

    def pode_acessar_portal(self):
        return self.ativo and self.usuario.is_active and getattr(self.cliente, "portal_ativo", True)

    def registrar_acesso(self):
        self.data_ultimo_acesso = timezone.now()
        self.save(update_fields=["data_ultimo_acesso"])


class DocumentoPortalCliente(TimestampedModel):
    """Mapa de documentos (referência a DocumentoVersao) liberados a uma conta cliente.
    Permite controle explícito do que é visível no portal sem expor tudo.
    """

    conta = models.ForeignKey(ContaCliente, on_delete=models.CASCADE, related_name="documentos")
    documento_versao = models.ForeignKey(
        "documentos.DocumentoVersao", on_delete=models.CASCADE, related_name="exposicoes_cliente"
    )
    titulo_externo = models.CharField(max_length=160, blank=True)
    descricao_externa = models.TextField(blank=True)
    expiracao_visualizacao = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "portal_cliente_doc"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conta", "ativo"]),
            models.Index(fields=["ativo"]),
        ]
        verbose_name = _("Documento Portal Cliente")
        verbose_name_plural = _("Documentos Portal Cliente")
        constraints = [models.UniqueConstraint(fields=["conta", "documento_versao"], name="unique_doc_portal_cliente")]

    def esta_visivel(self):
        if not self.ativo:
            return False
        return not (self.expiracao_visualizacao and self.expiracao_visualizacao < timezone.now())
