# core/templatetags/core_tags.py (Versão Corrigida)

from django import template

# CORREÇÃO: Usando imports relativos para melhor compatibilidade com editores de código.
from ..models import Tenant, TenantUser
from ..utils import format_cnpj as format_cnpj_util
from ..utils import format_phone as format_phone_util
from ..utils import get_current_tenant

register = template.Library()


@register.simple_tag(takes_context=True)
def get_tenant(context):
    request = context.get("request")
    if request:
        return get_current_tenant(request)
    return None


@register.simple_tag(takes_context=True)
def is_module_enabled(context, module_name):
    """Versão simplificada: delega a Tenant.is_module_enabled (canonical)."""
    request = context.get("request")
    if not request or not module_name:
        return False
    if getattr(request.user, "is_superuser", False):
        return True
    tenant = get_current_tenant(request)
    return tenant.is_module_enabled(module_name) if tenant else False


@register.simple_tag(takes_context=True)
def user_has_tenant_permission(context, permission_codename):
    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return False
    user = request.user
    if user.is_superuser:
        return True
    tenant = get_current_tenant(request)
    if not tenant:
        return False
    try:
        tenant_user = TenantUser.objects.select_related("role__permissions").get(user=user, tenant=tenant)
        if not tenant_user.role:
            return False
        return tenant_user.role.permissions.filter(codename=permission_codename).exists()
    except TenantUser.DoesNotExist:
        return False


@register.simple_tag(takes_context=True)
def is_tenant_admin(context):
    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return False
    tenant = get_current_tenant(request)
    if not tenant:
        return False
    if request.user.is_superuser:
        return True
    return TenantUser.objects.filter(tenant=tenant, user=request.user, is_tenant_admin=True).exists()


@register.simple_tag(takes_context=True)
def get_enabled_modules(context):
    request = context.get("request")
    if not request:
        return []
    tenant = get_current_tenant(request)
    if not tenant:
        return []
    return tenant.enabled_modules.get("modules", [])


@register.simple_tag(takes_context=True)
def get_all_tenants(context):
    """Retorna todos os tenants que o usuário atual tem acesso"""
    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return []

    user = request.user
    if user.is_superuser:
        # Superusuário tem acesso a todos os tenants
        return Tenant.objects.all().order_by("name")

    # Usuário comum só tem acesso aos tenants onde é membro
    tenant_users = TenantUser.objects.filter(user=user).select_related("tenant")
    return [tu.tenant for tu in tenant_users]


@register.filter(name="has_module")
def has_module(module_list, module_name):
    return module_name in module_list


@register.filter
def format_cnpj(cnpj):
    return format_cnpj_util(cnpj)


@register.filter
def format_phone(phone):
    return format_phone_util(phone)


@register.filter
def truncate_words_custom(value, length=20):
    try:
        words = str(value).split()
        if len(words) > length:
            return " ".join(words[:length]) + "..."
        return value
    except (ValueError, TypeError):
        return value


@register.filter
def get_item(dictionary, key):
    """
    Filtro para acessar itens de dicionário no template.
    Usado nos templates ultra modernos para acessar valores dinâmicos.
    """
    try:
        if hasattr(dictionary, "get"):
            return dictionary.get(key)
        elif hasattr(dictionary, "__getitem__"):
            return dictionary[key]
        else:
            return None
    except (KeyError, TypeError, AttributeError):
        return None


@register.filter
def replace_id(value, replacement=""):
    """
    Filtro para substituir IDs nos templates ultra modernos.
    Remove ou substitui caracteres especiais em IDs para uso em JavaScript/CSS.
    """
    try:
        if value is None:
            return replacement

        value_str = str(value)

        # Remove caracteres especiais comuns em IDs
        value_str = value_str.replace(".", "_")
        value_str = value_str.replace("-", "_")
        value_str = value_str.replace(" ", "_")
        value_str = value_str.replace("/", "_")
        value_str = value_str.replace("\\", "_")
        value_str = value_str.replace(":", "_")
        value_str = value_str.replace(";", "_")
        value_str = value_str.replace(",", "_")
        value_str = value_str.replace("(", "_")
        value_str = value_str.replace(")", "_")
        value_str = value_str.replace("[", "_")
        value_str = value_str.replace("]", "_")
        value_str = value_str.replace("{", "_")
        value_str = value_str.replace("}", "_")

        # Remove underscores duplos
        while "__" in value_str:
            value_str = value_str.replace("__", "_")

        # Remove underscores no início e fim
        value_str = value_str.strip("_")

        return value_str if value_str else replacement

    except (ValueError, TypeError, AttributeError):
        return replacement


@register.filter
def safe_getattr(obj, attr_name, default=None):
    """
    Filtro para acessar atributos de objetos de forma segura.
    Usado nos templates ultra modernos para acessar propriedades dinâmicas.
    """
    try:
        return getattr(obj, attr_name, default)
    except (AttributeError, TypeError):
        return default


