"""Testes básicos de fluxo do módulo Clientes.

Cobrem:
- List e Detail (smoke)
- Wizard criação PF & PJ (passos mínimos)
- Delete
- Import CSV simples

Regras relaxadas intencionais: senhas hardcoded de teste são aceitáveis (não produção).
"""

import csv
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from clientes.models import Cliente, PessoaFisica, PessoaJuridica  # pyright: ignore[reportMissingImports]
from core.models import Tenant, TenantUser  # pyright: ignore[reportMissingImports]

User = get_user_model()


@pytest.mark.django_db
def test_clientes_list_and_detail_smoke() -> None:
    """Smoke: lista e detalhe devem responder 200 e conter nome PF."""
    user = User.objects.create_user(username="u1", password="x")  # noqa: S106 - senha de teste
    tenant = Tenant.objects.create(nome="T1", schema_name="t1")
    TenantUser.objects.create(user=user, tenant=tenant, is_tenant_admin=True)
    cli = Cliente.objects.create(tenant=tenant, tipo="PF", email="a@b.com")
    PessoaFisica.objects.create(cliente=cli, nome_completo="Fulano Teste", cpf="123.456.789-00")
    c = Client()
    c.login(username="u1", password="x")  # noqa: S106
    session = c.session
    session["tenant_id"] = tenant.id
    session.save()
    resp = c.get(reverse("clientes:clientes_list"))
    assert resp.status_code == 200, resp.content[:400]
    resp2 = c.get(reverse("clientes:clientes_detail", args=[cli.id]))
    assert resp2.status_code == 200
    assert b"Fulano Teste" in resp2.content


@pytest.mark.django_db
def test_clientes_wizard_create_pf() -> None:
    """Cria cliente PF via wizard percorrendo passos mínimos."""
    user = User.objects.create_user(username="wizpf", password="x")  # noqa: S106
    tenant = Tenant.objects.create(nome="TW1", schema_name="tw1")
    TenantUser.objects.create(user=user, tenant=tenant, is_tenant_admin=True)
    c = Client()
    c.login(username="wizpf", password="x")  # noqa: S106
    s = c.session
    s["tenant_id"] = tenant.id
    s.save()
    # Step 1 identificação PF
    # Step 1: formulários usam prefixos pf- / pj- e campo tipo_pessoa.
    # Enviamos tanto pf-name (campo real do form) quanto pf-nome_completo para futura compat.
    step1 = {
        "step": 1,
        "pf-tipo_pessoa": "PF",
        "pf-name": "Pessoa Wizard",
        "pf-nome_completo": "Pessoa Wizard",  # tolerado se form ignorar
        "pf-cpf": "111.222.333-44",
    }
    resp1 = c.post(reverse("clientes:clientes_create"), data=step1, follow=True)
    assert resp1.status_code in (200, 302)
    # Step 2 endereço
    # Step 2: prefixo main-
    step2 = {
        "step": 2,
        "main-cep": "12345-000",
        "main-logradouro": "Rua X",
        "main-numero": "10",
        "main-bairro": "Centro",
        "main-cidade": "Cidade",
        "main-uf": "SP",
    }
    resp2 = c.post(reverse("clientes:clientes_create"), data=step2, follow=True)
    assert resp2.status_code in (200, 302)
    # Step 3 contatos
    # Step 3: contatos principais via campos *contato_principal*
    step3 = {
        "step": 3,
        "main-email_contato_principal": "wizard@example.com",
        "main-telefone_contato_principal": "+5511999999999",
    }
    resp3 = c.post(reverse("clientes:clientes_create"), data=step3, follow=True)
    assert resp3.status_code in (200, 302)
    # Step 4 documentos (simula skip se permitido)
    step4 = {"step": 4, "_skip": "1"}
    resp4 = c.post(reverse("clientes:clientes_create"), data=step4, follow=True)
    assert resp4.status_code in (200, 302)
    # Step 5 confirmação: campo obrigatório 'confirmar_dados' com prefixo main-
    step5 = {"step": 5, "wizard_finish": 1, "main-confirmar_dados": "on"}
    resp5 = c.post(reverse("clientes:clientes_create"), data=step5, follow=True)
    assert resp5.status_code in (200, 302)
    assert Cliente.objects.filter(tenant=tenant, pessoafisica__nome_completo__icontains="Pessoa Wizard").exists()
    # Recupera cliente e verifica nome_display no detalhe
    cliente = Cliente.objects.get(pessoafisica__nome_completo__icontains="Pessoa Wizard", tenant=tenant)
    resp_detail = c.get(reverse("clientes:clientes_detail", args=[cliente.id]))
    assert b"Pessoa Wizard" in resp_detail.content


