import decimal
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Tenant
from cotacoes.models import (
    Cotacao,
    CotacaoItem,
    PropostaFornecedor,
    PropostaFornecedorItem,
)
from fornecedores.models import Fornecedor, FornecedorPJ
from portal_fornecedor.models import AcessoFornecedor

User = get_user_model()


class InlineUpdatePortalTest(TestCase):
    def setUp(self):
        """Cria tenant, fornecedor (homologado + portal ativo), cotação e proposta base."""
        self.client = Client()
        self.user = User.objects.create_user(username="forn", password="x")
        self.tenant = Tenant.objects.create(name="Tenant T", subdomain="tenant-t")
        self.fornecedor = Fornecedor.objects.create(tenant=self.tenant)
        FornecedorPJ.objects.create(
            fornecedor=self.fornecedor, razao_social="FornX RS", nome_fantasia="FornX", cnpj="12.345.678/0001-90"
        )
        # Ativar condições para que o fornecedor possa enviar/editar propostas
        self.fornecedor.status_homologacao = "aprovado"
        self.fornecedor.portal_ativo = True
        self.fornecedor.save(update_fields=["status_homologacao", "portal_ativo"])
        AcessoFornecedor.objects.create(fornecedor=self.fornecedor, usuario=self.user, ativo=True)
        self.cotacao = Cotacao.objects.create(
            tenant=self.tenant,
            codigo="COT1",
            titulo="Teste",
            descricao="Desc",
            status="aberta",
            prazo_proposta=date.today() + timedelta(days=7),
            criado_por=self.user,
        )
        self.item = CotacaoItem.objects.create(
            cotacao=self.cotacao, descricao="Item A", quantidade=decimal.Decimal("2"), unidade="UN", ordem=1
        )
        self.proposta = PropostaFornecedor.objects.create(
            cotacao=self.cotacao,
            fornecedor=self.fornecedor,
            usuario=self.user,
            validade_proposta=date.today() + timedelta(days=10),
            prazo_entrega_geral=5,
            condicoes_pagamento="30D",
        )

    def test_inline_update_cria_item(self):
        self.client.login(username="forn", password="x")
        url = reverse("cotacoes:portal-proposta-item-inline-update", args=[self.proposta.id, self.item.id])
        resp = self.client.post(url, {"preco_unitario": "10,50", "prazo_entrega_dias": "7"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(PropostaFornecedorItem.objects.filter(proposta=self.proposta, item_cotacao=self.item).exists())

    def test_rate_limit(self):
        self.client.login(username="forn", password="x")
        url = reverse("cotacoes:portal-proposta-item-inline-update", args=[self.proposta.id, self.item.id])
        for _ in range(21):
            resp = self.client.post(url, {"preco_unitario": "1.00"})
        self.assertEqual(resp.status_code, 429)
