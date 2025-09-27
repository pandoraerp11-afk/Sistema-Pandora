"""Tags e filtros de template personalizados para a aplicação core.

Este módulo fornece um conjunto de tags e filtros para o sistema de templates
do Django, facilitando o acesso a dados específicos do tenant, formatação de
dados e verificação de permissões diretamente nos templates.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from django import template
from django.utils.safestring import SafeString, mark_safe

from core.models import Tenant, TenantUser
from core.utils import get_current_tenant

if TYPE_CHECKING:
    from django.forms import BoundField

register = template.Library()

# ==============================================================================
# CONSTANTES
# ==============================================================================

CPF_LENGTH = 11
CNPJ_LENGTH = 14
PHONE_LANDLINE_LENGTH = 10
PHONE_MOBILE_LENGTH = 11


# ==============================================================================
# TAGS DE TEMPLATE
# ==============================================================================


@register.simple_tag(takes_context=True)
def get_tenant(context: dict[str, Any]) -> Tenant | None:
    """Retorna o tenant atual com base na requisição."""
    request = context.get("request")
    return get_current_tenant(request) if request else None


@register.simple_tag(takes_context=True)
def is_module_enabled(context: dict[str, Any], module_name: str) -> bool:
    """Verifica se um módulo está habilitado para o tenant atual."""
    request = context.get("request")
    if not request or not module_name:
        return False

    user = getattr(request, "user", None)
    if user and getattr(user, "is_superuser", False):
        return True

    tenant = get_current_tenant(request)
    return tenant.is_module_enabled(module_name) if tenant else False


@register.simple_tag(takes_context=True)
def user_has_tenant_permission(context: dict[str, Any], permission_codename: str) -> bool:
    """Verifica se o usuário tem uma permissão específica no tenant."""
    request = context.get("request")
    if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
        return False

    user = request.user
    if user.is_superuser:
        return True

    tenant = get_current_tenant(request)
    if not tenant:
        return False

    try:
        tenant_user = TenantUser.objects.select_related("role__permissions").get(
            user=user,
            tenant=tenant,
        )
    except TenantUser.DoesNotExist:
        return False
    else:
        if not tenant_user.role:
            return False
        return tenant_user.role.permissions.filter(codename=permission_codename).exists()


@register.simple_tag(takes_context=True)
def is_tenant_admin(context: dict[str, Any]) -> bool:
    """Verifica se o usuário é administrador do tenant atual."""
    request = context.get("request")
    if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
        return False

    if request.user.is_superuser:
        return True

    tenant = get_current_tenant(request)
    if not tenant:
        return False

    return TenantUser.objects.filter(
        tenant=tenant,
        user=request.user,
        is_tenant_admin=True,
    ).exists()


@register.simple_tag(takes_context=True)
def get_enabled_modules(context: dict[str, Any]) -> list[str]:
    """Retorna a lista de módulos habilitados para o tenant atual."""
    request = context.get("request")
    tenant = get_current_tenant(request) if request else None
    return tenant.enabled_modules.get("modules", []) if tenant else []


@register.simple_tag(takes_context=True)
def get_all_tenants(context: dict[str, Any]) -> list[Tenant]:
    """Retorna todos os tenants aos quais o usuário atual tem acesso."""
    request = context.get("request")
    if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
        return []

    user = request.user
    if user.is_superuser:
        return list(Tenant.objects.all().order_by("name"))

    tenant_users = TenantUser.objects.filter(user=user).select_related("tenant")
    return [tu.tenant for tu in tenant_users]


# ==============================================================================
# FILTROS DE TEMPLATE
# ==============================================================================


@register.filter(name="has_module")
def has_module(module_list: list[str], module_name: str) -> bool:
    """Verifica se um nome de módulo existe em uma lista de módulos."""
    return module_name in module_list


@register.filter
def format_cnpj(cnpj: str | None) -> str:
    """Formata um número de CNPJ (XX.XXX.XXX/XXXX-XX)."""
    if not cnpj:
        return ""
    try:
        cnpj_clean = "".join(filter(str.isdigit, str(cnpj)))
        if len(cnpj_clean) != CNPJ_LENGTH:
            return str(cnpj)
    except (ValueError, TypeError):
        return str(cnpj)
    else:
        return f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:14]}"


@register.filter
def format_phone(phone: str | None) -> str:
    """Formata um número de telefone fixo ou celular."""
    if not phone:
        return ""
    try:
        phone_clean = "".join(filter(str.isdigit, str(phone)))
        if len(phone_clean) == PHONE_LANDLINE_LENGTH:
            return f"({phone_clean[:2]}) {phone_clean[2:6]}-{phone_clean[6:10]}"
        if len(phone_clean) == PHONE_MOBILE_LENGTH:
            return f"({phone_clean[:2]}) {phone_clean[2:7]}-{phone_clean[7:11]}"
    except (ValueError, TypeError):
        return str(phone)
    else:
        return str(phone)


@register.filter
def truncate_words_custom(value: Any, length: int = 20) -> str:  # noqa: ANN401
    """Trunca uma string para um número específico de palavras."""
    try:
        words = str(value).split()
        if len(words) > length:
            return " ".join(words[:length]) + "..."
    except (ValueError, TypeError):
        return str(value)
    else:
        return str(value)


@register.filter
def get_item(dictionary: Any, key: Any) -> Any:  # noqa: ANN401
    """Filtro para acessar itens de dicionário ou atributos de objeto no template."""
    try:
        if hasattr(dictionary, "get"):
            return dictionary.get(key)
        return dictionary[key]
    except (KeyError, TypeError, AttributeError):
        return None


@register.filter
def replace_id(value: Any, replacement: str = "") -> str:  # noqa: ANN401
    """Substitui caracteres especiais em uma string para uso como ID."""
    if value is None:
        return replacement
    try:
        value_str = str(value)
        # Substitui múltiplos caracteres especiais por um underscore
        value_str = re.sub(r"[.\- /\\:;,()\[\]{}]", "_", value_str)
        # Remove underscores duplicados
        value_str = re.sub(r"__+", "_", value_str)
        # Remove underscores no início e no fim
        value_str = value_str.strip("_")
    except (ValueError, TypeError):
        return replacement
    else:
        return value_str or replacement


@register.filter
def safe_getattr(
    obj: Any,  # noqa: ANN401
    attr_name: str,
    default: Any = None,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Acessa um atributo de um objeto de forma segura, retornando um padrão em caso de falha."""
    try:
        return getattr(obj, attr_name, default)
    except (AttributeError, TypeError):
        return default


