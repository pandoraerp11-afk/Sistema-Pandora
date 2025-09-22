from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

WIZARD_DEBUG_FLAG_NAME = "WIZARD_DEBUG"


def is_wizard_debug_enabled() -> bool:
    return bool(getattr(settings, WIZARD_DEBUG_FLAG_NAME, False))


class WizardDebugFilter(logging.Filter):
    name = "wizard_debug_filter"

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover (simples)
        if record.levelno >= logging.INFO:
            return True
        # só permite DEBUG se flag ligada
        return is_wizard_debug_enabled()


def install_wizard_logging_filter():
    root = logging.getLogger("core.wizard")  # namespace opcional
    # Evitar múltiplas instalações
    has = any(isinstance(f, WizardDebugFilter) for f in root.filters)
    if not has:
        root.addFilter(WizardDebugFilter())


__all__ = ["is_wizard_debug_enabled", "WIZARD_DEBUG_FLAG_NAME", "install_wizard_logging_filter"]
