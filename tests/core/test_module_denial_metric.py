import pytest
from django.core.cache import cache

from core.authorization import REASON_MODULE_DISABLED, log_module_denial


@pytest.mark.django_db
def test_module_denial_metric_increment(django_user_model):
    user = django_user_model.objects.create(username="muser")

    class DummyTenant:  # minimal stub
        id = 1
        enabled_modules = []

        def is_module_enabled(self, mod):
            return False

    tenant = DummyTenant()

    # Limpa contador prévio
    key = f"module_deny_count:financeiro:{REASON_MODULE_DISABLED}"
    cache.delete(key)

    log_module_denial(user, tenant, "financeiro", REASON_MODULE_DISABLED)
    v1 = cache.get(key)
    assert v1 == 1
    log_module_denial(user, tenant, "financeiro", REASON_MODULE_DISABLED)
    v2 = cache.get(key)
    assert v2 == 2
