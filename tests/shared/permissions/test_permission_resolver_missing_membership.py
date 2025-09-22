import pytest
from django.contrib.auth import get_user_model

from core.models import Tenant
from shared.services.permission_resolver import permission_resolver

pytestmark = [pytest.mark.django_db, pytest.mark.permission]


def test_resolve_denies_when_user_not_in_tenant(settings):
    User = get_user_model()
    user = User.objects.create_user("outsider", password="x")
    tenant = Tenant.objects.create(name="T1", subdomain="t1")
    allowed, reason = permission_resolver.resolve(user, tenant, "VIEW_COTACAO")
    assert allowed is False
    assert "não pertence" in reason.lower() or "inativo" in reason.lower()
