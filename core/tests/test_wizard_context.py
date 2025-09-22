"""Testes para a classe WizardContext."""

from typing import Any

import pytest

from core.services.wizard_context import WizardContext


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        # Casos de fallback (quando não há dados suficientes em 'pj' ou 'pf')
        ({"step_1": {"pj": {}, "pf": {}, "main": {"tipo_pessoa": "PJ"}}}, "PJ"),
        ({"step_1": {"pj": {}, "pf": {}, "main": {"tipo_pessoa": "PF"}}}, "PF"),
        # Casos de detecção por dados significativos
        ({"step_1": {"pj": {"tipo_pessoa": "PJ", "cnpj": "123"}}}, "PJ"),
        ({"step_1": {"pf": {"tipo_pessoa": "PF", "cpf": "456"}}}, "PF"),
        # Casos onde a detecção deve falhar (dados insuficientes)
        ({"step_1": {"pj": {"tipo_pessoa": "PJ"}}}, None),
        ({"step_1": {"pf": {"tipo_pessoa": "PF"}}}, None),
        # Casos vazios
        ({"step_1": {"pj": {}, "pf": {}, "main": {}}}, None),
        ({}, None),
    ],
)
def test_detect_tipo_pessoa(payload: dict[str, Any], expected: str | None) -> None:
    """Testa a detecção do tipo de pessoa com base no payload."""
    ctx = WizardContext(raw=payload, is_editing=False, editing_tenant=None)
    assert ctx.detect_tipo_pessoa() == expected  # noqa: S101
