from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.models import Tenant
from servicos.models import CategoriaServico, Servico, ServicoClinico


@pytest.mark.django_db
def test_criar_servico_clinico(client):
    User = get_user_model()
    user = User.objects.create_user("admin", "a@a.com", "x")
    user.is_staff = True
    user.save()
    client.force_login(user)
    tenant = Tenant.objects.create(nome="T1", slug="t1")
    # Vincula usuário ao tenant (TenantRequiredMixin)
    from core.models import TenantUser

    TenantUser.objects.create(tenant=tenant, user=user)
    cat = CategoriaServico.objects.create(nome="Cat A", slug="cat-a")
    url = reverse("servicos:servico_ofertado_create")
    # Seleciona tenant na sessão (TenantRequiredMixin)
    client.session["tenant_id"] = tenant.id
    client.session.save()
    resp = client.post(
        url,
        data={
            "tipo_servico": "OFERTADO",
            "nome_servico": "Serviço Clínico X",
            "categoria": cat.id,
            "preco_base": "100",
            "descricao_curta": "Desc",
            "descricao": "Longa",
            "is_clinical": "on",
            "ativo": "on",
            "clinico-duracao_estimada": "00:30",
            "clinico-intervalo_minimo_sessoes": 7,
            "clinico-requer_anamnese": "on",
            "clinico-requer_termo_consentimento": "on",
            "clinico-permite_fotos_evolucao": "on",
        },
        follow=True,
    )
    assert resp.status_code == 200
    s = Servico.objects.get(nome_servico="Serviço Clínico X")
    assert s.is_clinical is True
    assert hasattr(s, "perfil_clinico")
    assert s.perfil_clinico.duracao_estimada == timedelta(minutes=30)


@pytest.mark.django_db
def test_remover_perfil_clinico_na_edicao(client):
    User = get_user_model()
    user = User.objects.create_user("admin2", "b@b.com", "x")
    user.is_staff = True
    user.save()
    client.force_login(user)
    tenant = Tenant.objects.create(nome="T2", slug="t2")
    from core.models import TenantUser

    TenantUser.objects.create(tenant=tenant, user=user)
    cat = CategoriaServico.objects.create(nome="Cat B", slug="cat-b")
    s = Servico.objects.create(
        tenant=tenant,
        tipo_servico="OFERTADO",
        nome_servico="Clin X",
        slug="clin-x",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
    )
    ServicoClinico.objects.create(servico=s, duracao_estimada=timedelta(minutes=20))
    url = reverse("servicos:servico_ofertado_update", kwargs={"slug": s.slug})
    client.session["tenant_id"] = tenant.id
    client.session.save()
    resp = client.post(
        url,
        data={
            "tipo_servico": "OFERTADO",
            "nome_servico": "Clin X",
            "categoria": cat.id,
            "preco_base": "10",
            "descricao_curta": "",
            "descricao": "d",
            "ativo": "on",
            # is_clinical ausente => desmarca
        },
        follow=True,
    )
    assert resp.status_code == 200
    s.refresh_from_db()
    assert s.is_clinical is False
    assert not hasattr(s, "perfil_clinico")


@pytest.mark.django_db
def test_validacao_duracao_invalida(client):
    User = get_user_model()
    user = User.objects.create_user("admin3", "c@c.com", "x")
    user.is_staff = True
    user.save()
    client.force_login(user)
    tenant = Tenant.objects.create(nome="T3", slug="t3")
    from core.models import TenantUser

    TenantUser.objects.create(tenant=tenant, user=user)
    cat = CategoriaServico.objects.create(nome="Cat C", slug="cat-c")
    url = reverse("servicos:servico_ofertado_create")
    client.session["tenant_id"] = tenant.id
    client.session.save()
    resp = client.post(
        url,
        data={
            "tipo_servico": "OFERTADO",
            "nome_servico": "Serv XX",
            "categoria": cat.id,
            "preco_base": "50",
            "descricao": "desc",
            "is_clinical": "on",
            "clinico-duracao_estimada": "abc",  # inválido
        },
    )
    # Deve retornar erro de formulário (200 com erro exibido)
    assert resp.status_code == 200
    assert Servico.objects.filter(nome_servico="Serv XX").count() == 0
