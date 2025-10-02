"""Utilitário de correção de código (stub de implementação segura)."""

from __future__ import annotations

from pathlib import Path

from .base import BaseGenerator


class CodeFixer(BaseGenerator):
    """Aplica correções automáticas simples (implementação mínima).

    Esta classe existe principalmente para permitir evolução incremental sem
    bloquear instância por causa do método abstrato `generate`.
    """

    def generate(self) -> None:
        """No-op: geração não implementada neste estágio."""

    def apply_fix(self, file_path: str, _original_code: str, suggested_fix: str) -> bool:
        """Tenta aplicar uma correção.

        Convencão mínima: se a sugestão começar com 'REPLACE_ALL:' substitui
        todo o arquivo; do contrário retorna False sem efeitos colaterais.
        """
        if not suggested_fix:
            return False
        marker = "REPLACE_ALL:"
        if suggested_fix.startswith(marker):
            new_content = suggested_fix[len(marker) :]
            Path(file_path).write_text(new_content, encoding="utf-8")
            return True
        return False

    def fix_unused_imports(self, _file_path: str, content: str) -> str:
        """Stub: retorna conteúdo inalterado."""
        return content

    def format_code(self, _file_path: str, content: str) -> str:
        """Stub: retorna conteúdo inalterado."""
        return content
