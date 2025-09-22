# pandora_erp/settings.py

"""Django settings for pandora_erp project."""

from __future__ import annotations

import os
import warnings
from datetime import timedelta
from pathlib import Path

import core.monkeypatches  # noqa: F401  # aplica monkeypatches globais cedo

BASE_DIR = Path(__file__).resolve().parent.parent

FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = (
    os.environ.get("FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT", "False") == "True"
)

# =============================
# 2FA / SEGURANÇA (CONSTANTES)
TWOFA_LOCK_THRESHOLD = int(os.environ.get("TWOFA_LOCK_THRESHOLD", "5"))
TWOFA_LOCK_MINUTES = int(os.environ.get("TWOFA_LOCK_MINUTES", "5"))
TWOFA_RATE_LIMIT_ATTEMPTS = int(os.environ.get("TWOFA_RATE_LIMIT_ATTEMPTS", "10"))
TWOFA_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("TWOFA_RATE_LIMIT_WINDOW_SECONDS", "60"))
TWOFA_ALERT_THRESHOLDS = tuple(int(x) for x in os.environ.get("TWOFA_ALERT_THRESHOLDS", "20,50,100").split(","))
TWOFA_ALERT_EMAIL_COOLDOWN_MINUTES = int(os.environ.get("TWOFA_ALERT_EMAIL_COOLDOWN_MINUTES", "30"))
TWOFA_FERNET_KEYS = [s for s in os.environ.get("TWOFA_FERNET_KEYS", "").split(",") if s.strip()] or None
TWOFA_RECOVERY_PEPPER = os.environ.get("TWOFA_RECOVERY_PEPPER", "")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-key-for-development-only")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
TESTING = bool(os.environ.get("PYTEST_CURRENT_TEST"))


ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "https://8000-i881injdm9bubmu7elb87-5ff893a2.manusvm.computer",
    "*",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://8000-i881injdm9bubmu7elb87-5ff893a2.manusvm.computer",
]

INSTALLED_APPS = [
    # Aplicação ASGI em primeiro lugar
    "daphne",
    # Aplicações do Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Aplicações de terceiros
    "django_extensions",
    "crispy_forms",
    "crispy_bootstrap5",
    "widget_tweaks",
    "guardian",
    "rest_framework",
    "drf_yasg",
    "corsheaders",
    "django_tables2",
    "django_filters",
    "channels",
    # Suas aplicações (Pandora ERP) - CORRIGIDO SEM DUPLICAÇÕES
    "core.apps.CoreConfig",
    "admin.apps.AdminConfig",
    "user_management.apps.UserManagementConfig",
    "notifications.apps.NotificationsConfig",
    "clientes.apps.ClientesConfig",
    "obras.apps.ObrasConfig",
    "orcamentos.apps.OrcamentosConfig",
    "fornecedores.apps.FornecedoresConfig",
    "compras.apps.ComprasConfig",
    "financeiro.apps.FinanceiroConfig",
    "estoque.apps.EstoqueConfig",
    "apropriacao.apps.ApropriacaoConfig",
    "aprovacoes.apps.AprovacoesConfig",
    "mao_obra.apps.MaoObraConfig",
    "funcionarios.apps.FuncionariosConfig",
    "relatorios.apps.RelatoriosConfig",
    "bi.apps.BiConfig",
    "servicos.apps.ServicosConfig",
    "chat.apps.ChatConfig",
    "treinamento.apps.TreinamentoConfig",
    "sst.apps.SstConfig",
    "formularios.apps.FormulariosConfig",
    "produtos.apps.ProdutosConfig",
    "prontuarios.apps.ProntuariosConfig",
    "formularios_dinamicos.apps.FormulariosDinamicosConfig",
    "assistente_web.apps.AssistenteWebConfig",
    "cotacoes.apps.CotacoesConfig",
    "portal_fornecedor.apps.PortalFornecedorConfig",
    "portal_cliente.apps.PortalClienteConfig",
    # Novo módulo de agendamentos (extraído de prontuários - fase de transição)
    "agendamentos.apps.AgendamentosConfig",
    # Módulos sem apps.py (formato simples)
    "agenda",
    "cadastros_gerais",
    "quantificacao_obras",
    "ai_auditor",
    "documentos",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Enforcement 2FA (após autenticação, antes de tenant / módulo)
    "user_management.middleware_twofa.TwoFAMiddleware",
    "core.middleware_session_inactivity.SessionInactivityMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.TenantMiddleware",
    "core.middleware.ModuleAccessMiddleware",
    "core.middleware.UserActivityMiddleware",
    "core.middleware.AuditLogMiddleware",
    "core.middleware_latency.RequestLatencyMiddleware",
    "portal_cliente.middleware.PortalRequestIDMiddleware",
]

