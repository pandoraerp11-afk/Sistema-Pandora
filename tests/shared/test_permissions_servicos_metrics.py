from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import Tenant
from servicos.models import CategoriaServico, Servico, ServicoClinico
from shared.permissions_servicos import can_schedule_clinical_service, get_clinical_denials_count


@pytest.mark.django_db
def test_clinical_denial_metric_increments_only_on_denial():
    # Reset métrica explicitamente
    cache.delete("metric:clinical_schedule_denials")
    assert get_clinical_denials_count() == 0

    t = Tenant.objects.create(nome="T6", slug="t6")
    cat = CategoriaServico.objects.create(nome="Cat6", slug="cat6")
    # Serviço clínico offline (nega cliente)
    s_offline = Servico.objects.create(
        tenant=t,
        nome_servico="S6",
        slug="s6",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
        disponivel_online=False,
    )
    ServicoClinico.objects.create(servico=s_offline, duracao_estimada=timedelta(minutes=15))

    # Serviço clínico online (permite cliente)
    s_online = Servico.objects.create(
        tenant=t,
        nome_servico="S7",
        slug="s7",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=True,
        ativo=True,
        disponivel_online=True,
    )
    ServicoClinico.objects.create(servico=s_online, duracao_estimada=timedelta(minutes=20))

    User = get_user_model()
    u = User.objects.create_user("cli_metric", "cm@x", "x")

    # 1) Acesso negado (offline)
    assert can_schedule_clinical_service(u, s_offline) is False
    assert get_clinical_denials_count() == 1

    # 2) Acesso permitido (online) não incrementa
    assert can_schedule_clinical_service(u, s_online) is True
    assert get_clinical_denials_count() == 1

    # 3) Outro acesso negado incrementa novamente
    assert can_schedule_clinical_service(u, s_offline) is False
    assert get_clinical_denials_count() == 2


@pytest.mark.django_db
def test_clinical_denial_metric_not_incremented_for_non_clinical():
    cache.delete("metric:clinical_schedule_denials")
    t = Tenant.objects.create(nome="T7", slug="t7")
    cat = CategoriaServico.objects.create(nome="Cat7", slug="cat7")
    # Serviço não clínico (função retorna False mas não é caso de perfil clínico?)
    s = Servico.objects.create(
        tenant=t,
        nome_servico="S8",
        slug="s8",
        categoria=cat,
        preco_base=10,
        descricao="d",
        is_clinical=False,
        ativo=True,
    )
    User = get_user_model()
    u = User.objects.create_user("cli_metric2", "cm2@x", "x")

    # Chamada: retorna False (não clínico) e não deve incrementar métrica
    assert can_schedule_clinical_service(u, s) is False
    # Como a função sai cedo, métrica permanece 0
    assert get_clinical_denials_count() == 0
