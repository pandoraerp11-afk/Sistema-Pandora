"""Teste: staff deve agendar serviço clínico mesmo offline."""

from datetime import timedelta
from typing import TYPE_CHECKING, cast

import pytest
from django.contrib.auth import get_user_model

if TYPE_CHECKING:  # pragma: no cover
    from django.contrib.auth.models import User as DjangoUser

from core.models import Tenant
from servicos.models import CategoriaServico, Servico, ServicoClinico
from shared.permissions_servicos import can_schedule_clinical_service


@pytest.mark.django_db
def test_staff_can_schedule_clinical_offline() -> None:
    """Assegura que is_staff ignora restrição de disponibilização online."""
    tenant = Tenant.objects.create(nome="TStaff", slug="tstaff")
    cat = CategoriaServico.objects.create(nome="CatStaff", slug="catstaff")
    serv = Servico.objects.create(
        tenant=tenant,
        nome_servico="SrvClinicoOff",
        slug="srvclinicooff",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
        disponivel_online=False,
    )
    ServicoClinico.objects.create(servico=serv, duracao_estimada=timedelta(minutes=30))
    user_model = get_user_model()
    staff = cast("DjangoUser", user_model.objects.create_user("staff1", "st@x", "x"))
    staff.is_staff = True
    staff.save(update_fields=["is_staff"])
    assert can_schedule_clinical_service(staff, serv) is True  # noqa: S101