ROOT_URLCONF = "pandora_erp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.tenant_context",
            ],
            "builtins": [
                "core.templatetags.menu_tags",
            ],
        },
    },
]

WSGI_APPLICATION = "pandora_erp.wsgi.application"
ASGI_APPLICATION = "pandora_erp.asgi.application"

REDIS_URL = os.environ.get("REDIS_URL") or os.environ.get("REDIS_HOST")
if REDIS_URL:
    # Permitir formatos: redis://host:port/0 ou apenas host
    if not REDIS_URL.startswith("redis://"):
        host = REDIS_URL
        port = os.environ.get("REDIS_PORT", "6379")
        REDIS_URL = f"redis://{host}:{port}/0"
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        },
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 30,
        },
    },
}

# Configuração específica para habilitar foreign keys no SQLite
engine_val = DATABASES["default"].get("ENGINE")
if isinstance(engine_val, str) and "sqlite" in engine_val:
    import sqlite3

    # Registrar função para habilitar foreign keys automaticamente
    def enable_foreign_keys(connection: sqlite3.Connection, **_kwargs: object) -> None:
        """Enable SQLite foreign keys pragma when using sqlite backend."""
        if isinstance(connection, sqlite3.Connection):
            connection.execute("PRAGMA foreign_keys = ON;")

    from django.db.backends.signals import connection_created

    connection_created.connect(enable_foreign_keys)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = (
    # Subclasse de ModelBackend: inclui permissões e autenticação com bloqueio
    "user_management.auth_backends.PerfilStatusAuthenticationBackend",
    # permissões por objeto
    "guardian.backends.ObjectPermissionBackend",
)
# (UNIFICADO) Whitelist de módulos permitidos para usuários de portal.
# A definição canônica passa a ser somente a do bloco de AUTORIZAÇÃO MODULAR (abaixo),
# evitando duplicidade/confusão. Mantida aqui apenas referência retrocompatível caso
# algum import antecipado leia antes do bloco final; será sobrescrita depois.
PORTAL_ALLOWED_MODULES = ["documentos", "notifications", "chat"]

# Tempo máximo de inatividade (minutos) para marcar sessão como expirada logicamente (SessaoUsuario.ativa=False)
SESSION_MAX_INACTIVITY_MINUTES = int(os.environ.get("SESSION_MAX_INACTIVITY_MINUTES", "120"))  # 2h default
AUTH_USER_MODEL = "core.CustomUser"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# ----------------------------------------------------------------------------
# Warnings Filters (redução de ruído deprecações conhecidas)
# ----------------------------------------------------------------------------
# DRF registra o converter 'drf_format_suffix' internamente; em alguns contextos
# de import duplicado (ex: reload de testes) o Django 5.2 emite um RemovedInDjango60Warning
# indicando que overrides serão removidos. Não há registro manual no projeto.
# Silenciamos apenas esta mensagem específica até migrar para Django 6 / DRF ajuste upstream.
try:  # pragma: no cover (ambiente de teste já importa)
    from django.utils import deprecation as _deprecation
except ImportError:  # pragma: no cover
    _deprecation = None

