"""Filtros utilitários para templates do núcleo.

Inclui:
* Resolução de URL home de módulos.
* Nome de exibição legível de módulo.
* Normalização visual de nomes totalmente em maiúsculas (sem alterar o banco).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import template
from django.urls import NoReverseMatch, reverse

if TYPE_CHECKING:  # pragma: no cover - apenas para tipagem
    from collections.abc import Mapping

SIGLA_MAX_LEN = 3  # Limite para considerar token como sigla curta

register = template.Library()


@register.filter
def get_module_home_url(app_name: str | None) -> str:
    """Retorna URL "home" de um módulo pelo nome do app.

    Ordem de resolução:
    1. Mapeamento explícito.
    2. Padrão <app>:home.
    3. Fallbacks específicos para core.
    4. Dashboard.
    5. "#" se nada encontrado.
    """
    if not app_name:
        return "#"

    home_url_mapping: Mapping[str, str] = {
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
        if app_name == "core":
            for fallback in ("core:tenant_list", "core:core_home", "core:tenant_select"):
                try:
                    return reverse(fallback)
                except NoReverseMatch:
                    continue
        try:
            return reverse("dashboard")
        except NoReverseMatch:
            return "#"


@register.filter
def get_module_display_name(app_name: str | None) -> str:
    """Retorna nome de exibição amigável para um app/módulo."""
    if not app_name:
        return "Sistema"

    display_names: Mapping[str, str] = {
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


@register.filter(name="normalize_upper_name")
def normalize_upper_name(value: str | None) -> str | None:
    """Normaliza visualmente nomes totalmente em MAIÚSCULAS.

    Mantém dados originais; apenas apresentação. Preserva siglas de até 3 caracteres
    e tokens conhecidos. Se já existir minúscula, retorna o valor original.
    """
    if not value:
        return value
    letters = [c for c in value if c.isalpha()]
    if not letters or any(c.islower() for c in letters):
        return value
    upper_tokens = {"LTDA", "ME", "MEI", "EPP", "S/A", "SA", "CPF", "CNPJ"}
    reference = {t.replace(".", "") for t in upper_tokens}
    parts = value.split()
    out: list[str] = []
    for token in parts:
        cmp_token = token.replace(".", "").upper()
        if cmp_token in reference or (len(token) <= SIGLA_MAX_LEN and token.isupper()):
            out.append(token.upper())
        else:
            out.append(token.capitalize())
    return " ".join(out)
