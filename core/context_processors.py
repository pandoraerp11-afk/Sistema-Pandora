from django.utils import timezone


def tenant_context(request):
    """Contexto base do tenant + métricas leves Saúde."""
    tenant = getattr(request, "tenant", None)
    data = {"current_tenant": tenant}
    if tenant and request.user.is_authenticated:
        try:
            from prontuarios.models import Atendimento

            hoje = timezone.localdate()
            data["saude_atendimentos_hoje"] = Atendimento.objects.filter(
                tenant=tenant, data_atendimento__date=hoje
            ).count()
            # slots futuros livres removidos deste módulo
        except Exception:
            pass
    return data
