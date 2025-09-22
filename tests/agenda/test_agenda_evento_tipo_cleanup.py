import pytest
from django.utils import timezone

from agenda.models import Evento
from core.models import Tenant


@pytest.mark.django_db
def test_evento_tipo_migration_management_command(django_capture_stdout):
    tenant = Tenant.objects.create(name="T", slug="t")
    # criar 2 eventos com tipo legado
    Evento.objects.create(tenant=tenant, titulo="Legacy 1", data_inicio=timezone.now(), tipo_evento="procedimento")
    Evento.objects.create(tenant=tenant, titulo="Legacy 2", data_inicio=timezone.now(), tipo_evento="procedimento")

    from django.core import management

    out = django_capture_stdout()
    with out:
        management.call_command("migrate_evento_tipo_procedimento_to_servico")
    printed = out.getvalue()
    assert "Atualizados" in printed
    # validar mudança
    assert Evento.objects.filter(tipo_evento="procedimento").count() == 0
    assert Evento.objects.filter(tipo_evento="servico").count() == 2
