"""Verifica se constantes de subdomínio estão exportadas nas settings.

Sincronização de constantes de subdomínio.
Compat de import legacy removida (não era usada).
"""

from __future__ import annotations

import re

import pytest
from django.conf import settings


@pytest.mark.parametrize("name", ["SUBDOMAIN_MIN_LENGTH", "SUBDOMAIN_MAX_LENGTH", "SUBDOMAIN_REGEX"])
def test_constants_exported(name: str) -> None:
    """Cada constante de subdomínio deve estar em settings (contrato de compat)."""
    assert hasattr(settings, name), f"Constante ausente em settings: {name}"


def test_subdomain_limits_match_regex() -> None:
    """Valida coerência entre MIN/MAX e o padrão do regex compartilhado."""
    regex = settings.SUBDOMAIN_REGEX
    pattern = regex.pattern if isinstance(regex, re.Pattern) else str(regex)
    max_subdomain_length = 63  # constante local usada para comparação
    assert settings.SUBDOMAIN_MIN_LENGTH == 1, "SUBDOMAIN_MIN_LENGTH divergente (esperado 1)"
    assert max_subdomain_length == settings.SUBDOMAIN_MAX_LENGTH, "SUBDOMAIN_MAX_LENGTH divergente (esperado 63)"
    assert "{0,61}" in pattern or "{0,61}" in pattern.replace("\\", ""), "Regex não contém intervalo {0,61}"


# Fim do arquivo: import legacy removido.