@register.filter(name="to_json")
def to_json(value: Any) -> SafeString:  # noqa: ANN401
    """Converta um valor Python para uma string JSON segura para uso em templates."""
    try:
        json_string = json.dumps(value)
    except (TypeError, ValueError):
        return mark_safe("{}")
    else:
        # json.dumps escapa caracteres HTML, tornando o uso de mark_safe seguro aqui.
        return mark_safe(json_string)  # noqa: S308


@register.filter
def format_currency(value: Any) -> str:  # noqa: ANN401
    """Formata um valor numérico como moeda brasileira (R$)."""
    if value is None or value == "":
        return "R$ 0,00"
    try:
        if isinstance(value, str):
            value = float(value.replace("R$", "").strip().replace(".", "").replace(",", "."))
        formatted_value = f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"
    else:
        return formatted_value


@register.filter
def format_cpf(cpf: str | None) -> str:
    """Formata um número de CPF (XXX.XXX.XXX-XX)."""
    if not cpf:
        return ""
    try:
        cpf_clean = "".join(filter(str.isdigit, str(cpf)))
        if len(cpf_clean) != CPF_LENGTH:
            return str(cpf)
    except (ValueError, TypeError):
        return str(cpf)
    else:
        return f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:11]}"


@register.filter
def brazilian_date(date_value: Any, format_str: str = "d/m/Y") -> str:  # noqa: ANN401
    """Formata um objeto de data para o padrão brasileiro (dd/mm/YYYY)."""
    if not date_value:
        return ""
    try:
        if hasattr(date_value, "strftime"):
            formatted_date = date_value.strftime(
                format_str.replace("d", "%d").replace("m", "%m").replace("Y", "%Y"),
            )
        else:
            return str(date_value)
    except (ValueError, TypeError, AttributeError):
        return str(date_value)
    else:
        return formatted_date


@register.filter
def format_percentage(value: Any, decimal_places: int = 2) -> str:  # noqa: ANN401
    """Formata um valor numérico como uma porcentagem."""
    if value is None or value == "":
        return "0%"
    try:
        if isinstance(value, str):
            value = float(value.replace("%", "").replace(",", "."))
        formatted_value = f"{float(value):.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "0%"
    else:
        return formatted_value


@register.filter
def add_class(field: BoundField, css_class: str) -> SafeString | str:
    """Adiciona uma classe CSS a um campo de formulário do Django."""
    try:
        # Cria uma cópia dos atributos para não modificar o widget original.
        attrs = field.field.widget.attrs.copy()
        existing_class = attrs.get("class", "")
        attrs["class"] = f"{existing_class} {css_class}".strip()
        return field.as_widget(attrs=attrs)  # pyright: ignore [reportArgumentType]
    except (AttributeError, TypeError):
        # Retorna o campo como string em caso de erro inesperado.
        return str(field)


@register.filter
def get_attribute(obj: Any, attr_path: str) -> Any:  # noqa: ANN401
    """Acessa atributos aninhados de um objeto usando notação de ponto."""
    try:
        value = obj
        for attr in attr_path.split("."):
            value = value.get(attr) if hasattr(value, "get") and callable(value.get) else getattr(value, attr, None)
            if value is None:
                return None
    except (AttributeError, TypeError):
        return None
    else:
        return value


@register.filter
def multiply(value: Any, arg: Any) -> float:  # noqa: ANN401
    """Multiplica dois valores."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0.0


@register.filter
def divide(value: Any, arg: Any) -> float:  # noqa: ANN401
    """Divide dois valores, com segurança contra divisão por zero."""
    try:
        divisor = float(arg)
        if divisor == 0:
            return 0.0
        return float(value) / divisor
    except (ValueError, TypeError):
        return 0.0


@register.filter
def format_decimal(value: Any, decimal_places: int = 2) -> str:  # noqa: ANN401
    """Formata um número decimal com vírgula como separador."""
    if value is None or value == "":
        return "0,00"
    try:
        if isinstance(value, str):
            value = float(value.replace(",", "."))
        formatted_value = f"{float(value):.{decimal_places}f}".replace(".", ",")
    except (ValueError, TypeError):
        return "0,00"
    else:
        return formatted_value


@register.filter
def replace_url_id(url: str | None, object_id: Any) -> str | None:  # noqa: ANN401
    """Substitui um placeholder {id} em uma URL pelo ID de um objeto."""
    if not url or object_id is None:
        return url
    try:
        return url.replace("{id}", str(object_id))
    except (ValueError, TypeError, AttributeError):
        return url


@register.filter
def lookup(dictionary: dict[Any, Any], key: Any) -> Any:  # noqa: ANN401
    """Acessa um valor em um dicionário de forma segura."""
    return dictionary.get(key) if isinstance(dictionary, dict) else None
