from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["normalize_enabled_modules", "dedupe_preserve_order", "parse_socials_json"]


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def normalize_enabled_modules(value: Any) -> list[str]:
    """Normaliza lista heterogênea de módulos (lista, json, csv, set, dict legado)."""
    modules: list[str] = []
    if not value:
        return modules
    try:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        modules.extend(str(parsed_v).strip() for parsed_v in parsed if parsed_v)
                except Exception:  # noqa: BLE001
                    # fallback csv
                    modules.extend(v.strip() for v in stripped.split(",") if v.strip())
            else:
                modules.extend(v.strip() for v in stripped.split(",") if v.strip())
        elif isinstance(value, dict):
            # Tentar chaves conhecidas
            for key in ("modules", "legacy", "values", "items"):
                val = value.get(key)
                if isinstance(val, (list, tuple, set)):
                    modules.extend(str(v).strip() for v in val if v)
                    break
        elif isinstance(value, (list, tuple, set)):
            modules.extend(str(v).strip() for v in value if v)
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao normalizar enabled_modules: %s", e)
    return sorted(dedupe_preserve_order(modules))


def parse_socials_json(raw: str | None) -> dict[str, str]:
    """Interpreta lista JSON de {'nome','link'} para dict nome->link.
    Ignora entradas inválidas, última ocorrência vence."""
    if not raw:
        return {}
    raw = raw.strip()
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return {}
        result: dict[str, str] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            nome = (item.get("nome") or "").strip()
            link = (item.get("link") or "").strip()
            if nome and link:
                result[nome] = link
        return result
    except Exception as e:  # noqa: BLE001
        logger.warning("socials_json inválido: %s", e)
        return {}