@pytest.mark.django_db
def test_clientes_wizard_create_pj_minimo() -> None:
    """Cria cliente PJ via wizard com dados essenciais."""
    user = User.objects.create_user(username="wizpj", password="x")  # noqa: S106
    tenant = Tenant.objects.create(nome="TW2", schema_name="tw2")
    TenantUser.objects.create(user=user, tenant=tenant, is_tenant_admin=True)
    c = Client()
    c.login(username="wizpj", password="x")  # noqa: S106
    s = c.session
    s["tenant_id"] = tenant.id
    s.save()
    # Step 1 identificação PJ
    step1 = {
        "step": 1,
        "pj-tipo_pessoa": "PJ",
        "pj-name": "Empresa XYZ LTDA",  # nome_fantasia/"name" exigido pelo form base
        "pj-razao_social": "Empresa XYZ LTDA",
        "pj-cnpj": "12.345.678/0001-99",
    }
    c.post(reverse("clientes:clientes_create"), data=step1)
    # Step 2 endereço
    c.post(
        reverse("clientes:clientes_create"),
        data={
            "step": 2,
            "main-cep": "22222-000",
            "main-logradouro": "Av Central",
            "main-numero": "100",
            "main-bairro": "Centro",
            "main-cidade": "Rio",
            "main-uf": "RJ",
        },
    )
    # Step 3 contatos
    c.post(
        reverse("clientes:clientes_create"),
        data={"step": 3, "main-email_contato_principal": "contato@xyz.com"},
    )
    # Step 4 skip docs
    c.post(reverse("clientes:clientes_create"), data={"step": 4, "_skip": 1})
    # Step 5 confirma
    c.post(
        reverse("clientes:clientes_create"),
        data={"step": 5, "wizard_finish": 1, "main-confirmar_dados": "on"},
    )
    assert Cliente.objects.filter(tenant=tenant, pessoajuridica__razao_social__icontains="Empresa XYZ").exists()


@pytest.mark.django_db
def test_clientes_delete_flow() -> None:
    """Exclui cliente PJ e valida remoção."""
    user = User.objects.create_user(username="deluser", password="x")  # noqa: S106
    tenant = Tenant.objects.create(nome="TD1", schema_name="td1")
    TenantUser.objects.create(user=user, tenant=tenant, is_tenant_admin=True)
    cli = Cliente.objects.create(tenant=tenant, tipo="PJ")
    PessoaJuridica.objects.create(cliente=cli, razao_social="Del Co", cnpj="00.000.000/0001-00")
    c = Client()
    c.login(username="deluser", password="x")  # noqa: S106
    sess = c.session
    sess["tenant_id"] = tenant.id
    sess.save()
    resp = c.post(reverse("clientes:clientes_delete", args=[cli.id]), follow=True)
    assert resp.status_code in (200, 302)
    assert not Cliente.objects.filter(id=cli.id).exists()


@pytest.mark.django_db
def test_clientes_import_csv_minimo() -> None:
    """Importa um cliente PF via CSV mínimo."""
    user = User.objects.create_user(username="imp", password="x")  # noqa: S106
    tenant = Tenant.objects.create(nome="TI1", schema_name="ti1")
    TenantUser.objects.create(user=user, tenant=tenant, is_tenant_admin=True)
    c = Client()
    c.login(username="imp", password="x")  # noqa: S106
    sess = c.session
    sess["tenant_id"] = tenant.id
    sess.save()
    # Monta CSV em memória
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["tipo", "email", "telefone", "nome", "cpf"])  # cabeçalho simples
    writer.writerow(["PF", "csv1@example.com", "119", "Cliente CSV", "123.456.789-00"])
    data = buffer.getvalue().encode("utf-8")
    upload = SimpleUploadedFile("clientes.csv", data, content_type="text/csv")
    resp = c.post(
        reverse("clientes:cliente_import"),
        data={"arquivo": upload, "formato": "csv"},
        follow=True,
    )
    assert resp.status_code in (200, 302)
    assert Cliente.objects.filter(tenant=tenant, pessoafisica__cpf="123.456.789-00").exists()
