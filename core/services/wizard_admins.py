"""Utilidades para processamento de administradores do Wizard de Tenants.

Fornece parsing resiliente do bloco "step_6" (admins_json e senha em massa)
e geração de senhas seguras para novos administradores criados pelo wizard.
"""

from __future__ import annotations

import json
import logging
import secrets
import string
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["parse_admins_payload", "generate_secure_password"]


def _extract_raw_admins(step_data: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    admins_json_local: str | None = None
    bulk_pwd: str | None = None
    if "admins_json" in step_data:
        admins_json_local = step_data.get("admins_json")
        bulk_pwd = step_data.get("bulk_admin_password")
    elif isinstance(step_data.get("main"), dict):
        main = step_data["main"]
        admins_json_local = main.get("admins_json")
        bulk_pwd = main.get("bulk_admin_password")

    result: list[dict[str, Any]] = []
    if admins_json_local:
        try:
            parsed = json.loads(admins_json_local)
            if isinstance(parsed, list):
                result = [a for a in parsed if isinstance(a, dict)]
        except Exception as e:  # noqa: BLE001
            logger.warning("admins_json inválido: %s", e)
    else:
        base = step_data.get("main", {}) if "main" in step_data else step_data
        if any(base.get(k) for k in ("admin_email", "email")):
            result.append(base)
    return result[:50], (bulk_pwd or None)


def _normalize_admin_item(raw: dict[str, Any]) -> dict[str, Any]:
    item = dict(raw)
    mapping = {
        "admin_email": "email",
        "admin_nome": "nome",
        "admin_senha": "senha",
        "admin_confirmar_senha": "confirm_senha",
        "admin_telefone": "telefone",
        "admin_usuario": "username",
    }
    for src, dst in mapping.items():
        if dst not in item and src in item:
            item[dst] = item.get(src)
    for k in ("email", "nome", "telefone", "username"):
        if k in item and isinstance(item[k], str):
            item[k] = item[k].strip()
    return item


def generate_secure_password(length: int = 12) -> str:
    """Gera uma senha aleatória forte com letras, dígitos e símbolos.

    A senha inclui letras maiúsculas/minúsculas, dígitos e um conjunto curto de
    símbolos seguros para facilitar digitação mas manter entropia.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def parse_admins_payload(step_6_data: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Extrai admins_json e bulk_admin_password do bloco do Step 6.

    Retorna (admins_normalizados, bulk_password).
    Aceita tanto dados na raiz quanto em main e tolera payloads simples.
    """
    raw_admins, bulk_password = _extract_raw_admins(step_6_data)
    normalized = [_normalize_admin_item(a) for a in raw_admins if isinstance(a, dict)]
    return normalized, bulk_password
