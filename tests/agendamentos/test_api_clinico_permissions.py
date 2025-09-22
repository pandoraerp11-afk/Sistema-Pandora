from datetime import date, datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from agendamentos.models import Disponibilidade, Slot
from clientes.models import AcessoCliente, Cliente
from core.models import Tenant
from servicos.models import CategoriaServico, Servico, ServicoClinico
from shared.permissions_servicos import CLINICAL_SCHEDULING_DENIED_MESSAGE


@pytest.mark.django_db
def _criar_slot(tenant, profissional):
    disp = Disponibilidade.objects.create(
        tenant=tenant,
        profissional=profissional,
        data=date.today() + timedelta(days=1),
        hora_inicio=time(9, 0),
        hora_fim=time(10, 0),
        duracao_slot_minutos=30,
        capacidade_por_slot=1,
    )
    # Usa timezone para evitar datetime ingênuo
    naive = datetime.combine(disp.data, time(9, 0))
    horario = timezone.make_aware(naive, timezone.get_current_timezone()) if timezone.is_naive(naive) else naive
    slot = Slot.objects.create(
        tenant=tenant,
        disponibilidade=disp,
        profissional=profissional,
        horario=horario,
        capacidade_total=1,
        capacidade_utilizada=0,
        ativo=True,
    )
    return slot


@pytest.mark.django_db
def test_staff_pode_reservar_clinico(client):
    tenant = Tenant.objects.create(nome="T", slug="t")
    cat = CategoriaServico.objects.create(nome="Cat", slug="cat")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Clin",
        slug="clin",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
    )
    ServicoClinico.objects.create(servico=serv, duracao_estimada=timedelta(minutes=30))
    User = get_user_model()
    prof = User.objects.create_user("prof", "p@x", "x")
    prof.is_staff = True
    prof.save()
    from core.models import TenantUser

    TenantUser.objects.create(tenant=tenant, user=prof)
    client.force_login(prof)
    client.session["tenant_id"] = tenant.id
    slot = _criar_slot(tenant, prof)
    url = reverse("agendamentos:slot-reservar", kwargs={"pk": slot.id})
    resp = client.post(url, {"cliente_id": _criar_cliente(tenant).id, "servico_id": serv.id})
    assert resp.status_code == 200, resp.content


@pytest.mark.django_db
def test_cliente_portal_pode_reservar_clinico_online(client):
    tenant = Tenant.objects.create(nome="T2", slug="t2")
    cat = CategoriaServico.objects.create(nome="Cat2", slug="cat2")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Clin2",
        slug="clin2",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
        disponivel_online=True,
    )
    ServicoClinico.objects.create(servico=serv, duracao_estimada=timedelta(minutes=20))
    User = get_user_model()
    prof = User.objects.create_user("prof2", "p2@x", "x")
    prof.is_staff = True
    prof.save()
    from core.models import TenantUser as _TU

    _TU.objects.create(tenant=tenant, user=prof)
    slot = _criar_slot(tenant, prof)
    cli_user = User.objects.create_user("cli", "c@x", "x")
    cliente = _criar_cliente(tenant)
    AcessoCliente.objects.create(cliente=cliente, usuario=cli_user)
    from core.models import TenantUser

    TenantUser.objects.create(tenant=tenant, user=cli_user)
    client.force_login(cli_user)
    client.session["tenant_id"] = tenant.id
    client.session.save()
    url = reverse("agendamentos:cliente-slot-reservar", kwargs={"pk": slot.id})
    resp = client.post(url, {"servico_id": serv.id})
    assert resp.status_code == 200, resp.content


@pytest.mark.django_db
def test_cliente_portal_negado_servico_clinico_offline(client):
    tenant = Tenant.objects.create(nome="T3", slug="t3")
    cat = CategoriaServico.objects.create(nome="Cat3", slug="cat3")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Clin3",
        slug="clin3",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
        disponivel_online=False,
    )
    ServicoClinico.objects.create(servico=serv, duracao_estimada=timedelta(minutes=25))
    User = get_user_model()
    prof = User.objects.create_user("prof3", "p3@x", "x")
    prof.is_staff = True
    prof.save()
    from core.models import TenantUser as _TU3

    _TU3.objects.create(tenant=tenant, user=prof)
    slot = _criar_slot(tenant, prof)
    cli_user = User.objects.create_user("cli3", "c3@x", "x")
    cliente = _criar_cliente(tenant)
    AcessoCliente.objects.create(cliente=cliente, usuario=cli_user)
    from core.models import TenantUser

    TenantUser.objects.create(tenant=tenant, user=cli_user)
    client.force_login(cli_user)
    client.session["tenant_id"] = tenant.id
    client.session.save()
    url = reverse("agendamentos:cliente-slot-reservar", kwargs={"pk": slot.id})
    resp = client.post(url, {"servico_id": serv.id})
    assert resp.status_code == 403
    assert resp.json()["detail"] == str(CLINICAL_SCHEDULING_DENIED_MESSAGE)


@pytest.mark.django_db
def test_staff_negado_servico_clinico_inativo(client):
    tenant = Tenant.objects.create(nome="T4", slug="t4")
    cat = CategoriaServico.objects.create(nome="Cat4", slug="cat4")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="Clin4",
        slug="clin4",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=False,
    )
    ServicoClinico.objects.create(servico=serv, duracao_estimada=timedelta(minutes=25))
    User = get_user_model()
    prof = User.objects.create_user("prof4", "p4@x", "x")
    prof.is_staff = True
    prof.save()
    from core.models import TenantUser as _TU4

    _TU4.objects.create(tenant=tenant, user=prof)
    client.force_login(prof)
    client.session["tenant_id"] = tenant.id
    slot = _criar_slot(tenant, prof)
    url = reverse("agendamentos:slot-reservar", kwargs={"pk": slot.id})
    resp = client.post(url, {"cliente_id": _criar_cliente(tenant).id, "servico_id": serv.id})
    assert resp.status_code == 403
    assert resp.json()["detail"] == str(CLINICAL_SCHEDULING_DENIED_MESSAGE)


# Helpers
@pytest.mark.django_db
def _criar_cliente(tenant):
    cliente = Cliente.objects.create(tenant=tenant, tipo="PF", status="active")
    from clientes.models import PessoaFisica

    PessoaFisica.objects.create(cliente=cliente, nome_completo="Nome Teste", cpf="000.000.000-00")
    return cliente