RemovedInDjango60Warning = getattr(_deprecation, "RemovedInDjango60Warning", Warning)
# Ajuste do filtro para abranger a frase completa (DRF acrescenta trecho extra)
warnings.filterwarnings(
    "ignore",
    message=r"Converter 'drf_format_suffix' is already registered.*",
    category=RemovedInDjango60Warning,
)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "core:login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "core:login"

# Para habilitar expiração lógica de sessões por inatividade, adicionar
# 'core.middleware_session_inactivity.SessionInactivityMiddleware' ao MIDDLEWARE (após autenticação).

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://localhost:5174",
]
CORS_ALLOW_ALL_ORIGINS = False
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# ---------------------------------------------------------------------------
# Hardening básico (ativo somente quando DEBUG=False)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
    # Cookies SameSite (pode ser ajustado se app expor em iframe interno)
    CSRF_COOKIE_SAMESITE = os.environ.get("CSRF_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}

SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Bearer": {"type": "apiKey", "name": "Authorization", "in": "header"},
    },
}
ANONYMOUS_USER_NAME = "AnonymousUser"
NOTIFICATIONS_EMAIL_SENDER = DEFAULT_FROM_EMAIL
NOTIFICATIONS_SMS_GATEWAY_API_KEY = os.environ.get("NOTIFICATIONS_SMS_GATEWAY_API_KEY", "")
NOTIFICATIONS_PUSH_VAPID_PRIVATE_KEY = os.environ.get("NOTIFICATIONS_PUSH_VAPID_PRIVATE_KEY", "")
NOTIFICATIONS_PUSH_VAPID_PUBLIC_KEY = os.environ.get("NOTIFICATIONS_PUSH_VAPID_PUBLIC_KEY", "")

# =============================
# OTIMIZAÇÕES EM AMBIENTE DE TESTE (pytest)
# Detecta via variável TESTING definida no topo (PYTEST_CURRENT_TEST) e em conftest.
if TESTING:
    # Hash de senha mais rápido para acelerar criação de usuários em massa nos testes.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # Desabilitar validadores de senha para evitar overhead desnecessário em testes.
    AUTH_PASSWORD_VALIDATORS = []
    # Evitar envio real / tentativa de conexão SMTP em testes.
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    # Simplificar logging de queries lentas/ruidosas (opcional futura expansão)
    # Garantir que tarefas async (Celery) sejam síncronas se vier a ser adicionado celery config.
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

NOTIFICATIONS_PUSH_VAPID_ADMIN_EMAIL = os.environ.get("NOTIFICATIONS_PUSH_VAPID_ADMIN_EMAIL", "")
ADMIN_METRICS_RETENTION_DAYS = int(os.environ.get("ADMIN_METRICS_RETENTION_DAYS", "90"))
ADMIN_AUDIT_LOG_RETENTION_DAYS = int(os.environ.get("ADMIN_AUDIT_LOG_RETENTION_DAYS", "365"))

# Feature Flags (somente flags específicas não duplicadas mais abaixo)
AGENDAMENTOS_ENABLED = os.environ.get("AGENDAMENTOS_ENABLED", "True") == "True"
# Portal Cliente flags
PORTAL_CLIENTE_AUTO_ENABLE_DEBUG = os.environ.get("PORTAL_CLIENTE_AUTO_ENABLE_DEBUG", "False") == "True"
# Flags específicas do módulo de agendamentos
USE_NOVO_AGENDAMENTO = os.environ.get("USE_NOVO_AGENDAMENTO", "True") == "True"
ENABLE_EVENT_MIRROR = os.environ.get("ENABLE_EVENT_MIRROR", "True") == "True"
AGENDAMENTOS_CANCEL_ANTECEDENCIA_MINUTOS = int(os.environ.get("AGENDAMENTOS_CANCEL_ANTECEDENCIA_MINUTOS", "120"))
AGENDAMENTOS_REAGENDAMENTO_CADEIA_MAX = int(os.environ.get("AGENDAMENTOS_REAGENDAMENTO_CADEIA_MAX", "5"))
ENABLE_CONTROLLED_OVERBOOK = os.environ.get("ENABLE_CONTROLLED_OVERBOOK", "False") == "True"
# URL externa para portal do cliente (opcional)
CLIENT_PORTAL_URL = os.environ.get("CLIENT_PORTAL_URL", None)
ENABLE_WAITLIST = os.environ.get("ENABLE_WAITLIST", "False") == "True"
AGENDAMENTOS_OVERBOOK_EXTRA = int(os.environ.get("AGENDAMENTOS_OVERBOOK_EXTRA", "1"))

