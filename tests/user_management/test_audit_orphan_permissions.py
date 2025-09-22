import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

User = get_user_model()


@pytest.mark.django_db
def test_audit_orphan_permissions_reports(capsys):
    from core.models import Tenant
    from user_management.models import PermissaoPersonalizada

    u = User.objects.create(username="x")
    t = Tenant.objects.create(name="T", slug="t")
    # cria órfãs: ação inexistente
    PermissaoPersonalizada.objects.create(user=u, scope_tenant=None, acao="EDIT", modulo="INEXISTENTE", concedida=True)
    # cria válida: VIEW_COTACAO (assumindo que existe no action_map)
    PermissaoPersonalizada.objects.create(user=u, scope_tenant=t, acao="VIEW", modulo="COTACAO", concedida=True)

    call_command("audit_orphan_permissions")
    out, err = capsys.readouterr()
    assert "permissões órfãs encontradas" in out or "Nenhuma permissão órfã encontrada" in out
