"""Módulo para o wrapper de contexto do wizard."""

from __future__ import annotations

from collections.abc import KeysView
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.models import Tenant


@dataclass
class WizardContext:
    """Wrapper leve para dados do wizard.

    Não altera regras de negócio: apenas oferece acesso estruturado.
    """

    raw: dict[str, Any]
    is_editing: bool
    editing_tenant: Tenant | None

    @property
    def tipo_pessoa(self) -> str:
        """Detecta o tipo de pessoa (PJ ou PF) a partir dos dados do wizard."""
        detected = self.detect_tipo_pessoa()
        if detected:
            return detected
        # Fallback para o tenant em edição, se houver
        if self.is_editing and self.editing_tenant:
            return self.editing_tenant.tipo_pessoa
        return "PJ"  # Default fallback

    def get_step_data(self, step_number: int, form_key: str = "main") -> dict[str, Any]:
        """Obtém os dados de um formulário específico dentro de um step."""
        step_content = self.raw.get(f"step_{step_number}", {})
        if form_key:
            return step_content.get(form_key, {})
        return step_content

    def detect_tipo_pessoa(self) -> str | None:
        """Tenta detectar o tipo de pessoa a partir dos dados brutos do wizard."""
        step_1 = self.get_step_data(1, form_key="")
        pj_data = step_1.get("pj", {})
        pf_data = step_1.get("pf", {})

        # Verifica se há dados significativos que indiquem o tipo
        is_pj = pj_data.get("tipo_pessoa") == "PJ" and (pj_data.get("cnpj") or len(pj_data) > 1)
        is_pf = pf_data.get("tipo_pessoa") == "PF" and (pf_data.get("cpf") or len(pf_data) > 1)

        if is_pj:
            return "PJ"
        if is_pf:
            return "PF"

        # Fallback para o campo 'tipo_pessoa' no bloco 'main'
        main_data = step_1.get("main", {})
        if (tp := main_data.get("tipo_pessoa")) in ("PJ", "PF"):
            return tp

        return None

    def keys(self) -> KeysView[str]:  # conveniência
        """Retorna as chaves dos dados brutos."""
        return self.raw.keys()

    def __contains__(self, item: str) -> bool:  # passthrough
        """Verifica se um item existe nos dados brutos."""
        return item in self.raw

    def as_dict(self) -> dict[str, Any]:
        """Retorna os dados brutos como um dicionário."""
        return self.raw
