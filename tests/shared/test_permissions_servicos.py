from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from core.models import Tenant
from servicos.models import CategoriaServico, Servico, ServicoClinico
from shared.permissions_servicos import can_schedule_clinical_service


@pytest.mark.django_db
def test_can_schedule_superuser():
    t = Tenant.objects.create(nome="T", slug="t")
    cat = CategoriaServico.objects.create(nome="Cat", slug="cat")
    s = Servico.objects.create(
        tenant=t,
        nome_servico="S1",
        slug="s1",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
    )
    ServicoClinico.objects.create(servico=s, duracao_estimada=timedelta(minutes=30))
    User = get_user_model()
    u = User.objects.create_user("su", "su@x", "x")
    u.is_superuser = True
    u.save()
    assert can_schedule_clinical_service(u, s) is True


@pytest.mark.django_db
def test_can_schedule_secretaria_group():
    t = Tenant.objects.create(nome="T2", slug="t2")
    cat = CategoriaServico.objects.create(nome="Cat2", slug="cat2")
    s = Servico.objects.create(
        tenant=t,
        nome_servico="S2",
        slug="s2",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
    )
    ServicoClinico.objects.create(servico=s, duracao_estimada=timedelta(minutes=20))
    g = Group.objects.create(name="MinhaSecretaria")
    User = get_user_model()
    u = User.objects.create_user("user", "u@x", "x")
    u.groups.add(g)
    g.name = "EquipeSecretariaCentral"
    g.save()
    assert can_schedule_clinical_service(u, s) is True


@pytest.mark.django_db
def test_can_schedule_cliente_online():
    t = Tenant.objects.create(nome="T3", slug="t3")
    cat = CategoriaServico.objects.create(nome="Cat3", slug="cat3")
    s = Servico.objects.create(
        tenant=t,
        nome_servico="S3",
        slug="s3",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
        disponivel_online=True,
    )
    ServicoClinico.objects.create(servico=s, duracao_estimada=timedelta(minutes=25))
    User = get_user_model()
    u = User.objects.create_user("cli", "c@x", "x")
    assert can_schedule_clinical_service(u, s) is True


@pytest.mark.django_db
def test_denied_cliente_servico_offline():
    t = Tenant.objects.create(nome="T4", slug="t4")
    cat = CategoriaServico.objects.create(nome="Cat4", slug="cat4")
    s = Servico.objects.create(
        tenant=t,
        nome_servico="S4",
        slug="s4",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
        disponivel_online=False,
    )
    ServicoClinico.objects.create(servico=s, duracao_estimada=timedelta(minutes=25))
    User = get_user_model()
    u = User.objects.create_user("cli2", "c2@x", "x")
    assert can_schedule_clinical_service(u, s) is False


@pytest.mark.django_db
def test_denied_inactive_servico():
    t = Tenant.objects.create(nome="T5", slug="t5")
    cat = CategoriaServico.objects.create(nome="Cat5", slug="cat5")
    s = Servico.objects.create(
        tenant=t,
        nome_servico="S5",
        slug="s5",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=False,
    )
    ServicoClinico.objects.create(servico=s, duracao_estimada=timedelta(minutes=10))
    User = get_user_model()
    u = User.objects.create_user("cli3", "c3@x", "x")
    assert can_schedule_clinical_service(u, s) is False
