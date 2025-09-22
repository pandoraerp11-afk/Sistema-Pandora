import re
from collections.abc import Iterable

SUBDOMAIN_REGEX = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
RESERVED_SUBDOMAINS = {"www", "admin", "static", "media", "api"}


def normalize_subdomain(value: str | None) -> str:
    return (value or "").strip().lower()


def is_valid_subdomain_format(subdomain: str) -> bool:
    return bool(SUBDOMAIN_REGEX.match(subdomain))


def is_reserved_subdomain(subdomain: str, extra_reserved: Iterable[str] | None = None) -> bool:
    if not subdomain:
        return False
    base = RESERVED_SUBDOMAINS
    if extra_reserved:
        base = base | set(extra_reserved)
    return subdomain in base


def validate_subdomain(subdomain: str, existing_query) -> tuple[bool, str | None]:
    """Valida subdomínio retornando (ok, mensagem_erro).
    existing_query deve ser um queryset de Tenants filtrado por subdomain.
    """
    if not subdomain:
        return False, "Subdomínio obrigatório."
    if not is_valid_subdomain_format(subdomain):
        return False, "Formato inválido."
    if is_reserved_subdomain(subdomain):
        return False, "Subdomínio reservado."
    if existing_query.exists():
        return False, "Subdomínio já em uso."
    return True, None