# Assistente IA (voz) - desabilitado por padrão para evitar logs no startup
ASSISTANT_SPEECH_ENABLED = os.environ.get("ASSISTANT_SPEECH_ENABLED", "False") == "True"
ASSISTANT_TTS_ENABLED = os.environ.get("ASSISTANT_TTS_ENABLED", "False") == "True"
ASSISTANT_SPEECH_RATE = int(os.environ.get("ASSISTANT_SPEECH_RATE", "150"))

# Wizard Tenants - política de sessão em exceções (configurável por env var)
PRESERVE_WIZARD_SESSION_ON_EXCEPTION = os.environ.get("PRESERVE_WIZARD_SESSION_ON_EXCEPTION", "True") == "True"


# ==============================================================================
# ESTRUTURA DE MENU CORRIGIDA E UNIFICADA COM FUNCIONÁRIOS E CORE COMPLETO
# ==============================================================================
PANDORA_MODULES = [
    # NÍVEL 1: FERRAMENTAS DO SUPER ADMIN
    {"name": "PAINEL SUPER ADMIN", "is_header": True, "superuser_only": True},
    {
        "module_name": "core",
        "name": "Gerenciar Empresas",
        "icon": "fas fa-building",
        "url": "core:core_home",
        "superuser_only": True,
    },
    # NÍVEL 2: FERRAMENTAS DO ADMINISTRADOR DA EMPRESA
    {"name": "ADMINISTRAÇÃO DA EMPRESA", "is_header": True, "tenant_admin_only": True},
    {
        "module_name": "admin",
        "name": "Administração",
        "icon": "fas fa-shield-alt",
        "url": "administration:admin_home",
        "superuser_only": True,
    },
    # NÍVEL 2.5: RECURSOS HUMANOS COMPLETO
    {"name": "RECURSOS HUMANOS", "is_header": True},
    # Submenu de Funcionários simplificado para único botão apontando para a Home do módulo
    {
        "module_name": "funcionarios",
        "name": "Funcionários",
        "icon": "fas fa-user-friends",
        "url": "funcionarios:funcionarios_home",
    },
    # NÍVEL 3: CADASTROS BASE PARA A OPERAÇÃO
    {"name": "CADASTROS", "is_header": True},
    {"module_name": "clientes", "name": "Clientes", "icon": "fas fa-address-book", "url": "clientes:clientes_home"},
    {
        "module_name": "fornecedores",
        "name": "Fornecedores",
        "icon": "fas fa-truck",
        "url": "fornecedores:fornecedores_home",
    },
    # --- CORREÇÃO E DESMEMBRAMENTO APLICADOS AQUI ---
    {"module_name": "produtos", "name": "Produtos", "icon": "fas fa-box-open", "url": "produtos:produtos_home"},
    {"module_name": "servicos", "name": "Serviços", "icon": "fas fa-concierge-bell", "url": "servicos:servicos_home"},
    # --- FIM DA CORREÇÃO ---
    {
        "module_name": "cadastros_gerais",
        "name": "Cadastros Auxiliares",
        "icon": "fas fa-book",
        "url": "cadastros_gerais:cadastros_gerais_home",
    },
    # NÍVEL 4: OPERAÇÃO DO DIA A DIA
    {"name": "OPERAÇÕES", "is_header": True},
    {"module_name": "obras", "name": "Obras", "icon": "fas fa-hard-hat", "url": "obras:obras_home"},
    {
        "module_name": "quantificacao_obras",
        "name": "Quantificação de Obras",
        "icon": "fas fa-calculator",
        "children": [
            {"name": "Home Quantificação", "url": "quantificacao_obras:quantificacao_obras_home"},
            {"name": "Listar Projetos", "url": "quantificacao_obras:projeto_list"},
            {"name": "Novo Projeto", "url": "quantificacao_obras:projeto_create"},
        ],
    },
    {
        "module_name": "orcamentos",
        "name": "Orçamentos",
        "icon": "fas fa-file-invoice-dollar",
        "children": [
            {"name": "Home Orçamentos", "url": "orcamentos:orcamentos_home"},
            {"name": "Listar Orçamentos", "url": "orcamentos:orcamento_list"},
            {"name": "Novo Orçamento", "url": "orcamentos:orcamento_create"},
        ],
    },
    {
        "module_name": "mao_obra",
        "name": "Mão de Obra",
        "icon": "fas fa-user-hard-hat",
        "children": [
            {"name": "Home Mão de Obra", "url": "mao_obra:mao_obra_home"},
            {"name": "Listar Mão de Obra", "url": "mao_obra:mao_obra_list"},
            {"name": "Nova Mão de Obra", "url": "mao_obra:mao_obra_create"},
        ],
    },
    {
        "module_name": "compras",
        "name": "Compras",
        "icon": "fas fa-shopping-cart",
        "children": [
            {"name": "Home Compras", "url": "compras:compras_home"},
            {"name": "Listar Compras", "url": "compras:compras_list"},
            {"name": "Nova Compra", "url": "compras:compras_create"},
        ],
    },
    {
        "module_name": "apropriacao",
        "name": "Apropriação de Obras",
        "icon": "fas fa-clipboard-check",
        "children": [
            {"name": "Home Apropriação", "url": "apropriacao:apropriacao_home"},
            {"name": "Listar Apropriações", "url": "apropriacao:apropriacao_list"},
        ],
    },
    # NÍVEL 5: GESTÃO E ANÁLISE
    {"name": "GESTÃO", "is_header": True},
    {
        "module_name": "financeiro",
        "name": "Financeiro",
        "icon": "fas fa-dollar-sign",
        "children": [
            {"name": "Home Financeiro", "url": "financeiro:financeiro_home"},
            {"name": "Listar Lançamentos", "url": "financeiro:financeiro_list"},
        ],
    },
    {"module_name": "estoque", "name": "Estoque", "icon": "fas fa-warehouse", "url": "estoque:estoque_home"},
    {
        "module_name": "aprovacoes",
        "name": "Aprovações",
        "icon": "fas fa-thumbs-up",
        "children": [
            {"name": "Home Aprovações", "url": "aprovacoes:aprovacoes_home"},
            {"name": "Listar Aprovações", "url": "aprovacoes:aprovacoes_list"},
        ],
    },
    {
        "module_name": "relatorios",
        "name": "Relatórios",
        "icon": "fas fa-chart-pie",
        "children": [
            {"name": "Home Relatórios", "url": "relatorios:relatorios_home"},
            {"name": "Listar Relatórios", "url": "relatorios:relatorios_list"},
        ],
    },
    {
        "module_name": "bi",
        "name": "Business Intelligence",
        "icon": "fas fa-chart-bar",
        "children": [
            {"name": "Home BI", "url": "bi:bi_home"},
            {"name": "Relatórios Analíticos", "url": "bi:bi_reports"},
        ],
    },
    # NÍVEL 6: FERRAMENTAS DIVERSAS
    {"name": "FERRAMENTAS", "is_header": True},
    {"module_name": "agenda", "name": "Agenda", "icon": "far fa-calendar-alt", "url": "agenda:agenda_home"},
    # Novo módulo de agendamentos (fase beta). Condicionado à feature flag.
    *(
        [
            {
                "module_name": "agendamentos",
                "name": "Agendamentos (Beta)",
                "icon": "fas fa-calendar-check",
                "children": [
                    {"name": "Home Agendamentos", "url": "agendamentos:home"},
                    {"name": "Dashboard", "url": "agendamentos:dashboard"},
                    {"name": "Agendamentos", "url": "agendamentos:agendamento-list"},
                    {"name": "Slots", "url": "agendamentos:slot-list"},
                    {"name": "Disponibilidades", "url": "agendamentos:disponibilidade-list"},
                    {"name": "Waitlist", "url": "agendamentos:waitlist-list"},
                    {"name": "Auditoria", "url": "agendamentos:auditoria-list"},
                ],
            },
        ]
        if AGENDAMENTOS_ENABLED
        else []
    ),
    {"module_name": "chat", "name": "Chat Interno", "icon": "far fa-comments", "url": "chat:chat_home"},
    {"module_name": "documentos", "name": "Documentos", "icon": "fas fa-file-alt", "url": "documentos:documentos_home"},
    {
        "module_name": "notifications",
        "name": "Minhas Notificações",
        "icon": "far fa-bell",
        "children": [
            {"name": "Home Notificações", "url": "notifications:notifications_home"},
            {"name": "Listar Notificações", "url": "notifications:notification_list"},
        ],
    },
    {
        "module_name": "formularios",
        "name": "Formulários Customizados",
        "icon": "fab fa-wpforms",
        "children": [
            {"name": "Home Formulários", "url": "formularios:formularios_home"},
            {"name": "Listar Formulários", "url": "formularios:formularios_list"},
        ],
    },
    {
        "module_name": "formularios_dinamicos",
        "name": "Formulários Dinâmicos",
        "icon": "fas fa-file-alt",
        "children": [
            {"name": "Home Dinâmicos", "url": "formularios_dinamicos:formularios_dinamicos_home"},
            {"name": "Listar Formulários", "url": "formularios_dinamicos:form_list"},
        ],
    },
    {
        "module_name": "sst",
        "name": "SST",
        "icon": "fas fa-user-shield",
        "children": [
            {"name": "Home SST", "url": "sst:sst_home"},
            {"name": "Normas e Procedimentos", "url": "sst:normas_list"},
        ],
    },
    {
        "module_name": "treinamento",
        "name": "Treinamentos",
        "icon": "fas fa-chalkboard-teacher",
        "children": [
            {"name": "Home Treinamentos", "url": "treinamento:treinamento_home"},
            {"name": "Listar Treinamentos", "url": "treinamento:treinamentos_list"},
        ],
    },
    {
        "module_name": "ai_auditor",
        "name": "Agente de IA",
        "icon": "fas fa-robot",
        "children": [
            {"name": "Home IA", "url": "ai_auditor:ai_auditor_home"},
            {"name": "Análises", "url": "ai_auditor:dashboard"},
        ],
    },
    {
        "module_name": "assistente_web",
        "name": "Assistente IA",
        "icon": "fas fa-brain",
        "children": [
            {"name": "Chat com Assistente", "url": "assistente_web:home"},
            {"name": "Configurações", "url": "assistente_web:configuracoes"},
            {"name": "Histórico", "url": "assistente_web:historico"},
        ],
    },
    {
        "module_name": "user_management",
        "name": "Gerenciamento de Usuários",
        "icon": "fas fa-users",
        "children": [
            {"name": "Home Usuários", "url": "user_management:user_management_home"},
            {"name": "Listar Usuários", "url": "user_management:usuario_list"},
        ],
    },
    # NÍVEL 7: MÓDULOS DE SAÚDE
    {"name": "SAÚDE", "is_header": True},
    # Prontuários expandido (evita necessidade de partial manual separado)
    {
        "module_name": "prontuarios",
        "name": "Prontuários",
        "icon": "fas fa-notes-medical",
        "children": [
            {"name": "Home Prontuários", "url": "prontuarios:home"},
            {"name": "Atendimentos", "url": "prontuarios:atendimentos_list"},
            {"name": "Serviços Clínicos", "url": "servicos:servico_list"},
            {"name": "Anamneses", "url": "prontuarios:anamneses_list"},
            {"name": "Perfis Clínicos", "url": "prontuarios:perfils_clinicos_list"},
            {"name": "Fotos Evolução", "url": "prontuarios:fotos_evolucao_list"},
            {"name": "Disponibilidades", "url": "prontuarios:disponibilidades_list"},
            {"name": "Slots", "url": "prontuarios:slots_list"},
        ],
    },
]

