# core/templatetags/menu_tags.py (VERSÃO ULTRA MODERNA - Refatorada)

from django import template
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe

from ..models import TenantUser
from ..utils import get_current_tenant

try:
    from ..authorization import AccessDecision, can_access_module
except Exception:  # caso arquivo ainda não carregado/migração inicial
    can_access_module = None  # type: ignore
    AccessDecision = None  # type: ignore

register = template.Library()


@register.simple_tag(takes_context=True)
def render_sidebar_menu(context):
    """Renderiza o menu lateral dinamicamente usando templates modernos
    compatível com o design ultra moderno e Bootstrap 5.
    """
    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return ""

    user = request.user

    # Verificar tenant com tratamento de erro aprimorado
    try:
        tenant = get_current_tenant(request) if hasattr(request, "session") else None
    except (AttributeError, KeyError):
        tenant = None

    # Verificar se é admin do tenant
    is_admin_of_tenant = False
    if tenant and not user.is_superuser:
        is_admin_of_tenant = TenantUser.objects.filter(tenant=tenant, user=user, is_tenant_admin=True).exists()

    def can_view_module(module_config):
        """Verifica se o usuário pode visualizar o módulo.
        Se FEATURE_UNIFIED_ACCESS estiver ativa e authorization disponível, usa a função central.
        Caso contrário, mantém lógica legada (com hardcode somente se FEATURE_REMOVE_MENU_HARDCODE for False).
        """
        if module_config.get("is_header"):
            return True

        module_name = module_config.get("module_name")

        # Caminho novo unificado
        if getattr(settings, "FEATURE_UNIFIED_ACCESS", False) and can_access_module:
            decision = can_access_module(user, tenant, module_name)
            return decision.allowed

        # Lógica legada reduzida (hardcode removido)
        if user.is_superuser:
            return True
        if module_config.get("tenant_admin_only") and not is_admin_of_tenant:
            return False
        if not module_name or not tenant:
            return False
        try:
            return tenant.is_module_enabled(module_name)
        except Exception:
            return False

    # Se usuário não tem tenant e não é superuser, provavelmente é usuário somente portal -> não renderiza menu corporativo
    if not tenant and not user.is_superuser:
        return ""

    # Processar módulos disponíveis
    available_modules = [m for m in settings.PANDORA_MODULES if isinstance(m, dict) and can_view_module(m)]

    # Agrupar módulos por seções
    menu_groups = _group_modules_by_sections(available_modules)

    # Processar URLs e estado ativo
    processed_groups = []
    for group in menu_groups:
        if group["items"]:
            processed_items = []
            for item in group["items"]:
                processed_item = _process_menu_item(item, request)
                if processed_item:
                    processed_items.append(processed_item)

            if processed_items:
                processed_groups.append({"header": group["header"], "items": processed_items})

    # Usar template para renderizar ao invés de concatenação manual
    menu_context = {"menu_groups": processed_groups, "request": request}

    try:
        return render_to_string("core/sidebar_menu.html", menu_context, request=request)
    except Exception:
        # Fallback para o sistema antigo se o template não existir
        return _render_menu_fallback(processed_groups, request)


def _group_modules_by_sections(modules):
    """Agrupa módulos por seções com cabeçalhos"""
    grouped_modules = []
    current_group = None

    for module in modules:
        if module.get("is_header"):
            if current_group:
                grouped_modules.append(current_group)
            current_group = {"header": module.get("name", ""), "items": []}
        elif current_group:
            current_group["items"].append(module)
        else:
            if not grouped_modules or "header" in grouped_modules[0]:
                grouped_modules.append({"header": None, "items": []})
            grouped_modules[-1]["items"].append(module)

    if current_group:
        grouped_modules.append(current_group)

    return grouped_modules


def _process_menu_item(module, request):
    """Processa um item do menu individual"""
    has_children = "children" in module and module["children"]
    is_active = False
    menu_url = "#"

    # Processar filhos se existirem
    processed_children = []
    if has_children:
        for child in module["children"]:
            try:
                child_url = reverse(child["url"])
                child_is_active = request.path == child_url
                if child_is_active:
                    is_active = True
                processed_children.append({"name": child["name"], "url": child_url, "is_active": child_is_active})
            except NoReverseMatch:
                continue
    elif "url" in module:
        try:
            menu_url = reverse(module["url"])
            is_active = request.path == menu_url
        except NoReverseMatch:
            menu_url = "#"

    # Gerar ID único para collapse (Bootstrap 5)
    collapse_id = f"submenu-{module.get('module_name', 'unknown')}" if has_children else None

    return {
        "name": module["name"],
        "url": menu_url,
        "icon": module.get("icon", "fas fa-circle"),
        "is_active": is_active,
        "has_children": has_children,
        "children": processed_children,
        "collapse_id": collapse_id,
        "module_name": module.get("module_name", ""),
    }


def _render_menu_fallback(processed_groups, request):
    """Sistema de fallback usando concatenação (compatibilidade)"""
    menu_html = ['<ul class="nav-list">']

    for group in processed_groups:
        if group["header"]:
            menu_html.append(f'<li class="nav-section-title">{group["header"]}</li>')

        for item in group["items"]:
            active_class = "active" if item["is_active"] else ""
            menu_html.append(f'<li class="nav-item {active_class}">')

            # Link principal
            if item["has_children"]:
                menu_html.append(
                    f'<a href="#" class="nav-link" '
                    f'data-bs-toggle="collapse" data-bs-target="#{item["collapse_id"]}" '
                    f'aria-expanded="{"true" if item["is_active"] else "false"}">',
                )
            else:
                link_class = "nav-link active" if item["is_active"] else "nav-link"
                menu_html.append(f'<a href="{item["url"]}" class="{link_class}">')

            menu_html.append(f'<i class="nav-icon {item["icon"]}"></i>')
            menu_html.append(f'<span class="nav-text">{item["name"]}</span>')

            if item["has_children"]:
                menu_html.append('<i class="nav-arrow fas fa-chevron-down"></i>')

            menu_html.append("</a>")

            # Submenu
            if item["has_children"]:
                collapse_class = "nav-submenu collapse"
                if item["is_active"]:
                    collapse_class += " show"

                menu_html.append(f'<ul id="{item["collapse_id"]}" class="{collapse_class}" data-bs-parent=".nav-list">')
                for child in item["children"]:
                    child_link_class = "nav-link active" if child["is_active"] else "nav-link"
                    # CORREÇÃO: Adicionando a classe "nav-item" ao <li> do submenu
                    menu_html.append(
                        f'<li class="nav-item"><a href="{child["url"]}" class="{child_link_class}"><span class="nav-text">{child["name"]}</span></a></li>',
                    )
                menu_html.append("</ul>")

            menu_html.append("</li>")

    menu_html.append("</ul>")
    return mark_safe("".join(menu_html))
