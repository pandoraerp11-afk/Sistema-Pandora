"""Helpers de sessão para o Portal Cliente.

Centraliza lógica de garantir que a sessão contenha o `tenant_id` ativo
para evitar redirects intermediários (ex.: /core/tenant-select/) em fluxos
AJAX quando o usuário já possui uma ContaCliente ativa.
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable

    from django.http import HttpRequest

from .models import ContaCliente


def ensure_tenant_session(request: HttpRequest) -> None:
    """Garante que `tenant_id` esteja presente na sessão.

    Usa (na ordem):
      1. Lista `request.contas_cliente` se já preenchida pelo decorator.
      2. Consulta rápida (`values_list`) de contas ativas do usuário.
    Não sobrescreve um tenant_id já definido.
    """
    if "tenant_id" in request.session:
        return

    contas: Iterable[ContaCliente] | None = getattr(request, "contas_cliente", None)
    conta = None
    if contas:
        # contas_cliente pode ser lista lazy; pegamos o primeiro ativo
        for c in contas:  # pragma: no cover (loop trivial)
            if getattr(c, "ativo", False):
                conta = c
                break
    if conta is None:
        conta = (
            ContaCliente.objects.select_related("cliente")
            .filter(usuario=request.user, ativo=True)
            .only("cliente__tenant_id")
            .first()
        )
    if conta and getattr(conta.cliente, "tenant_id", None):
        request.session["tenant_id"] = conta.cliente.tenant_id
        # Alguns backends precisam de save explícito para marcar modificação
        with suppress(Exception):  # pragma: no cover - dependente backend
            request.session.save()
