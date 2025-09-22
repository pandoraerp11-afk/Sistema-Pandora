from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponseForbidden, JsonResponse

from core.services.wizard_metrics import snapshot_metrics


@login_required
def wizard_metrics_view(request: HttpRequest):
    if not request.user.is_staff:
        return HttpResponseForbidden("Staff only")
    return JsonResponse({"wizard_metrics": snapshot_metrics()})