# Adicionar configurações específicas do módulo (opcional)
# Tamanho máximo para upload de imagens (em bytes)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Configurações de processamento de imagem
PRONTUARIOS_IMAGE_MAX_WIDTH = 1920
PRONTUARIOS_IMAGE_MAX_HEIGHT = 1080
PRONTUARIOS_IMAGE_QUALITY = 85

# Configurações de backup automático
PRONTUARIOS_BACKUP_RETENTION_DAYS = 90
PRONTUARIOS_AUTO_BACKUP_ENABLED = True

STATIC_ROOT = BASE_DIR / "staticfiles"

# ============================================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================================

# Configurações de cookies seguros
CSRF_COOKIE_SECURE = not DEBUG  # Seguro apenas em produção (HTTPS)
SESSION_COOKIE_SECURE = not DEBUG  # Seguro apenas em produção (HTTPS)

# Configurações de HTTPS (apenas para produção)
SECURE_SSL_REDIRECT = False  # Manter False em desenvolvimento
SECURE_HSTS_SECONDS = 0  # Desabilitado em desenvolvimento
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Em produção, habilitar segurança HTTPS
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Proteção adicional (sempre ativa)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Configuração de SECRET_KEY mais robusta
if not DEBUG and SECRET_KEY.startswith("django-insecure-"):
    import warnings

    warnings.warn(
        "ATENÇÃO: Usando SECRET_KEY insegura em produção! Configure a variável de ambiente DJANGO_SECRET_KEY.",
        RuntimeWarning,
        stacklevel=2,
    )

