"""Dashboard view for the AI Auditor app.

Provides an authenticated, tenant-aware dashboard showing recent audit sessions and issue counts by severity.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from ai_auditor.models import AuditSession, CodeIssue
from core.mixins import TenantRequiredMixin


class DashboardView(LoginRequiredMixin, TenantRequiredMixin, View):
    """Authenticated, tenant-aware dashboard view showing recent audit sessions and issue counts by severity."""

    def get(self, request, *args, **kwargs):
        tenant = request.tenant

        # Obter as últimas sessões de auditoria
        latest_sessions = AuditSession.objects.filter(tenant=tenant).order_by()[:5]

        # Contagem de problemas por severidade
        total_issues = CodeIssue.objects.filter(session__tenant=tenant).count()
        critical_issues = CodeIssue.objects.filter(
            session__tenant=tenant,
            severity="critical",
        ).count()
        high_issues = CodeIssue.objects.filter(
            session__tenant=tenant,
            severity="high",
        ).count()
        medium_issues = CodeIssue.objects.filter(
            session__tenant=tenant,
            severity="medium",
        ).count()
        low_issues = CodeIssue.objects.filter(
            session__tenant=tenant,
            severity="low",
        ).count()

        context = {
            "latest_sessions": latest_sessions,
            "total_issues": total_issues,
            "critical_issues": critical_issues,
            "high_issues": high_issues,
            "medium_issues": medium_issues,
            "low_issues": low_issues,
        }
        return render(request, "ai_auditor/dashboard.html", context)
