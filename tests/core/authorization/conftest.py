import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Limpa o cache antes de cada teste de autorização para evitar efeitos de chave stale
    (especialmente em deduplicação de logs e métricas)."""
    cache.clear()
    yield
