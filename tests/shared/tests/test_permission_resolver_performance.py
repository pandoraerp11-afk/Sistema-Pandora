import time

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.mark.skipif(
    not __import__("os").environ.get("PANDORA_PERF"), reason="Set PANDORA_PERF=1 to run performance baseline tests"
)
def test_permission_resolver_baseline(settings):
    """Baseline simples de desempenho do permission_resolver.

    Mede tempo médio de resolução (cold + warm cache). Objetivo: detectar regressões grosseiras.
    Não é micro-benchmark exato; thresholds amplos para robustez em CI compartilhado.
    """
    settings.FEATURE_UNIFIED_ACCESS = True
    from core.models import Tenant, TenantUser
    from shared.services.permission_resolver import permission_resolver

    tenant = Tenant.objects.create(
        nome="Perf", slug="perf", enabled_modules={"modules": ["clientes", "financeiro", "obras"]}
    )
    user = User.objects.create_user("perfuser", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)

    actions = [f"VIEW_{m.upper()}" for m in ["clientes", "financeiro", "obras"]]

    # Cold runs
    cold_durations = []
    for act in actions:
        t0 = time.perf_counter()
        permission_resolver.resolve(user, tenant, act)
        cold_durations.append(time.perf_counter() - t0)

    # Warm runs (cache hit) multiple iterations
    warm_durations = []
    for _ in range(50):
        for act in actions:
            t0 = time.perf_counter()
            permission_resolver.resolve(user, tenant, act)
            warm_durations.append(time.perf_counter() - t0)

    avg_cold = sum(cold_durations) / len(cold_durations)
    avg_warm = sum(warm_durations) / len(warm_durations)

    # Thresholds: generous (0.02s cold, 0.003s warm) to avoid flaky failures on slower machines
    assert avg_cold < 0.02, f"Cold average too high: {avg_cold:.5f}s"
    assert avg_warm < 0.003, f"Warm average too high: {avg_warm:.5f}s"

    # Expor métricas para logs (pytest -vv mostra)
    print(
        f"PERF permission_resolver avg_cold={avg_cold:.6f}s avg_warm={avg_warm:.6f}s iterations={len(warm_durations)}"
    )


@pytest.mark.skipif(
    not __import__("os").environ.get("PANDORA_PERF"), reason="Set PANDORA_PERF=1 to run performance baseline tests"
)
def test_menu_render_baseline(settings, django_template_rendered_signal):
    from django.template import Context, Template

    from core.models import Tenant, TenantUser

    tenant = Tenant.objects.create(
        nome="Perf2", slug="perf2", enabled_modules={"modules": ["clientes", "financeiro", "obras"]}
    )
    user = User.objects.create_user("menuperf", password="x")
    TenantUser.objects.create(tenant=tenant, user=user, is_tenant_admin=True)
    settings.FEATURE_UNIFIED_ACCESS = True
    tpl = Template("{% load menu_tags %}{% render_sidebar_menu %}")

    class R:
        pass

    r = R()
    r.user = user
    r.session = {"tenant_id": tenant.id}
    r.path = "/"

    # Warm up
    tpl.render(Context({"request": r}))

    iterations = 100
    import time as _time

    t0 = _time.perf_counter()
    for _ in range(iterations):
        tpl.render(Context({"request": r}))
    total = _time.perf_counter() - t0
    avg = total / iterations
    # Threshold generoso: 8ms por render
    assert avg < 0.008, f"Menu render average too high: {avg:.5f}s"
    print(f"PERF menu_render avg={avg:.6f}s total={total:.6f}s iterations={iterations}")
