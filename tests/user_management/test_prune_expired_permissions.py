import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from core.models import Tenant
from user_management.models import PerfilUsuarioEstendido, PermissaoPersonalizada

User = get_user_model()


@pytest.mark.django_db
def test_prune_expired_permissions():
    u = User.objects.create(username="permu")
    tenant = Tenant.objects.create(name="TP", subdomain="tp")
    PerfilUsuarioEstendido.objects.get_or_create(user=u)
    PermissaoPersonalizada.objects.create(
        user=u,
        modulo="X",
        acao="VIEW",
        concedida=True,
        scope_tenant=tenant,
        data_expiracao=timezone.now() - timezone.timedelta(days=1),
    )
    assert PermissaoPersonalizada.objects.count() == 1
    call_command("prune_expired_permissions")
    assert PermissaoPersonalizada.objects.count() == 0