# Logging estruturado opcional
if os.environ.get("STRUCTURED_LOG_JSON", "False") == "True":
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "django.utils.log.ServerFormatter",
                "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        },
        "loggers": {
            "": {"handlers": ["console"], "level": "INFO"},
            "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        },
    }


"""
=============================================================================
CELERY / TAREFAS ASSÍNCRONAS
=============================================================================
Configuração central do Celery. Usa Redis como broker/result backend quando
REDIS_URL está definido. Em desenvolvimento (sem Redis) cai para um broker
em memória (apenas para testes simples; não usar em produção).
"""

# Broker/Backend
if REDIS_URL:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
else:
    # Fallback inseguro e não persistente - apenas para desenvolvimento rápido
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "rpc://"

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_ENABLE_UTC = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TIME_LIMIT = 60 * 5  # 5 minutos hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 4  # 4 minutos soft
CELERY_TASK_ACKS_LATE = True  # Permite reentrega se worker cai
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Evita retenção excessiva de tasks
CELERY_TASK_DEFAULT_QUEUE = "default"

# Roteamento (pode ser expandido quando houver filas específicas de mídia)
CELERY_TASK_ROUTES = {
    "prontuarios.tasks.gerar_thumbnail_foto": {"queue": "media"},
    "prontuarios.tasks.gerar_variacao_webp": {"queue": "media"},
    "prontuarios.tasks.processar_imagens_lote": {"queue": "media"},
    "prontuarios.tasks.extrair_video_poster": {"queue": "video"},
    "prontuarios.tasks.validar_video": {"queue": "video"},
    "prontuarios.tasks.transcodificar_video": {"queue": "video"},
    "prontuarios.tasks.reprocessar_derivados_foto": {"queue": "media"},
}

