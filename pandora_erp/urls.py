import json

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

"""URL configuration principal do Pandora ERP.

Inclui integração opcional com Prometheus. O import de prometheus_client é
protegido para que a ausência ou erro de instalação do pacote não impeça o
servidor de inicializar. A rota /metrics retornará 503 se o pacote não estiver
disponível ou apresentará as métricas padrão caso esteja instalado.
"""

# Import Prometheus de forma segura
try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # type: ignore

    _PROM_AVAILABLE = True
except Exception:  # ModuleNotFoundError ou qualquer outro problema de runtime
    generate_latest = None  # type: ignore
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"  # fallback mínimo
    _PROM_AVAILABLE = False
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from core.views import dashboard
from core.views_help import AjudaView


def metrics_view(request):
    """Endpoint de métricas Prometheus (seguro mesmo sem a lib)."""
    if not _PROM_AVAILABLE or generate_latest is None:
        return HttpResponse(
            json.dumps({"status": "unavailable", "detail": "prometheus_client não instalado ou falhou no import"}),
            status=503,
            content_type="application/json",
        )
    try:
        output = generate_latest()
        return HttpResponse(output, content_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        return HttpResponse(
            json.dumps({"status": "error", "detail": f"Falha ao gerar métricas: {e}"}),
            status=500,
            content_type="application/json",
        )


def redirect_to_dashboard(request):
    """Redireciona a raiz do site para o dashboard do sistema"""
    return redirect("dashboard")


urlpatterns = [
    path("django-admin/", admin.site.urls),
    # --- Página inicial redireciona para dashboard ---
    path("", redirect_to_dashboard, name="home"),
    # --- Dashboard Principal do Sistema ---
    path("dashboard/", dashboard, name="dashboard"),
    # Métricas Prometheus (opcional)
    path("metrics/", metrics_view, name="metrics"),
    # --- Módulos ---
    path("core/", include("core.urls", namespace="core")),
    # APIs principais (namespaces usados nos testes)
    path("core-api/", include("core.api_urls", namespace="core_api")),
    path("admin-panel/", include("admin.urls", namespace="administration")),
    # Alias de compatibilidade para testes que usam namespace 'admin'
    path("admin/", include("admin.urls", namespace="admin")),
    path("clientes/", include("clientes.urls", namespace="clientes")),
    path("obras/", include("obras.urls", namespace="obras")),
    path("orcamentos/", include("orcamentos.urls", namespace="orcamentos")),
    path("fornecedores/", include("fornecedores.urls", namespace="fornecedores")),
    path("cotacoes/", include("cotacoes.urls", namespace="cotacoes")),
    path("compras/", include("compras.urls", namespace="compras")),
    path("financeiro/", include("financeiro.urls", namespace="financeiro")),
    path("estoque/", include("estoque.urls", namespace="estoque")),
    path("estoque-api/", include("estoque.api_urls", namespace="estoque_api")),
    path("produtos/", include("produtos.urls", namespace="produtos")),
    path("servicos/", include("servicos.urls", namespace="servicos")),
    path("funcionarios/", include("funcionarios.urls", namespace="funcionarios")),
    path("agenda/", include("agenda.urls", namespace="agenda")),
    # Eventos unificado na Agenda; rota antiga temporariamente redirecionada
    # path("eventos/", include("eventos.urls", namespace="eventos")),
    path("chat/", include("chat.urls", namespace="chat")),
    path("notifications/", include("notifications.urls", namespace="notifications")),
    path("relatorios/", include("relatorios.urls", namespace="relatorios")),
    path("bi/", include("bi.urls", namespace="bi")),
    path("ai-auditor/", include("ai_auditor.urls", namespace="ai_auditor")),
    path("assistente-web/", include("assistente_web.urls", namespace="assistente_web")),
    path("cadastros-gerais/", include("cadastros_gerais.urls", namespace="cadastros_gerais")),
    path("aprovacoes/", include("aprovacoes.urls", namespace="aprovacoes")),
    path("apropriacao/", include("apropriacao.urls", namespace="apropriacao")),
    path("sst/", include("sst.urls", namespace="sst")),
    path("quantificacao-obras/", include("quantificacao_obras.urls", namespace="quantificacao_obras")),
    path("mao-obra/", include("mao_obra.urls", namespace="mao_obra")),
    path("prontuarios/", include("prontuarios.urls", namespace="prontuarios")),
    path("agendamentos/", include("agendamentos.urls", namespace="agendamentos")),
    path("treinamento/", include("treinamento.urls", namespace="treinamento")),
    path("formularios/", include("formularios.urls", namespace="formularios")),
    path("formularios-dinamicos/", include("formularios_dinamicos.urls", namespace="formularios_dinamicos")),
    path("user-management/", include("user_management.urls", namespace="user_management")),
    path("documentos/", include("documentos.urls", namespace="documentos")),
    path("portal-cliente/", include("portal_cliente.urls", namespace="portal_cliente")),
    path("ajuda/", AjudaView.as_view(), name="ajuda_home"),
]

# Configuração para servir arquivos estáticos/mídia durante desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
