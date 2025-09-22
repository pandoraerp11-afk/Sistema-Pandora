from django.urls import path

from . import views

app_name = "ai_auditor"

urlpatterns = [
    # Dashboard
    path("home/", views.AIAuditorDashboardView.as_view(), name="ai_auditor_home"),
    path("", views.DashboardView.as_view(), name="dashboard"),
    # Análise - rota principal para análises
    path("analise/", views.CodeIssueListView.as_view(), name="analise"),
    # Chat e API
    path("chat/", views.ChatView.as_view(), name="chat"),
    path("api/chat/", views.ChatAPIView.as_view(), name="chat_api"),
    # Auditorias
    path("execute-audit/", views.ExecuteAuditView.as_view(), name="execute_audit"),
    path("execute-security-audit/", views.ExecuteSecurityAuditView.as_view(), name="execute_security_audit"),
    path("execute-performance-audit/", views.ExecutePerformanceAuditView.as_view(), name="execute_performance_audit"),
    # Sessões
    path("sessions/", views.AuditSessionListView.as_view(), name="session_list"),
    path("sessions/<int:pk>/", views.AuditSessionDetailView.as_view(), name="session_detail"),
    path("sessions/<int:pk>/report/", views.SessionReportView.as_view(), name="session_report"),
    # Problemas
    path("issues/", views.CodeIssueListView.as_view(), name="issue_list"),
    path("issues/<int:pk>/", views.CodeIssueDetailView.as_view(), name="issue_detail"),
    path("issues/<int:pk>/fix/", views.AutoFixIssueView.as_view(), name="auto_fix_issue"),
    # Configurações
    path("settings/", views.AIAuditorSettingsView.as_view(), name="settings"),
]
