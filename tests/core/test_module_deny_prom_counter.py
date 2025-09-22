import pytest
from django.contrib.auth import get_user_model

from core.authorization import MODULE_DENY_COUNTER, REASON_MODULE_DISABLED, log_module_denial
from core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
def test_module_deny_prometheus_counter(settings):
    if MODULE_DENY_COUNTER is None:
        pytest.skip("Prometheus não instalado")
    settings.FEATURE_LOG_MODULE_DENIALS = True
    user = User.objects.create(username="denyuser")
    tenant = Tenant.objects.create(name="T", subdomain="t-deny")
    before = None
    try:
        # coleta valor atual
        for s in MODULE_DENY_COUNTER.collect():
            for sample in s.samples:
                if sample.labels.get("module") == "xmod" and sample.labels.get("reason") == REASON_MODULE_DISABLED:
                    before = sample.value
    except Exception:
        before = None
    log_module_denial(user, tenant, "xmod", REASON_MODULE_DISABLED)
    after = None
    for s in MODULE_DENY_COUNTER.collect():
        for sample in s.samples:
            if sample.labels.get("module") == "xmod" and sample.labels.get("reason") == REASON_MODULE_DISABLED:
                after = sample.value
    if before is None:
        assert after is not None and after >= 1
    else:
        assert after == before + 1
