"""
Métricas Prometheus para cotações e portal fornecedor.
"""

import time
from functools import wraps

from prometheus_client import Counter, Gauge, Histogram, Summary

# Métricas de Cotações
COTACAO_CREATED = Counter("pandora_cotacao_created_total", "Cotações criadas", ["tenant"])
COTACAO_STATUS_CHANGE = Counter(
    "pandora_cotacao_status_change_total", "Mudanças de status de cotação", ["tenant", "from_status", "to_status"]
)

# Métricas de Propostas
PROPOSTA_SUBMITTED = Counter("pandora_proposta_submitted_total", "Propostas enviadas", ["tenant"])
PROPOSTA_SELECTED = Counter("pandora_proposta_selected_total", "Propostas selecionadas", ["tenant"])
PROPOSTA_REJECTED = Counter("pandora_proposta_rejected_total", "Propostas rejeitadas", ["tenant"])

# Métricas de Portal
PORTAL_LOGIN = Counter("pandora_portal_login_total", "Logins no portal", ["portal_type", "tenant"])
PORTAL_VIEW_HITS = Counter(
    "pandora_portal_view_hits_total", "Acessos a views do portal", ["portal_type", "view_name", "tenant"]
)
PORTAL_ACTION_DURATION = Histogram(
    "pandora_portal_action_duration_seconds", "Duração de ações do portal", ["portal_type", "action"]
)

# Métricas de Estado
COTACOES_ATIVAS = Gauge("pandora_cotacoes_ativas", "Cotações ativas por tenant", ["tenant"])
FORNECEDORES_ATIVOS = Gauge("pandora_fornecedores_ativos", "Fornecedores com portal ativo", ["tenant"])
PROPOSTAS_PENDENTES = Gauge("pandora_propostas_pendentes", "Propostas aguardando decisão", ["tenant"])

# Health Metrics
HEALTH_CHECK_DURATION = Summary("pandora_health_check_duration_seconds", "Duração dos health checks", ["component"])


def track_cotacao_metrics(action_type):
    """
    Decorator para rastrear métricas de cotações.

    Usage:
        @track_cotacao_metrics('create')
        def create_cotacao(request):
            pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                # Extrair tenant do contexto
                tenant = None
                if hasattr(args[0], "tenant"):
                    tenant = args[0].tenant
                elif len(args) > 1 and hasattr(args[1], "tenant"):
                    tenant = args[1].tenant

                tenant_label = str(tenant.id) if tenant else "unknown"

                # Registrar métrica baseada no tipo de ação
                if action_type == "create" and tenant:
                    COTACAO_CREATED.labels(tenant=tenant_label).inc()
                elif action_type == "submit_proposta" and tenant:
                    PROPOSTA_SUBMITTED.labels(tenant=tenant_label).inc()
                elif action_type == "select_proposta" and tenant:
                    PROPOSTA_SELECTED.labels(tenant=tenant_label).inc()

                return result

            except Exception:
                # Registrar erro se necessário
                raise
            finally:
                # Registrar duração
                duration = time.time() - start_time
                PORTAL_ACTION_DURATION.labels(portal_type="cotacoes", action=action_type).observe(duration)

        return wrapper

    return decorator


def track_portal_view(portal_type="fornecedor"):
    """
    Decorator para rastrear acessos a views do portal.

    Usage:
        @track_portal_view('fornecedor')
        def dashboard_view(request):
            pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()

            try:
                result = func(request, *args, **kwargs)

                # Extrair informações do request
                tenant = getattr(request, "tenant", None)
                tenant_label = str(tenant.id) if tenant else "unknown"
                view_name = func.__name__

                # Registrar hit
                PORTAL_VIEW_HITS.labels(portal_type=portal_type, view_name=view_name, tenant=tenant_label).inc()

                return result

            finally:
                # Registrar duração
                duration = time.time() - start_time
                PORTAL_ACTION_DURATION.labels(portal_type=portal_type, action=f"view_{func.__name__}").observe(duration)

        return wrapper

    return decorator


def update_state_metrics():
    """
    Atualiza métricas de estado (Gauges).
    Deve ser chamada periodicamente via task.
    """
    try:
        from core.models import Tenant
        from cotacoes.models import Cotacao, PropostaFornecedor
        from fornecedores.models import Fornecedor

        for tenant in Tenant.objects.all():
            tenant_label = str(tenant.id)

            # Cotações ativas
            cotacoes_ativas = Cotacao.objects.filter(tenant=tenant, status="aberta").count()
            COTACOES_ATIVAS.labels(tenant=tenant_label).set(cotacoes_ativas)

            # Fornecedores ativos
            fornecedores_ativos = Fornecedor.objects.filter(tenant=tenant, portal_ativo=True, status="active").count()
            FORNECEDORES_ATIVOS.labels(tenant=tenant_label).set(fornecedores_ativos)

            # Propostas pendentes
            propostas_pendentes = PropostaFornecedor.objects.filter(cotacao__tenant=tenant, status="enviada").count()
            PROPOSTAS_PENDENTES.labels(tenant=tenant_label).set(propostas_pendentes)

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao atualizar métricas de estado: {e}")


def health_check_component(component_name):
    """
    Decorator para health checks com métricas.

    Usage:
        @health_check_component('database')
        def check_database():
            # verificação
            return True, "OK"
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with HEALTH_CHECK_DURATION.labels(component=component_name).time():
                return func(*args, **kwargs)

        return wrapper

    return decorator
