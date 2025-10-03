"""Testes de atualização inline de itens de proposta no portal do fornecedor.

Refatorado para estilo pytest (asserts simples) e uso de datetimes timezone-aware
para eliminar warnings de naive datetime.
"""

import decimal
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Tenant
from cotacoes.models import Cotacao, CotacaoItem, PropostaFornecedor, PropostaFornecedorItem
from fornecedores.models import Fornecedor, FornecedorPJ
from portal_fornecedor.models import AcessoFornecedor

User = get_user_model()


class InlineUpdatePortalTest(TestCase):
    """Cenários de atualização inline de itens de proposta com validação de rate limit."""

    def setUp(self) -> None:
        """Cria tenant, fornecedor homologado/portal ativo, cotação, item e proposta base."""
        self.client = Client()
        password = os.environ.get("TEST_PASSWORD", "x")
        self.user = User.objects.create_user(username="forn", password=password)
        self.tenant = Tenant.objects.create(name="Tenant T", subdomain="tenant-t")
        self.fornecedor = Fornecedor.objects.create(tenant=self.tenant)
        FornecedorPJ.objects.create(
            fornecedor=self.fornecedor,
            razao_social="FornX RS",
            nome_fantasia="FornX",
            cnpj="12.345.678/0001-90",
        )
        # Ativar condições para que o fornecedor possa enviar/editar propostas
        self.fornecedor.status_homologacao = "aprovado"
        self.fornecedor.portal_ativo = True
        self.fornecedor.save(update_fields=["status_homologacao", "portal_ativo"])
        AcessoFornecedor.objects.create(fornecedor=self.fornecedor, usuario=self.user, ativo=True)
        # prazo_proposta é DateTimeField (timezone-aware). Evita criar naive datetime usando timezone.now().
        self.cotacao = Cotacao.objects.create(
            tenant=self.tenant,
            codigo="COT1",
            titulo="Teste",
            descricao="Desc",
            status="aberta",
            prazo_proposta=timezone.now() + timedelta(days=7),
            criado_por=self.user,
        )
        self.item = CotacaoItem.objects.create(
            cotacao=self.cotacao,
            descricao="Item A",
            quantidade=decimal.Decimal(2),
            unidade="UN",
            ordem=1,
        )
        self.proposta = PropostaFornecedor.objects.create(
            cotacao=self.cotacao,
            fornecedor=self.fornecedor,
            usuario=self.user,
            validade_proposta=(timezone.now() + timedelta(days=10)).date(),
            prazo_entrega_geral=5,
            condicoes_pagamento="30D",
        )

    def test_inline_update_cria_item(self) -> None:
        """Verifica criação de item de proposta via endpoint inline update."""
        password = os.environ.get("TEST_PASSWORD", "x")
        self.client.login(username="forn", password=password)
        url = reverse("cotacoes:portal-proposta-item-inline-update", args=[self.proposta.id, self.item.id])
        resp = self.client.post(url, {"preco_unitario": "10,50", "prazo_entrega_dias": "7"})
        assert resp.status_code == 200
        assert PropostaFornecedorItem.objects.filter(
            proposta=self.proposta,
            item_cotacao=self.item,
        ).exists()

    def test_rate_limit(self) -> None:
        """Aplica múltiplas requisições para atingir limite e validar retorno 429."""
        password = os.environ.get("TEST_PASSWORD", "x")
        self.client.login(username="forn", password=password)
        url = reverse("cotacoes:portal-proposta-item-inline-update", args=[self.proposta.id, self.item.id])
        for _ in range(21):
            resp = self.client.post(url, {"preco_unitario": "1.00"})
        assert resp.status_code == 429
