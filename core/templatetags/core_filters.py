from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.filter
def get_module_home_url(app_name):
    """
    Retorna a URL home do módulo baseada no app_name
    """
    if not app_name:
        return "#"

    # Mapeamento de apps para suas URLs home específicas
    home_url_mapping = {
        "core": "core:core_home",
        "clientes": "clientes:list",
        "fornecedores": "fornecedores:list",
        "produtos": "produtos:list",
        "servicos": "servicos:list",
        "financeiro": "financeiro:home",
        "obras": "obras:list",
        "orcamentos": "orcamentos:list",
        "estoque": "estoque:home",
        "funcionarios": "funcionarios:list",
        "compras": "compras:home",
        "bi": "bi:home",
        "relatorios": "relatorios:home",
        "user_management": "user_management:home",
        "admin": "admin:home",
    }

    url_name = home_url_mapping.get(app_name, f"{app_name}:home")

    try:
        return reverse(url_name)
    except NoReverseMatch:
        # Tenta variações comuns para core
        if app_name == "core":
            fallback_urls = ["core:tenant_list", "core:core_home", "core:tenant_select"]
            for fallback in fallback_urls:
                try:
                    return reverse(fallback)
                except NoReverseMatch:
                    continue

        # Último recurso: dashboard geral
        try:
            return reverse("dashboard")
        except NoReverseMatch:
            return "#"
        except NoReverseMatch:
            return "#"


@register.filter
def get_module_display_name(app_name):
    """
    Retorna o nome de exibição do módulo
    """
    if not app_name:
        return "Sistema"

    display_names = {
        "core": "Configurações",
        "clientes": "Clientes",
        "fornecedores": "Fornecedores",
        "produtos": "Produtos",
        "servicos": "Serviços",
        "financeiro": "Financeiro",
        "obras": "Obras",
        "orcamentos": "Orçamentos",
        "estoque": "Estoque",
        "funcionarios": "Funcionários",
        "compras": "Compras",
        "bi": "Business Intelligence",
        "relatorios": "Relatórios",
        "user_management": "Usuários",
        "admin": "Administração",
    }

    return display_names.get(app_name, app_name.title())
