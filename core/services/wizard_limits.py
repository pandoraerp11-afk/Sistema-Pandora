from __future__ import annotations

"""Limites centralizados do Wizard de Tenant.
Altera apenas locais onde antes havia números inline; não muda regras de negócio (apenas consolida)."""

# Máximo de registros processados em listas JSON
MAX_ADDITIONAL_ADDRESSES = 50
MAX_ADMINS = 50
MAX_CONTACTS = 100
MAX_SOCIALS = 50

__all__ = ["MAX_ADDITIONAL_ADDRESSES", "MAX_ADMINS", "MAX_CONTACTS", "MAX_SOCIALS"]
