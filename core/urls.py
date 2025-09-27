"""Rotas do módulo core (mantidas sem rotas de documentos locais)."""

from django.urls import path
from django.views.generic import RedirectView

from . import api_views, views
from .views_wizard_metrics import wizard_metrics_view  # endpoint de métricas internas do wizard (staff-only)

# Import direto dos componentes do wizard (arquivo principal agora incorporado em views refatoradas)
from .wizard_views import (
    TenantCreationWizardView,
    check_subdomain_availability,
    wizard_goto_step,
    wizard_validate_field,
)

# A declaração do nome do app é essencial.
app_name = "core"

# ESTAS SÃO AS ÚNICAS ROTAS QUE DEVEM ESTAR NESTE ARQUIVO.
urlpatterns = [
    # --- Autenticação e Seleção de Tenant ---
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("tenant-select/", views.tenant_select, name="tenant_select"),
    # --- Dashboard do Módulo CORE (específico) ---
    path("home/", views.core_home, name="core_home"),
    # --- Gerenciamento de Tenants (Páginas HTML) ---
    path("tenants/", views.TenantListView.as_view(), name="tenant_list"),
    # Rotas de criação/edição agora usam exclusivamente o Wizard moderno
    # Rotas canonicas (uso interno e externo) - criação/edição via Wizard
    path("tenants/create/", TenantCreationWizardView.as_view(), name="tenant_create"),
    path("tenants/<int:pk>/", views.TenantDetailView.as_view(), name="tenant_detail"),
    path("tenants/<int:pk>/edit/", TenantCreationWizardView.as_view(), name="tenant_update"),
    path("tenants/<int:pk>/delete/", views.TenantDeleteView.as_view(), name="tenant_delete"),
    path("tenants/<int:pk>/modules/", views.tenant_module_config, name="tenant_module_config"),
    # --- Rotas legacy (transitórias) - manter até 2025-10 para backlinks existentes ---
    # Redirecionam para as rotas canônicas evitando quebra de links antigos.
    path(
        "tenants/wizard/",
        RedirectView.as_view(pattern_name="core:tenant_create", permanent=True),
        name="tenant_wizard",
    ),
    path(
        "tenants/wizard/<int:pk>/edit/",
        RedirectView.as_view(pattern_name="core:tenant_update", permanent=True),
        name="tenant_wizard_edit",
    ),
    # Navegação de steps agora usa sempre tenant_create/tenant_update; mantemos endpoints goto como alias.
    path("tenants/wizard/step/<int:step>/", wizard_goto_step, name="wizard_goto_step"),
    # Alias explícito para edição evitando template quebrar caso espere nome separado
    path("tenants/wizard/<int:pk>/edit/step/<int:step>/", wizard_goto_step, name="wizard_goto_step_edit"),
    path("tenants/wizard/validate-field/", wizard_validate_field, name="tenant_wizard_validate_field"),
    path("tenants/check-subdomain/", check_subdomain_availability, name="check_subdomain"),
    # Alias legacy (apenas para compatibilidade de testes migrados / backlinks internos).
    # NOTE(compat): alias temporário; remover após migrar testes para 'check_subdomain' (meta 2025-11).
    path(
        "tenants/check-subdomain-legacy/",
        check_subdomain_availability,
        name="tenant_subdomain_check",
    ),
    # --- Gerenciamento de Usuários do Tenant ---
    path("tenant-users/", views.TenantUserListView.as_view(), name="tenant_user_list"),
    path("tenant-users/create/", views.TenantUserCreateView.as_view(), name="tenant_user_create"),
    path("tenant-users/<int:pk>/edit/", views.TenantUserUpdateView.as_view(), name="tenant_user_update"),
    path("tenant-users/<int:pk>/delete/", views.TenantUserDeleteView.as_view(), name="tenant_user_delete"),
    path("tenant-users/<int:pk>/detail/", views.TenantUserDetailView.as_view(), name="tenant_user_detail"),
    path("tenant-users/<int:pk>/permissions/", views.tenant_user_permissions, name="tenant_user_permissions"),
    path("tenant-users/<int:pk>/toggle-status/", views.tenant_user_toggle_status, name="tenant_user_toggle_status"),
    path("tenant-users/<int:pk>/reset-password/", views.tenant_user_reset_password, name="tenant_user_reset_password"),
    # --- Gerenciamento de Cargos e Permissões ---
    path("roles/", views.RoleListView.as_view(), name="role_list"),
    path("roles/create/", views.RoleCreateView.as_view(), name="role_create"),
    path("roles/<int:pk>/", views.RoleDetailView.as_view(), name="role_detail"),
    path("roles/<int:pk>/edit/", views.RoleUpdateView.as_view(), name="role_update"),
    path("roles/<int:pk>/delete/", views.RoleDeleteView.as_view(), name="role_delete"),
    path("roles/<int:pk>/permissions/", views.role_permissions, name="role_permissions"),
    # --- Gerenciamento de Departamentos ---
    path("departments/", views.DepartmentListView.as_view(), name="department_list"),
    path("departments/create/", views.DepartmentCreateView.as_view(), name="department_create"),
    path("departments/<int:pk>/", views.DepartmentDetailView.as_view(), name="department_detail"),
    path("departments/<int:pk>/edit/", views.DepartmentUpdateView.as_view(), name="department_update"),
    path("departments/<int:pk>/delete/", views.DepartmentDeleteView.as_view(), name="department_delete"),
    # --- Relatórios do Módulo Core ---
    path("reports/", views.core_reports, name="reports"),
    # --- Configurações Globais do Sistema (Super Admin) ---
    path("global-configurations/", views.system_global_configurations, name="global_configurations"),
    path("tenant-switch/<int:tenant_id>/", views.switch_tenant, name="switch_tenant"),
    # --- APIs ---
    path("api/dashboard/metrics/", api_views.dashboard_metrics, name="dashboard_metrics"),
    path("api/tenants/", api_views.api_tenant_list, name="api_tenant_list"),
    path("api/tenants/create/", api_views.api_tenant_create, name="api_tenant_create"),
    path("api/tenants/switch/<int:tenant_id>/", api_views.api_switch_tenant, name="api_switch_tenant"),
    path("api/modules/diagnostics/", api_views.api_module_diagnostics, name="api_module_diagnostics"),
    path("api/permissions/cache/", api_views.api_permission_cache_inspect, name="api_permission_cache_inspect"),
    path("api/cargo/suggestions/", api_views.api_cargo_suggestions, name="api_cargo_suggestions"),
    path("api/departments/", api_views.api_departments_list, name="api_departments_list"),
    # Alias compat solicitado pelos testes migrados
    path("api/departments-legacy/", api_views.api_departments_list, name="departments_api"),
    path("api/ui-permissions/", views.ui_permissions_json, name="ui_permissions_json"),
    # --- Métricas internas do Wizard (staff only) ---
    path("wizard/metrics/", wizard_metrics_view, name="wizard_metrics"),
]
