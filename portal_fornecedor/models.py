"""
Modelo para acesso de fornecedores ao portal.
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimestampedModel

User = get_user_model()


class AcessoFornecedor(TimestampedModel):
    """
    Relaciona um usuário com um fornecedor para acesso ao portal.
    """

    fornecedor = models.ForeignKey(
        "fornecedores.Fornecedor", on_delete=models.CASCADE, related_name="acessos", verbose_name=_("Fornecedor")
    )
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="acessos_fornecedor", verbose_name=_("Usuário")
    )
    is_admin_portal = models.BooleanField(
        default=False,
        verbose_name=_("Administrador do Portal"),
        help_text=_("Usuário pode gerenciar outros usuários do fornecedor"),
    )
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"), help_text=_("Acesso ativo ao portal"))
    data_concessao = models.DateTimeField(default=timezone.now, verbose_name=_("Data de Concessão"))
    data_ultimo_acesso = models.DateTimeField(null=True, blank=True, verbose_name=_("Último Acesso"))
    concedido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acessos_fornecedor_concedidos",
        verbose_name=_("Concedido por"),
    )
    observacoes = models.TextField(blank=True, verbose_name=_("Observações"), help_text=_("Observações sobre o acesso"))

    class Meta:
        db_table = "portal_fornecedor_acesso"
        verbose_name = _("Acesso de Fornecedor")
        verbose_name_plural = _("Acessos de Fornecedores")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["fornecedor", "ativo"]),
            models.Index(fields=["usuario", "ativo"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["fornecedor", "usuario"], name="unique_acesso_fornecedor_usuario")
        ]

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} - {self.fornecedor}"

    def pode_acessar_portal(self):
        """Verifica se este acesso permite login no portal."""
        return self.ativo and self.fornecedor.pode_acessar_portal() and self.usuario.is_active

    def registrar_acesso(self):
        """Registra um novo acesso ao portal."""
        self.data_ultimo_acesso = timezone.now()
        self.save(update_fields=["data_ultimo_acesso"])

    @classmethod
    def criar_acesso(cls, fornecedor, usuario, is_admin=False, concedido_por=None):
        """Cria um novo acesso para fornecedor."""
        acesso, created = cls.objects.get_or_create(
            fornecedor=fornecedor,
            usuario=usuario,
            defaults={"is_admin_portal": is_admin, "concedido_por": concedido_por, "ativo": True},
        )
        return acesso, created
