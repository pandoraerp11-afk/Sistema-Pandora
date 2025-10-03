"""Teste focal para auto-bind de tenant via AcessoFornecedor no force_login.

Garante que o patch em Client.force_login (definido em conftest) popula session['tenant_id']
quando o usuário só possui AcessoFornecedor ativo e nenhum TenantUser.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model

from core.models import Tenant
from fornecedores.models import Fornecedor
from portal_fornecedor.models import AcessoFornecedor

User = get_user_model()


if TYPE_CHECKING:
    from django.test.client import Client


@pytest.mark.django_db
def test_force_login_popula_tenant_via_acesso_fornecedor(client: Client) -> None:
    """Auto-bind de tenant via AcessoFornecedor quando não há TenantUser.

    Cenário:
    - Usuário sem vínculos TenantUser
    - Existe AcessoFornecedor ativo
    - force_login deve acionar lógica de _auto_bind_single_tenant em conftest e popular session['tenant_id'].
    """
    tenant = Tenant.objects.create(nome="T-Forn", slug="tforn")
    forn = Fornecedor.objects.create(
        tenant=tenant,
        nome_fantasia="Fornecedor Teste",
        razao_social="Fornecedor Teste LTDA",
        cnpj="12345678000199",
    )
    pwd = os.environ.get("TEST_PASSWORD", "pass")
    user = User.objects.create_user(username="usuario_forn", password=pwd)
    assert not user.tenant_memberships.exists()
    AcessoFornecedor.objects.create(fornecedor=forn, usuario=user, ativo=True)
    client.force_login(user)
    sess = client.session
    assert sess.get("tenant_id") == tenant.id, "tenant_id não foi populado via AcessoFornecedor ativo"
