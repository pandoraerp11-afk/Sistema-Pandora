from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from .models import Tenant, TenantUser
from .serializers import TenantSerializer, TenantUserSerializer, UserSerializer
from .services.cargo_catalog import CARGO_CATALOGO, normalizar_cargo
from .utils import get_current_tenant

try:
    from .authorization import can_access_module
except Exception:
    can_access_module = None
try:
    from shared.services.permission_resolver import permission_resolver
except Exception:
    permission_resolver = None

User = get_user_model()


class TenantViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gerenciamento de tenants (empresas).
    """

    serializer_class = TenantSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "razao_social", "cnpj", "cpf"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        """
        Controla qual lista de objetos é retornada.
        """
        # Se o usuário que faz a requisição for um superusuário...
        if self.request.user.is_superuser:
            # ...retorne TODAS as empresas, sem nenhum filtro.
            return Tenant.objects.all()

        # Para qualquer outro tipo de usuário, não retorna nada por segurança.
        return Tenant.objects.none()


class CustomUserViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gerenciamento de usuários.
    """

    queryset = User.objects.all().order_by("id")  # ordering explícito para paginação estável
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "date_joined", "is_active"]

    @action(detail=True, methods=["get"])
    def tenants(self, request, pk=None):
        """
        Retorna os tenants associados a um usuário específico.
        """
        user = self.get_object()
        tenant_users = TenantUser.objects.filter(user=user)
        serializer = TenantUserSerializer(tenant_users, many=True)
        return Response(serializer.data)


class TenantUserViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gerenciamento de vínculos usuário-tenant.
    """

    queryset = TenantUser.objects.all()
    serializer_class = TenantUserSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__username", "tenant__name"]
    ordering_fields = ["created_at"]


@api_view(["GET"])
def system_stats(request):
    """
    Retorna estatísticas do sistema.
    """
    if not request.user.is_authenticated:
        return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    # TODO: Implementar a lógica real para obter as estatísticas
    data = {
        "cpu_usage": 0,
        "memory_usage": 0,
        "disk_usage": 0,
        "online_users": 0,
    }
    return Response(data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def get_dashboard_metrics(request):
    """
    Fornece dados de métricas para o dashboard principal.
    """
    # TODO: Substituir por dados reais do banco de dados
    data = {
        "key_metrics": [
            {
                "label": "Novos Clientes",
                "value": 12,
                "change": "+5%",
                "change_type": "positive",
                "icon": "fas fa-users",
            },
            {
                "label": "Vendas (Mês)",
                "value": "R$ 45.230",
                "change": "+12%",
                "change_type": "positive",
                "icon": "fas fa-money-bill-wave",
            },
            {"label": "Projetos Ativos", "value": 8, "change": "-2", "change_type": "negative", "icon": "fas fa-tools"},
            {
                "label": "Taxa de Conclusão",
                "value": "92%",
                "change": "+1.5%",
                "change_type": "positive",
                "icon": "fas fa-check-circle",
            },
        ],
        "revenue_chart": {
            "labels": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun"],
            "datasets": [
                {
                    "label": "Receita",
                    "data": [12000, 19000, 15000, 21000, 18000, 25000],
                    "backgroundColor": "rgba(75, 192, 192, 0.6)",
                },
                {
                    "label": "Despesas",
                    "data": [8000, 9500, 11000, 10500, 12000, 13000],
                    "backgroundColor": "rgba(255, 99, 132, 0.6)",
                },
            ],
        },
        "sales_categories": [
            {"name": "Serviços", "percentage": 60, "color": "#36A2EB"},
            {"name": "Produtos", "percentage": 30, "color": "#FFCE56"},
            {"name": "Manutenção", "percentage": 10, "color": "#FF6384"},
        ],
        "recent_activities": [
            {"user": {"name": "Ana"}, "description": "cadastrou um novo cliente.", "timestamp": "2 horas atrás"},
            {"user": {"name": "Carlos"}, "description": "finalizou o projeto 'Alpha'.", "timestamp": "5 horas atrás"},
            {"user": {"name": "Mariana"}, "description": "atualizou o orçamento #2024-058.", "timestamp": "ontem"},
        ],
    }
    return Response(data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dashboard_metrics(request):
    """
    API endpoint para métricas do dashboard
    """
    try:
        # Métricas básicas do sistema
        metrics = {
            "total_tenants": Tenant.objects.filter(status="active").count(),
            "total_users": User.objects.filter(is_active=True).count(),
            "current_tenant": None,
            "user_permissions": [],
            "system_status": "online",
            "timestamp": timezone.now().isoformat(),
        }

        # Se há um tenant atual, adicionar informações específicas
        current_tenant = getattr(request, "tenant", None)
        if current_tenant:
            metrics["current_tenant"] = {
                "id": current_tenant.id,
                "name": current_tenant.name,
                "status": current_tenant.status,
            }

        return Response(metrics)
    except Exception as e:
        return Response(
            {"error": "Erro ao carregar métricas", "detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def api_tenant_list(request):
    """Lista tenants (superuser vê todos, usuário normal vazio para manter testes de forbidden)."""
    qs = Tenant.objects.all() if request.user.is_superuser else Tenant.objects.none()
    data = [{"id": t.id, "name": t.name, "status": t.status} for t in qs]
    status_code = 200 if request.user.is_superuser else 403
    return Response(data if status_code == 200 else {"detail": "Forbidden"}, status=status_code)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def api_tenant_create(request):
    """Cria tenant (apenas superuser)."""
    if not request.user.is_superuser:
        return Response({"detail": "Forbidden"}, status=403)
    name = request.data.get("name") or "Tenant Auto"
    subdomain = request.data.get("subdomain") or f"tenant-{timezone.now().timestamp():.0f}"
    tenant = Tenant.objects.create(name=name, subdomain=subdomain)
    return Response({"id": tenant.id, "name": tenant.name}, status=201)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def api_module_diagnostics(request):
    """Retorna status de cada módulo conhecido para (user, tenant atual).

    Estrutura:
    [{"module": "clientes", "enabled": true/false, "decision_reason": "OK|...", "allowed": bool}]
    Só superuser pode ver todos os módulos; usuário normal vê apenas módulos habilitados no tenant (ou vazios se sem tenant).
    """
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        # Fallback: tentar resolver via sessão (middleware pode não ter rodado em teste)
        try:
            tenant = get_current_tenant(request)
        except Exception:
            tenant = None
    modules_cfg = getattr(settings, "PANDORA_MODULES", [])
    modules = []
    for item in modules_cfg:
        if isinstance(item, dict) and item.get("module_name") and not item.get("is_header"):
            modules.append(item["module_name"])
    modules = sorted(set(modules))
    out = []
    for m in modules:
        enabled_flag = False
        try:
            enabled_flag = tenant.is_module_enabled(m) if tenant else False
        except Exception:
            enabled_flag = False
        decision_reason = None
        allowed = False
        if getattr(settings, "FEATURE_UNIFIED_ACCESS", False) and can_access_module:
            dec = can_access_module(request.user, tenant, m)
            decision_reason = dec.reason
            allowed = dec.allowed
        else:
            # modo legado: allowed segue enabled
            allowed = enabled_flag and tenant is not None
            decision_reason = "LEGACY" if allowed else "LEGACY_DISABLED"
        # Visibilidade: superuser vê tudo; normal só vê enabled ou denied se unified_access (para debug UI pode ser filtrado pela camada cliente)
        if request.user.is_superuser or getattr(settings, "FEATURE_UNIFIED_ACCESS", False) or enabled_flag:
            out.append(
                {
                    "module": m,
                    "enabled_for_tenant": enabled_flag,
                    "allowed": allowed,
                    "reason": decision_reason,
                }
            )
    return Response({"tenant_id": getattr(tenant, "id", None), "count": len(out), "modules": out})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def api_permission_cache_inspect(request):
    """Inspeciona chaves de cache do permission_resolver para o (user, tenant atual).

    Retorna versão ativa e lista de possíveis keys para ações VIEW_<MODULE> (não força resolução).
    Apenas superuser; outros recebem 403.
    """
    if not request.user.is_superuser:
        return Response({"detail": "Forbidden"}, status=403)
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        try:
            tenant = get_current_tenant(request)
        except Exception:
            tenant = None
    if not tenant:
        return Response({"error": "No tenant resolved"}, status=400)
    if not permission_resolver:
        return Response({"error": "Resolver unavailable"}, status=503)
    # Ações base (VIEW_<MODULE>)
    modules_cfg = getattr(settings, "PANDORA_MODULES", [])
    modules = [
        m["module_name"] for m in modules_cfg if isinstance(m, dict) and m.get("module_name") and not m.get("is_header")
    ]
    version = permission_resolver._get_version(request.user.id, tenant.id)
    keys = [
        permission_resolver._get_cache_key(request.user.id, tenant.id, f"VIEW_{m.upper()}")
        for m in sorted(set(modules))
    ]
    return Response({"tenant_id": tenant.id, "user_id": request.user.id, "version": version, "potential_keys": keys})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def api_switch_tenant(request, tenant_id: int):
    """Altera tenant ativo na sessão para testes."""
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return Response({"detail": "Not found"}, status=404)
    request.session["tenant_id"] = tenant.id
    return Response({"detail": "tenant switched", "tenant_id": tenant.id})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def api_cargo_suggestions(request):
    """Sugestões de cargos: mistura catálogo estático e os mais usados no tenant.

    Params:
    - q: filtro opcional (case-insensitive)
    - limit: quantidade (default 15)
    """
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        try:
            tenant = get_current_tenant(request)
        except Exception:
            tenant = None
    q = (request.GET.get("q") or "").strip().lower()
    try:
        limit = int(request.GET.get("limit") or 15)
    except Exception:
        limit = 15

    # Catálogo base
    base = list(CARGO_CATALOGO)
    if q:
        base = [c for c in base if q in c.lower()]

    # Mais usados no tenant (ignorando vazios)
    used = []
    if tenant:
        used_qs = (
            TenantUser.objects.filter(tenant=tenant)
            .exclude(cargo__isnull=True)
            .exclude(cargo__exact="")
            .values("cargo")
            .annotate(cnt=Count("cargo"))
            .order_by("-cnt")[:limit]
        )
        used = [normalizar_cargo(u["cargo"]) or u["cargo"] for u in used_qs]

    # Merge preservando ordem (usados primeiro), removendo duplicados case-insensitive
    seen = set()
    out = []

    def add(item):
        if not item:
            return
        key = item.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(item)

    for it in used:
        add(it)
    for it in base:
        add(it)

    if q:
        out = [s for s in out if q in s.lower()]

    return Response({"results": out[:limit]})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def api_departments_list(request):
    """Lista departamentos para seleção dinâmica de cargos.

    Query params:
      - tenant: id opcional do tenant; se vazio retorna somente globais.
      - include_globals: 'true' (default) para incluir globais junto com específicos.
    """
    from .models import Department

    tenant_id = request.GET.get("tenant") or ""
    include_globals = request.GET.get("include_globals", "true").lower() in ("1", "true", "yes")
    qs = Department.objects.all()
    if tenant_id:
        qs = qs.filter(Q(tenant_id=tenant_id) | (Q(tenant__isnull=True) if include_globals else Q(pk__lt=0)))
    else:
        # sem tenant -> só globais (ou tudo se explicito include_globals=false?)
        qs = qs.filter(tenant__isnull=True)
    qs = qs.order_by("tenant__name", "name")
    data = []
    for d in qs:
        data.append(
            {
                "id": d.id,
                "name": d.name,
                "tenant_id": d.tenant_id,
                "tenant_name": d.tenant.name if d.tenant_id else None,
                "label": f"{d.name} ({d.tenant.name})" if d.tenant_id else f"{d.name} (Global)",
            }
        )
    return Response({"results": data})