# Agendamentos periódicos (Celery Beat)
CELERY_BEAT_SCHEDULE = {
    "limpeza-arquivos-temporarios-semanal": {
        "task": "prontuarios.tasks.limpar_arquivos_temporarios",
        "schedule": timedelta(days=7),
    },
    "verificar-atendimentos-pendentes-diario": {
        "task": "prontuarios.tasks.verificar_atendimentos_pendentes",
        "schedule": timedelta(days=1),
    },
    # No-show automático para agendamentos (a cada 30 minutos)
    "agendamentos-no-show": {
        "task": "agendamentos.tasks.marcar_no_show_agendamentos",
        "schedule": timedelta(minutes=30),
    },
    # Backup automático diário (condicional via flag)
    "backup-automatico-diario": {
        "task": "prontuarios.tasks.executar_backup_automatico_tenants",
        "schedule": timedelta(days=1),
    },
    # Manutenção de perfis / sessões (ativada por flag)
    **(
        {
            "user_mgmt-desbloquear-usuarios": {
                "task": "user_management.tasks.desbloquear_usuarios_periodico",
                "schedule": timedelta(minutes=30),
            },
            "user_mgmt-limpar-sessoes-expiradas": {
                "task": "user_management.tasks.limpar_sessoes_expiradas_periodico",
                "schedule": timedelta(minutes=30),
            },
            "user_mgmt-limpar-logs-antigos": {
                "task": "user_management.tasks.limpar_logs_antigos_periodico",
                "schedule": timedelta(hours=24),
            },
        }
        if os.environ.get("ENABLE_USER_MGMT_MAINTENANCE", "True") == "True"
        else {}
    ),
}

