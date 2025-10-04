"""Context processors for the core app."""

from importlib import import_module
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone


def tenant_context(request: HttpRequest) -> dict[str, Any]:
    """Contexto base do tenant + métricas leves Saúde."""
    tenant = getattr(request, "tenant", None)
    data = {"current_tenant": tenant, "VERSION": getattr(settings, "VERSION", "N/D")}
    if tenant and request.user.is_authenticated:
        try:
            pront_mod = import_module("prontuarios.models")
            atendimento = pront_mod.Atendimento
            hoje = timezone.localdate()
            data["saude_atendimentos_hoje"] = atendimento.objects.filter(
                tenant=tenant,
                data_atendimento__date=hoje,
            ).count()
        except ImportError:
            # Se o app não estiver disponível, ignora silenciosamente
            pass
    return data
