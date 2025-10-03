"""Testes focados em normalização de aliases de módulos do wizard.

Cobre:
- Colapso de múltiplos aliases (agendamento/agendamentos) para "agenda" sem duplicar;
- Preservação de ordem relativa para módulos diferentes;
- Pipeline combinada (normalize_enabled_modules -> normalize_module_aliases) sem duplicar;
- Casos vazios / None;
- Idempotência.
"""

from __future__ import annotations

import pytest

from core.services.wizard_normalizers import (
    normalize_enabled_modules,
    normalize_module_aliases,
)


def test_alias_collapse_all_variants() -> None:
    """Todas as variantes relacionadas a agenda colapsam em uma única entrada."""
    raw = ["agenda", "agendamentos", "agendamento"]
    result = normalize_module_aliases(raw)
    assert result == ["agenda"], "Deve restar somente 'agenda'"


def test_alias_with_noise_and_preserve_order() -> None:
    """Mantém ordem relativa dos módulos distintos após colapso de aliases."""
    raw = [
        "clientes",
        "agendamentos",  # -> agenda
        "financeiro",
        "agendamento",  # -> agenda (duplicado após mapeamento)
        "agenda",  # já destino
        "estoque",
    ]
    result = normalize_module_aliases(raw)
    assert result == ["clientes", "agenda", "financeiro", "estoque"]


def test_pipeline_no_duplicate_after_double_normalization() -> None:
    """Pipeline (enabled_modules -> aliases) não deixa duplicados residuais."""
    csv = "agenda,agendamentos,agendamento,clientes"
    stage1 = normalize_enabled_modules(csv)
    # stage1 alfabeticamente: ['agenda','agendamento','agendamentos','clientes']
    final = normalize_module_aliases(stage1)
    assert final == ["agenda", "clientes"]


@pytest.mark.parametrize("value", [None, [], (), set()])
def test_empty_and_none_inputs(value: list[str] | tuple[str, ...] | set[str] | None) -> None:
    """Entradas vazias ou None retornam lista vazia."""
    assert normalize_module_aliases(value) == []


def test_idempotency() -> None:
    """Aplicar a função novamente não altera o resultado (idempotente)."""
    raw = ["agendamentos", "agendamento", "agenda", "agenda"]
    once = normalize_module_aliases(raw)
    twice = normalize_module_aliases(once)
    assert once == ["agenda"]
    assert twice == once
