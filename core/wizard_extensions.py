"""Mixins leves para extensão de wizards (metadados e contexto).

Sem alteração de regras de negócio: nenhuma validação ou persistência é
modificada; apenas acrescentamos metadados e suporte a edição.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.db import models  # noqa: TC002 - necessário em runtime (queries)

if TYPE_CHECKING:  # imports apenas para tipagem
    from collections.abc import Callable


class WizardExtensionMixin:
    """Fornece metas e adaptação de contexto aos wizards.

    Responsável somente por:
    - fornecer metadados da entidade
    - envolver get_context_data para adicionar chaves auxiliares
    - localizar entidade em edição
    """

    entity_model: type[models.Model] | None = None
    entity_name: str = ""
    entity_verbose_name: str = ""
    requires_superuser: bool = False
    requires_tenant_access: bool = True

    def get_entity_config(self) -> dict[str, Any]:
        """Retorna dicionário de metadados configurados."""
        return {
            "model": self.entity_model,
            "name": self.entity_name,
            "verbose_name": self.entity_verbose_name,
            "requires_superuser": self.requires_superuser,
            "requires_tenant_access": self.requires_tenant_access,
        }

    def adapt_wizard_for_entity(self) -> None:
        """Envolve get_context_data acrescentando chaves informativas.

        Idempotente: se o método já foi adaptado, a chamada subsequente não
        quebra comportamento (apenas redefine com mesma lógica).
        """
        if not hasattr(self, "get_context_data"):
            return
        config = self.get_entity_config()
        original: Callable[..., dict[str, Any]] = self.get_context_data

        def adapted_get_context_data(**kwargs: object) -> dict[str, Any]:
            # Chamamos a versão original; CBVs aceitam kwargs variados.
            ctx = original(**kwargs)  # assinatura dinâmica aceitável
            ctx.setdefault("entity_type", config["name"])
            ctx.setdefault("entity_verbose_name", config["verbose_name"])
            return ctx

        # Atribuição dinâmica controlada para enriquecer contexto sem alterar lógica.
        self.get_context_data = cast("Callable[..., dict[str, Any]]", adapted_get_context_data)

    def get_editing_entity(self) -> models.Model | None:
        """Retorna a entidade sendo editada (ou None)."""
        model = self.entity_model
        if model is None:
            return None
        pk_val = getattr(getattr(self, "kwargs", {}), "get", lambda *_: None)("pk")
        if not pk_val:
            return None
        try:
            qs = model.objects.all()
            if self.requires_tenant_access:
                req = getattr(self, "request", None)
                tenant_obj = getattr(req, "tenant", None)
                if tenant_obj is not None:
                    qs = qs.filter(tenant=tenant_obj)
            return qs.get(pk=pk_val)
        except model.DoesNotExist:  # pragma: no cover - fluxo raro
            return None


class ClienteWizardMixin(WizardExtensionMixin):
    """Metadados para wizards de Cliente."""

    entity_name = "cliente"
    entity_verbose_name = "Cliente"
    requires_superuser = False
    requires_tenant_access = True

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Importa e fixa o modelo Cliente (lazy para evitar ciclo)."""
        super().__init__(*args, **kwargs)
        from clientes.models import Cliente  # noqa: PLC0415 - lazy import evita ciclo

        self.entity_model = Cliente


class FornecedorWizardMixin(WizardExtensionMixin):
    """Metadados para wizards de Fornecedor."""

    entity_name = "fornecedor"
    entity_verbose_name = "Fornecedor"
    requires_superuser = False
    requires_tenant_access = True

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Importa e fixa o modelo Fornecedor (lazy)."""
        super().__init__(*args, **kwargs)
        from fornecedores.models import Fornecedor  # noqa: PLC0415 - lazy import evita ciclo

        self.entity_model = Fornecedor
