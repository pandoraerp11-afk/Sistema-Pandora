# core/wizard_base.py - Sistema Base Reutilizável para Wizard
"""
Sistema de Wizard Genérico e Reutilizável
Mantém toda a segurança multi-tenant existente
"""

from typing import Any

from django.db import models


class WizardEntityConfig:
    """
    Configuração base para diferentes tipos de entidades no wizard
    Permite reutilizar todo o código do wizard_views.py existente
    """

    # Dados básicos da entidade
    entity_name: str = ""  # Ex: "cliente", "fornecedor", "tenant"
    entity_model: type[models.Model] | None = None
    entity_verbose_name: str = ""

    # Modelos relacionados (PJ/PF)
    pj_model: type[models.Model] | None = None
    pf_model: type[models.Model] | None = None

    # Modelos de relacionamentos
    address_model: type[models.Model] | None = None
    contact_model: type[models.Model] | None = None
    document_model: type[models.Model] | None = None

    # URLs e redirecionamentos
    list_url_name: str = ""
    detail_url_name: str = ""

    # Configurações de steps específicas
    custom_steps: dict[int, dict[str, Any]] = {}

    # Permissões específicas
    requires_superuser: bool = False
    requires_tenant_admin: bool = False

    def get_wizard_steps(self) -> dict[int, dict[str, Any]]:
        """Retorna os steps do wizard com customizações específicas"""
        # Base steps (similar ao WIZARD_STEPS atual)
        base_steps = {
            1: {
                "name": "Identificação",
                "icon": "fas fa-user",
                "description": f"Dados básicos do {self.entity_verbose_name.lower()}",
            },
            2: {"name": "Endereços", "icon": "fas fa-map-marker-alt", "description": "Endereço principal"},
            3: {"name": "Contatos", "icon": "fas fa-phone", "description": "Telefones e e-mails"},
            4: {"name": "Documentos", "icon": "fas fa-file-alt", "description": "Documentos (opcional)"},
            5: {"name": "Confirmação", "icon": "fas fa-check-circle", "description": "Revisão dos dados"},
        }

        # Aplicar customizações específicas
        for step_num, custom_config in self.custom_steps.items():
            if step_num in base_steps:
                base_steps[step_num].update(custom_config)

        return base_steps


# Configurações específicas para cada módulo
class TenantWizardConfig(WizardEntityConfig):
    """Configuração para o wizard de Tenants (atual)"""

    entity_name = "tenant"
    entity_verbose_name = "Empresa"
    requires_superuser = True

    custom_steps = {
        5: {"name": "Configurações", "icon": "fas fa-cog", "description": "Planos e módulos"},
        6: {"name": "Usuário Admin", "icon": "fas fa-user-shield", "description": "Administrador inicial"},
        7: {"name": "Confirmação", "icon": "fas fa-check-circle", "description": "Revisão e confirmação"},
    }


class ClienteWizardConfig(WizardEntityConfig):
    """Configuração para o wizard de Clientes"""

    entity_name = "cliente"
    entity_verbose_name = "Cliente"
    requires_tenant_admin = True  # Requer acesso ao tenant, não superuser

    list_url_name = "clientes:clientes_list"
    detail_url_name = "clientes:clientes_detail"


class FornecedorWizardConfig(WizardEntityConfig):
    """Configuração para o wizard de Fornecedores"""

    entity_name = "fornecedor"
    entity_verbose_name = "Fornecedor"
    requires_tenant_admin = True

    list_url_name = "fornecedores:fornecedores_list"
    detail_url_name = "fornecedores:fornecedores_detail"

    custom_steps = {
        4: {"name": "Dados Bancários", "icon": "fas fa-university", "description": "Contas bancárias e PIX"},
        5: {"name": "Confirmação", "icon": "fas fa-check-circle", "description": "Revisão final"},
    }


# Registry de configurações
WIZARD_CONFIGS = {
    "tenant": TenantWizardConfig(),
    "cliente": ClienteWizardConfig(),
    "fornecedor": FornecedorWizardConfig(),
}


def get_wizard_config(entity_type: str) -> WizardEntityConfig:
    """Retorna a configuração do wizard para um tipo de entidade"""
    if entity_type not in WIZARD_CONFIGS:
        raise ValueError(f"Tipo de entidade '{entity_type}' não suportado")
    return WIZARD_CONFIGS[entity_type]
