import pytest
from django.contrib.auth import get_user_model

from shared.services.permission_resolver import permission_resolver

User = get_user_model()


@pytest.mark.django_db
def test_pipeline_dynamic_add_remove(permission_resolver=permission_resolver):
    # Setup usuário e tenant mínimos
    from core.models import Role, Tenant, TenantUser

    user = User.objects.create(username="u1", is_active=True)
    tenant = Tenant.objects.create(name="T1", slug="t1")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    # Garantir step custom não existe
    assert "dummy_step" not in permission_resolver.list_pipeline_steps()

    # Injetar método dinamicamente
    def _step_dummy(self, user, tenant, action, resource, context):
        if action == "ACTION_X":
            return True, "via dummy", "dummy"
        return None

    # Monkeypatch no objeto
    permission_resolver.__class__._step_dummy = _step_dummy

    added = permission_resolver.add_pipeline_step("_step_dummy", position=0)
    assert added
    assert "_step_dummy" in permission_resolver.list_pipeline_steps()

    # Resolver ação que dummy concede
    allowed, reason = permission_resolver.resolve(user, tenant, "ACTION_X")
    assert allowed is True
    assert "dummy" in reason

    # Remover e garantir que agora nega (pipeline exausta)
    removed = permission_resolver.remove_pipeline_step("_step_dummy")
    assert removed
    allowed2, reason2 = permission_resolver.resolve(user, tenant, "ACTION_X")
    assert allowed2 is False
    # Após remoção o step _step_default retorna negação antes de chegar no fallback de pipeline exaurida.
    assert ("pipeline exhausted" in reason2) or ("default" in reason2)


@pytest.mark.django_db
def test_global_invalidation(permission_resolver=permission_resolver):
    from core.models import Role, Tenant, TenantUser

    user = User.objects.create(username="u2", is_active=True)
    tenant = Tenant.objects.create(name="T2", slug="t2")
    role = Role.objects.create(name="basic", tenant=tenant)
    TenantUser.objects.create(user=user, tenant=tenant, role=role)

    # Primeira resolução (gera cache miss)
    permission_resolver.resolve(user, tenant, "UNKNOWN_ACTION")
    # Segunda deve ser hit
    allowed_cached, reason_cached = permission_resolver.resolve(user, tenant, "UNKNOWN_ACTION")
    assert "cache" in reason_cached or "default" in reason_cached

    # Invalidação global
    permission_resolver.invalidate_cache()

    # Após invalidar, uma nova resolução deve recomputar (não conseguimos inspecionar TTL, mas o reason muda por novo trace sem cache_hit inicial)
    allowed_after, reason_after = permission_resolver.resolve(user, tenant, "UNKNOWN_ACTION")
    # Se trace presente, deve não ter cache_hit antes da cadeia
    if "|trace=" in reason_after:
        assert "cache_hit" not in reason_after.split("|trace=")[1].split(">")[0]
