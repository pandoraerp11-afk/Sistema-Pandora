import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from core.models import Tenant
from cotacoes.models import Cotacao, CotacaoItem, PropostaFornecedor
from fornecedores.models import Fornecedor
from portal_fornecedor.models import AcessoFornecedor

User = get_user_model()


@pytest.mark.django_db
def test_portal_fornecedor_dashboard(client):
    tenant = Tenant.objects.create(nome="T1", slug="t1")
    user = User.objects.create_user(username="forn1", password="pass")
    forn = Fornecedor.objects.create(tenant=tenant, nome_fantasia="Forn X", razao_social="RS", cnpj="12345678000100")
    AcessoFornecedor.objects.create(fornecedor=forn, usuario=user, ativo=True)
    client.force_login(user)
    url = reverse("cotacoes:portal-dashboard")
    resp = client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_criar_proposta_fluxo_basico(client):
    tenant = Tenant.objects.create(nome="T1", slug="t1")
    user = User.objects.create_user(username="forn2", password="pass")
    forn = Fornecedor.objects.create(tenant=tenant, nome_fantasia="Forn Y", razao_social="RS", cnpj="22345678000100")
    AcessoFornecedor.objects.create(fornecedor=forn, usuario=user, ativo=True)
    client.force_login(user)
    cot = Cotacao.objects.create(
        tenant=tenant,
        codigo="COT001",
        titulo="Teste",
        criado_por=user,
        prazo_proposta=timezone.now() + timezone.timedelta(days=2),
    )
    CotacaoItem.objects.create(cotacao=cot, descricao="Item A", quantidade=5, unidade="UN")
    create_url = reverse("cotacoes:portal-criar-proposta", args=[cot.id])
    resp = client.post(
        create_url,
        {
            "validade_proposta": (timezone.now() + timezone.timedelta(days=5)).date(),
            "prazo_entrega_geral": 10,
        },
    )
    # Redireciona para edição
    assert resp.status_code in (302, 303)
    assert PropostaFornecedor.objects.filter(cotacao=cot, fornecedor=forn).exists()


@pytest.mark.django_db
def test_fornecedor_sem_acesso_retorna_404(client):
    Tenant.objects.create(nome="T1", slug="t1")
    user = User.objects.create_user(username="x", password="pass")
    client.force_login(user)
    url = reverse("cotacoes:portal-dashboard")
    resp = client.get(url)
    assert resp.status_code == 404
