import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from documentos.models import DominioDocumento, RegraDocumento

User = get_user_model()


@pytest.mark.django_db
def test_bulk_setup_api_with_dominio_id(client):
    User.objects.create_superuser(username="admin_bulk1", email="a1@example.com", password="pass")
    client.login(username="admin_bulk1", password="pass")
    dominio = DominioDocumento.objects.create(nome="Fornecedores", slug="fornecedores", app_label="fornecedores")
    url = reverse("documentos:bulk_setup_api")
    payload = {
        "categorias": [{"temp_id": "c1", "nome": "Fiscal"}],
        "tipos": [{"temp_id": "t1", "nome": "Nota Fiscal", "categoria_ref": "c1", "periodicidade": "mensal"}],
        "regras": [
            {
                "tipo_ref": "t1",
                "exigencia": "obrigatorio",
                "nivel_aplicacao": "entidade",
                "escopo": "app",
                "dominio_id": dominio.id,
            }
        ],
    }
    r = client.post(url, data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 201, r.content
    data = r.json()
    assert data["regras"][0]["dominio_id"] == dominio.id
    regra = RegraDocumento.objects.get(pk=data["regras"][0]["id"])
    assert regra.dominio_id == dominio.id
    assert regra.app_label == dominio.app_label  # replicação legado


@pytest.mark.django_db
def test_bulk_setup_api_with_dominio_slug(client):
    User.objects.create_superuser(username="admin_bulk2", email="a2@example.com", password="pass")
    client.login(username="admin_bulk2", password="pass")
    dominio = DominioDocumento.objects.create(nome="Clientes", slug="clientes", app_label="clientes")
    url = reverse("documentos:bulk_setup_api")
    payload = {
        "categorias": [{"temp_id": "c1", "nome": "Operacional"}],
        "tipos": [{"temp_id": "t1", "nome": "Contrato Cliente", "categoria_ref": "c1", "periodicidade": "anual"}],
        "regras": [{"tipo_ref": "t1", "escopo": "filtro", "dominio_slug": "clientes"}],
    }
    r = client.post(url, data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 201, r.content
    regra = RegraDocumento.objects.get()
    assert regra.dominio_id == dominio.id
    assert regra.app_label == dominio.app_label


@pytest.mark.django_db
def test_bulk_setup_api_legacy_app_label_fallback(client):
    User.objects.create_superuser(username="admin_bulk3", email="a3@example.com", password="pass")
    client.login(username="admin_bulk3", password="pass")
    url = reverse("documentos:bulk_setup_api")
    payload = {
        "categorias": [{"temp_id": "c1", "nome": "Segurança"}],
        "tipos": [{"temp_id": "t1", "nome": "Documento Segurança", "categoria_ref": "c1", "periodicidade": "unico"}],
        "regras": [{"tipo_ref": "t1", "escopo": "app", "app_label": "seguranca"}],
    }
    r = client.post(url, data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 201, r.content
    regra = RegraDocumento.objects.get()
    assert regra.dominio_id is None
    assert regra.app_label == "seguranca"


@pytest.mark.django_db
def test_bulk_setup_api_error_missing_domain_and_app_label(client):
    User.objects.create_superuser(username="admin_bulk4", email="a4@example.com", password="pass")
    client.login(username="admin_bulk4", password="pass")
    url = reverse("documentos:bulk_setup_api")
    payload = {
        "categorias": [{"temp_id": "c1", "nome": "RH"}],
        "tipos": [{"temp_id": "t1", "nome": "Ficha Colaborador", "categoria_ref": "c1", "periodicidade": "unico"}],
        "regras": [{"tipo_ref": "t1", "escopo": "app"}],
    }
    r = client.post(url, data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 400
    body = r.json()
    assert "regras" in body["errors"]
    assert any("dominio" in e["errors"] for e in body["errors"]["regras"])
