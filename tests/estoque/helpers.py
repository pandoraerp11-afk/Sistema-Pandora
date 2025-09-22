# Helper utilitário para testes de estoque centralizando criação de usuário + tenant + dados básicos
from django.contrib.auth import get_user_model

from core.models import Tenant, TenantUser
from estoque.models import Deposito, EstoqueSaldo
from produtos.models import Categoria, Produto


def bootstrap_user_tenant(client, *, username="tester", password="pass"):
    """Cria usuário, tenant vinculado e faz login atribuindo tenant_id na sessão.
    Retorna (user, tenant, client)
    """
    User = get_user_model()
    user = User.objects.create_user(username=username, password=password)
    tenant = Tenant.objects.create(nome=f"Empresa {username}", slug=f"empresa-{username}")
    TenantUser.objects.create(user=user, tenant=tenant)
    client.login(username=username, password=password)
    # garantir tenant na sessão
    sess = client.session
    sess["tenant_id"] = tenant.id
    sess.save()
    return user, tenant, client


def create_basic_inventory(produto_nome="Produto X", deposito_codigo="DEP1", qtd=50, reservado=5):
    categoria = Categoria.objects.create(nome="Geral")
    produto = Produto.objects.create(nome=produto_nome, categoria=categoria)
    deposito = Deposito.objects.create(codigo=deposito_codigo, nome="Principal")
    saldo = EstoqueSaldo.objects.create(produto=produto, deposito=deposito, quantidade=qtd, reservado=reservado)
    return categoria, produto, deposito, saldo
