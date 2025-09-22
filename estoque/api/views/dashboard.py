"""Dashboard API refatorado para reutilizar lógica comum (ver mixin em home.py)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .home import EstoqueDashboardDataMixin


class DashboardEstoqueView(EstoqueDashboardDataMixin, APIView):
    """Dashboard reutiliza mixin unificado (ver home.py)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        return Response(self.build_dashboard_payload(tenant))
