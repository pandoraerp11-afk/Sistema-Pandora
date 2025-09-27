"""Compat layer para testes migrados que ainda faziam import star de core/tests.

Objetivo: permitir remoção incremental desses imports sem quebrar a suíte.
Evite adicionar novos símbolos aqui. Idealmente os `from tests.core.legacy_imports import *`
serão removidos futuramente.
"""

# Exemplo de alias / utilitários mínimos (se necessário no futuro)
# No momento deixamos vazio propositalmente; o import * apenas não deve falhar.

__all__: list[str] = []
