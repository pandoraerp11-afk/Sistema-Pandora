"""Utilitários e funções auxiliares para a aplicação core."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.utils.text import slugify

if TYPE_CHECKING:
    from django.http import HttpRequest

from .models import Tenant

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTES
# ==============================================================================

CPF_LENGTH = 11
CNPJ_LENGTH = 14
PHONE_LANDLINE_LENGTH = 10
PHONE_MOBILE_LENGTH = 11
CEP_LENGTH = 8

VALID_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "webp", "svg"}
VALID_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"}


# ==============================================================================
# FUNÇÕES DE FORMATAÇÃO E HELPERS
# ==============================================================================


def normalize_text(text: str | None) -> str:
    """Normaliza um texto removendo acentos e caracteres especiais."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text))
    normalized = "".join([c for c in normalized if not unicodedata.combining(c)])
    normalized = re.sub(r"[^\w\s-]", "", normalized).strip()  # Mantém hifens
    return normalized.lower()


def format_cnpj(cnpj: str | None) -> str:
    """Formata um CNPJ adicionando pontuação."""
    if not cnpj:
        return ""
    cnpj_clean = re.sub(r"\D", "", str(cnpj))
    if len(cnpj_clean) != CNPJ_LENGTH:
        return str(cnpj)
    return f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:]}"


def format_cpf(cpf: str | None) -> str:
    """Formata um CPF adicionando pontuação."""
    if not cpf:
        return ""
    cpf_clean = re.sub(r"\D", "", str(cpf))
    if len(cpf_clean) != CPF_LENGTH:
        return str(cpf)
    return f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:]}"


def format_phone(phone: str | None) -> str:
    """Formata um número de telefone brasileiro."""
    if not phone:
        return ""
    phone_clean = re.sub(r"\D", "", str(phone))
    if len(phone_clean) == PHONE_MOBILE_LENGTH:
        return f"({phone_clean[:2]}) {phone_clean[2:7]}-{phone_clean[7:]}"
    if len(phone_clean) == PHONE_LANDLINE_LENGTH:
        return f"({phone_clean[:2]}) {phone_clean[2:6]}-{phone_clean[6:]}"

    return str(phone)


def format_cep(cep: str | None) -> str:
    """Formata um CEP adicionando pontuação."""
    if not cep:
        return ""
    cep_clean = re.sub(r"\D", "", str(cep))
    if len(cep_clean) != CEP_LENGTH:
        return str(cep)
    return f"{cep_clean[:5]}-{cep_clean[5:]}"


def decimal_to_str(value: Decimal | str | float | None, decimal_places: int = 2) -> str:
    """Converta um valor decimal para string formatada com vírgula."""
    if value is None:
        return ""
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except InvalidOperation:
            return str(value)
    return str(value.quantize(Decimal(10) ** -decimal_places)).replace(".", ",")


def str_to_decimal(value: str | Decimal | float | None) -> Decimal:
    """Converta uma string com vírgula para Decimal."""
    if not value:
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    value_str = str(value).replace(".", "").replace(",", ".")
    try:
        return Decimal(value_str)
    except InvalidOperation:
        return Decimal(0)


def format_date(date_obj: date | datetime | str | None, format_str: str = "%d/%m/%Y") -> str:
    """Formata um objeto date ou datetime para string."""
    if not date_obj:
        return ""
    if isinstance(date_obj, str):
        try:
            # Tenta converter de string ISO (YYYY-MM-DD) para objeto date
            parsed_date = datetime.strptime(date_obj, "%Y-%m-%d").date()  # noqa: DTZ007
            return parsed_date.strftime(format_str)
        except ValueError:
            # Se a string não estiver no formato esperado, retorne a string original.
            return date_obj
    try:
        return date_obj.strftime(format_str)
    except (ValueError, AttributeError):
        return str(date_obj)


def parse_date(date_str: str | date | datetime | None, format_str: str = "%d/%m/%Y") -> date | None:
    """Converta uma string de data para objeto date."""
    if not date_str:
        return None
    if isinstance(date_str, datetime):
        return date_str.date()
    if isinstance(date_str, date):
        return date_str
    try:
        return datetime.strptime(date_str, format_str).date()  # noqa: DTZ007
    except (ValueError, TypeError):
        return None


def get_file_extension(filename: str) -> str:
    """Obtém a extensão de um arquivo."""
    if not filename:
        return ""
    return Path(filename).suffix[1:].lower()


def is_valid_image_extension(filename: str) -> bool:
    """Verifica se a extensão do arquivo é de uma imagem válida."""
    return get_file_extension(filename) in VALID_IMAGE_EXTENSIONS


def is_valid_document_extension(filename: str) -> bool:
    """Verifica se a extensão do arquivo é de um documento válido."""
    return get_file_extension(filename) in VALID_DOCUMENT_EXTENSIONS