@register.filter
def to_json(value):
    """
    Filtro para converter valores Python para JSON nos templates.
    Útil para passar dados para JavaScript nos templates ultra modernos.
    """
    try:
        import json

        return json.dumps(value)
    except (TypeError, ValueError):
        return "{}"


@register.filter
def format_currency(value):
    """
    Filtro para formatar valores monetários em formato brasileiro.
    """
    try:
        if value is None or value == "":
            return "R$ 0,00"

        # Converte para float se necessário
        if isinstance(value, str):
            # Remove caracteres não numéricos exceto ponto e vírgula
            value = value.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
            value = float(value)
        elif not isinstance(value, (int, float)):
            return "R$ 0,00"

        # Formata para formato brasileiro
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"


@register.filter
def format_cpf(cpf):
    """
    Filtro para formatar CPF em formato brasileiro.
    """
    try:
        if not cpf:
            return ""

        # Remove caracteres não numéricos
        cpf_clean = "".join(filter(str.isdigit, str(cpf)))

        if len(cpf_clean) != 11:
            return cpf  # Retorna original se não tiver 11 dígitos

        # Formata CPF: XXX.XXX.XXX-XX
        return f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:11]}"
    except (ValueError, TypeError):
        return cpf


@register.filter
def format_cnpj_filter(cnpj):
    """
    Filtro para formatar CNPJ em formato brasileiro.
    """
    try:
        if not cnpj:
            return ""

        # Remove caracteres não numéricos
        cnpj_clean = "".join(filter(str.isdigit, str(cnpj)))

        if len(cnpj_clean) != 14:
            return cnpj  # Retorna original se não tiver 14 dígitos

        # Formata CNPJ: XX.XXX.XXX/XXXX-XX
        return f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:14]}"
    except (ValueError, TypeError):
        return cnpj


@register.filter
def format_phone_filter(phone):
    """
    Filtro para formatar telefone em formato brasileiro.
    """
    try:
        if not phone:
            return ""

        # Remove caracteres não numéricos
        phone_clean = "".join(filter(str.isdigit, str(phone)))

        if len(phone_clean) == 10:
            # Telefone fixo: (XX) XXXX-XXXX
            return f"({phone_clean[:2]}) {phone_clean[2:6]}-{phone_clean[6:10]}"
        elif len(phone_clean) == 11:
            # Celular: (XX) 9XXXX-XXXX
            return f"({phone_clean[:2]}) {phone_clean[2:7]}-{phone_clean[7:11]}"
        else:
            return phone  # Retorna original se não for formato conhecido
    except (ValueError, TypeError):
        return phone


@register.filter
def brazilian_date(date_value, format_str="d/m/Y"):
    """
    Filtro para formatar data em formato brasileiro.
    """
    try:
        if not date_value:
            return ""

        if hasattr(date_value, "strftime"):
            return date_value.strftime(format_str.replace("d", "%d").replace("m", "%m").replace("Y", "%Y"))

        return str(date_value)
    except (ValueError, TypeError, AttributeError):
        return str(date_value) if date_value else ""


@register.filter
def format_percentage(value, decimal_places=2):
    """
    Filtro para formatar percentual.
    """
    try:
        if value is None or value == "":
            return "0%"

        if isinstance(value, str):
            value = float(value.replace("%", "").replace(",", "."))

        return f"{value:.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "0%"


@register.filter
def add_class(field, css_class):
    """
    Filtro para adicionar classes CSS a campos de formulário.
    """
    try:
        if hasattr(field, "as_widget"):
            return field.as_widget(attrs={"class": css_class})
        return field
    except (AttributeError, TypeError):
        return field


@register.filter
def get_attribute(obj, attr_path):
    """
    Filtro para acessar atributos aninhados usando notação de ponto.
    Ex: obj|get_attribute:"user.profile.name"
    """
    try:
        value = obj
        for attr in attr_path.split("."):
            value = value.get(attr) if hasattr(value, "get") and callable(value.get) else getattr(value, attr, None)

            if value is None:
                return None

        return value
    except (AttributeError, TypeError):
        return None


@register.filter
def multiply(value, arg):
    """
    Filtro para multiplicar valores.
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """
    Filtro para dividir valores.
    """
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def format_decimal(value, decimal_places=2):
    """
    Filtro para formatar números decimais.
    """
    try:
        if value is None or value == "":
            return "0,00"

        if isinstance(value, str):
            value = float(value.replace(",", "."))

        formatted = f"{float(value):.{decimal_places}f}"
        return formatted.replace(".", ",")
    except (ValueError, TypeError):
        return "0,00"


@register.filter
def replace_url_id(url, object_id):
    """
    Filtro para substituir {id} nas URLs de ação com o ID real do objeto.
    """
    try:
        if url and object_id:
            return url.replace("{id}", str(object_id))
        return url
    except (ValueError, TypeError, AttributeError):
        return url


@register.filter
def lookup(dictionary, key):
    """
    Filtro para acessar valores de dicionário no template
    Uso: {{ dict|lookup:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, {})
    return {}