# Flag para desabilitar agendamentos em certos ambientes (ex: testes)
CELERY_BEAT_DISABLE = os.environ.get("CELERY_BEAT_DISABLE", "False") == "True"
if CELERY_BEAT_DISABLE:
    CELERY_BEAT_SCHEDULE = {}

# ===========================================================================
# AUTORIZAÇÃO MODULAR (FEATURE FLAGS E CONFIG) - sempre definido (fora de if)
# ===========================================================================
# --- AUTORIZAÇÃO MODULAR (DEFINIÇÕES CANÔNICAS ÚNICAS) ---
PORTAL_USER_GROUP_NAME = os.environ.get("PORTAL_USER_GROUP_NAME", "PortalUser")
FEATURE_UNIFIED_ACCESS = os.environ.get("FEATURE_UNIFIED_ACCESS", "True") == "True"
FEATURE_REMOVE_MENU_HARDCODE = (
    os.environ.get("FEATURE_REMOVE_MENU_HARDCODE", "True") == "True"
)  # (LEGADO) manter até remoção definitiva da flag
FEATURE_STRICT_ENABLED_MODULES = os.environ.get("FEATURE_STRICT_ENABLED_MODULES", "False") == "True"
FEATURE_LOG_MODULE_DENIALS = os.environ.get("FEATURE_LOG_MODULE_DENIALS", "True") == "True"
TWOFA_ENCRYPT_SECRETS = (
    os.environ.get("TWOFA_ENCRYPT_SECRETS", "False") == "True"
)  # default False para retrocompatibilidade
FEATURE_MODULE_DENY_403 = (
    os.environ.get("FEATURE_MODULE_DENY_403", "False") == "True"
)  # se True, retorna 403 em vez de redirect
FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT = (
    os.environ.get("FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT", "False") == "True"
)

# Whitelist portal consolidada (env var tem prioridade; fallback lista padrão)
_portal_env = os.environ.get("PORTAL_ALLOWED_MODULES")
if _portal_env:
    PORTAL_ALLOWED_MODULES = [m.strip() for m in _portal_env.split(",") if m.strip()]
# Caso contrário mantém a lista já definida no topo (unificação)