def generate_unique_filename(_instance: Any, filename: str) -> str:  # noqa: ANN401
    """Gera um nome de arquivo único adicionando um UUID."""
    path = Path(filename)
    name = path.stem
    ext = path.suffix
    unique_id = str(uuid.uuid4())[:8]
    return f"{slugify(name)}-{unique_id}{ext}"


def truncate_string(text: str | None, max_length: int = 100, suffix: str = "...") -> str:
    """Trunca uma string para um tamanho máximo."""
    if not text or len(text) <= max_length:
        return text or ""
    return text[: max_length - len(suffix)].strip() + suffix


def json_serialize(obj: Any) -> str:  # noqa: ANN401
    """Serializa um objeto para JSON de forma segura."""

    def default_handler(o: Any) -> float | str:  # noqa: ANN401
        if isinstance(o, Decimal | float):
            return float(o)
        if isinstance(o, datetime | date):
            return o.isoformat()
        if isinstance(o, uuid.UUID):
            return str(o)
        msg = f"Object of type {type(o).__name__} is not JSON serializable"
        raise TypeError(msg)

    return json.dumps(obj, default=default_handler)


def json_deserialize(json_str: str | None) -> dict[Any, Any] | list[Any]:
    """Deserializa uma string JSON para um objeto Python."""
    if not json_str:
        return {}
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def format_json_text(raw: str | None) -> str:
    """Formata uma string JSON com indentação de 2 espaços.

    Regras:
    - Se a string for vazia ou None, retorna-a (vazia) diretamente.
    - Se não for JSON válido, retorna o texto original (comportamento leniente
      para manter expectativa dos testes legados).
    - Mantém ordem de inserção (Python 3.7+ garante ordem em dicts).
    """
    if raw is None or raw == "":  # preserva empty string
        return raw or ""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    try:
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):  # fallback extremamente defensivo
        return raw


# ==============================================================================
# FUNÇÕES ESSENCIAIS PARA O CORE (CORRIGIDAS E VALIDADAS)
# ==============================================================================


def get_client_ip(request: HttpRequest) -> str | None:
    """Obtém o endereço IP real do cliente a partir do request.

    Considera proxies (X-Forwarded-For).
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")


def _get_tenant_id_from_session(request: HttpRequest) -> int | None:
    """Obtém o ID do tenant da sessão ou dos cookies."""
    tenant_id = request.session.get("tenant_id")
    if tenant_id:
        return int(tenant_id)

    try:
        cookie_tid = request.COOKIES.get("current_tenant_id")
        if cookie_tid:
            tenant_id = int(cookie_tid)
            request.session["tenant_id"] = tenant_id
            return tenant_id
    except (AttributeError, TypeError, ValueError):
        logger.warning("Could not read a valid tenant_id from cookies.")

    return None


def _get_tenant_from_user_fallback(request: HttpRequest) -> int | None:
    """Tenta obter o tenant como fallback a partir do usuário autenticado."""
    try:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return None

        # Primeiro tenta via memberships explícitos
        if hasattr(user, "tenant_memberships"):
            tenants = list(user.tenant_memberships.values_list("tenant_id", flat=True)[:2])
            if len(tenants) == 1:
                return tenants[0]

        # Fallback adicional: propriedade user.tenant (camada de compatibilidade)
        if hasattr(user, "_legacy_single_tenant"):
            # Acesso intencional a membro privado para compatibilidade legada.
            single_tenant = user._legacy_single_tenant  # noqa: SLF001
            if single_tenant:
                return single_tenant.id
    except AttributeError:
        logger.warning("Error during tenant fallback for user %s.", getattr(request.user, "username", "Anonymous"))

    return None


def get_current_tenant(request: HttpRequest) -> Tenant | None:
    """Obtém o tenant (empresa) atual a partir da sessão do usuário.

    Este é o método principal e mais seguro para identificação do tenant.
    Utiliza um cache no objeto request para evitar múltiplas buscas no banco de dados.
    """
    if hasattr(request, "_cached_tenant"):
        return request._cached_tenant  # noqa: SLF001

    if not hasattr(request, "session"):
        # Em alguns contextos (como testes de API), a sessão pode não existir.
        # Inicializamos um dicionário vazio para evitar `AttributeError`.
        request.session = {}

    tenant_id = _get_tenant_id_from_session(request)
    if not tenant_id:
        tenant_id = _get_tenant_from_user_fallback(request)
        if tenant_id:
            request.session["tenant_id"] = tenant_id

    if not tenant_id:
        request._cached_tenant = None  # noqa: SLF001
        return None

    try:
        tenant = Tenant.objects.get(id=tenant_id, status="active")
    except Tenant.DoesNotExist:
        if "tenant_id" in request.session:
            del request.session["tenant_id"]
        request._cached_tenant = None  # noqa: SLF001
        return None
    else:
        request._cached_tenant = tenant  # noqa: SLF001
        return tenant
