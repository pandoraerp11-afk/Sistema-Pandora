"""Fixtures específicos dos testes de portal_cliente.

Limpa o cache automaticamente entre testes para impedir vazamento de chaves de
throttle que poderiam causar 429 prematuros.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache_between_tests() -> None:  # pragma: no cover - infra de teste
    """Limpa cache entre testes (sem teardown)."""
    cache.clear()
