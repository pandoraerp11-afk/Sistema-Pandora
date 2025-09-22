# core/wizard_extensions.py - Sistema de extensão ZERO-RISK
"""
Extensões para o wizard que NÃO modificam o código original
Permite reutilizar funcionalidade sem tocar no wizard_views.py existente
"""

from typing import Any

from django.db import models


class WizardExtensionMixin:
    """
    Mixin que permite estender o wizard existente sem modificar o código original
    Funciona como um "plugin" que adiciona funcionalidades
    """

    # Configurações que podem ser sobrescritas por módulos específicos
    entity_model: models.Model | None = None
    entity_name: str = ""
    entity_verbose_name: str = ""

    # Permissões específicas (override do test_func original)
    requires_superuser: bool = False
    requires_tenant_access: bool = True

    def get_entity_config(self) -> dict[str, Any]:
        """Retorna configuração específica da entidade"""
        return {
            "model": self.entity_model,
            "name": self.entity_name,
            "verbose_name": self.entity_verbose_name,
            "requires_superuser": self.requires_superuser,
            "requires_tenant_access": self.requires_tenant_access,
        }

    def adapt_wizard_for_entity(self):
        """
        Adapta o wizard existente para a entidade específica
        Chamado automaticamente, não requer modificação do wizard original
        """
        config = self.get_entity_config()

        # Adaptar títulos
        if hasattr(self, "get_context_data"):
            original_get_context_data = self.get_context_data

            def adapted_get_context_data(**kwargs):
                context = original_get_context_data(**kwargs)
                context.update(
                    {
                        "entity_type": config["name"],
                        "entity_verbose_name": config["verbose_name"],
                    }
                )
                return context

            self.get_context_data = adapted_get_context_data

    def get_editing_entity(self):
        """Método genérico para pegar entidade sendo editada"""
        if not self.entity_model:
            return None

        entity_pk = self.kwargs.get("pk")
        if entity_pk:
            try:
                queryset = self.entity_model.objects.all()

                # Aplicar filtro de tenant se necessário
                if self.requires_tenant_access and hasattr(self.request, "tenant"):
                    queryset = queryset.filter(tenant=self.request.tenant)

                return queryset.get(pk=entity_pk)
            except self.entity_model.DoesNotExist:
                return None
        return None


class ClienteWizardMixin(WizardExtensionMixin):
    """Configurações específicas para wizard de clientes"""

    entity_name = "cliente"
    entity_verbose_name = "Cliente"
    requires_superuser = False  # Override: clientes não precisam de superuser
    requires_tenant_access = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Importação lazy para evitar problemas circulares
        from clientes.models import Cliente

        self.entity_model = Cliente


class FornecedorWizardMixin(WizardExtensionMixin):
    """Configurações específicas para wizard de fornecedores"""

    entity_name = "fornecedor"
    entity_verbose_name = "Fornecedor"
    requires_superuser = False
    requires_tenant_access = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Importação lazy
        from fornecedores.models import Fornecedor

        self.entity_model = Fornecedor
