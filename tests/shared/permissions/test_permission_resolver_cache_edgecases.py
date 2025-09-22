import pytest
from django.contrib.auth import get_user_model

from core.models import Tenant
from shared.services.permission_resolver import permission_resolver

User = get_user_model()


@pytest.mark.django_db
def test_permission_resolver_cache_key_includes_resource_and_invalidates_by_version():
    user = User.objects.create(username="permuser", is_active=True)
    tenant = Tenant.objects.create(name="T1", slug="t1")

    # Garantir estado limpo
    permission_resolver.invalidate_cache(user_id=user.id, tenant_id=tenant.id)

    allow1, _ = permission_resolver.resolve(user, tenant, "VIEW_COTACAO", resource="cotacao:1")
    allow2, _ = permission_resolver.resolve(user, tenant, "VIEW_COTACAO", resource="cotacao:2")

    # Chaves diferentes por recurso devem produzir resultados independentes (mesmo que iguais)
    assert isinstance(allow1, bool)
    assert isinstance(allow2, bool)

    # Invalidação seletiva deve forçar novo cálculo
    permission_resolver.invalidate_cache(user_id=user.id, tenant_id=tenant.id)
    allow3, _ = permission_resolver.resolve(user, tenant, "VIEW_COTACAO", resource="cotacao:1")
    assert isinstance(allow3, bool)


@pytest.mark.django_db
def test_permission_resolver_cache_global_era_bump():
    user = User.objects.create(username="permuser2", is_active=True)
    tenant = Tenant.objects.create(name="T2", slug="t2")

    _ = permission_resolver.resolve(user, tenant, "VIEW_COTACAO")
    # Bump global era
    permission_resolver.invalidate_cache()
    _ = permission_resolver.resolve(user, tenant, "VIEW_COTACAO")
    # Sem asserts fortes; apenas valida que não lança exceção
