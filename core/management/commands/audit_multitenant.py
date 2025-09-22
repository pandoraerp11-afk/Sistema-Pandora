import inspect

from django.apps import apps
from django.core.management.base import BaseCommand
from django.views import View

# Importar mixins de segurança conhecidos
from core.mixins import SuperuserRequiredMixin, TenantAdminOrSuperuserMixin, TenantRequiredMixin

# Lista de apps a serem ignorados na auditoria
IGNORED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "debug_toolbar",
    "rest_framework",
    "django_filters",
    "django_tables2",
    # Adicione outros apps de terceiros ou internos que não precisam de auditoria
    "core",  # O próprio core não precisa ter tenant em todos os modelos
]

# Lista de mixins de segurança que estamos procurando
SECURITY_MIXINS = {
    TenantRequiredMixin,
    TenantAdminOrSuperuserMixin,
    SuperuserRequiredMixin,
    # Adicione aqui outros mixins de segurança personalizados se houver
}


class Command(BaseCommand):
    help = "Audita modelos e views para garantir a conformidade com as regras multi-tenant."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Iniciando Auditoria Multi-Tenant ---"))

        self.audit_models()
        self.audit_views()

        self.stdout.write(self.style.SUCCESS("--- Auditoria Concluída ---"))

    def audit_models(self):
        self.stdout.write(self.style.HTTP_INFO("\n[+] Auditando Modelos..."))

        app_configs = apps.get_app_configs()
        for app_config in app_configs:
            if app_config.name in IGNORED_APPS:
                continue

            self.stdout.write(self.style.SQL_TABLE(f"  App: {app_config.name}"))
            models = app_config.get_models()
            if not models:
                self.stdout.write("    - Nenhum modelo encontrado.")
                continue

            for model in models:
                has_tenant_field = hasattr(model, "_meta") and "tenant" in [f.name for f in model._meta.get_fields()]

                if has_tenant_field:
                    self.stdout.write(self.style.SUCCESS(f'    - {model.__name__}: OK (possui campo "tenant")'))
                else:
                    self.stdout.write(
                        self.style.WARNING(f'    - {model.__name__}: ATENÇÃO (não possui campo "tenant")')
                    )

    def audit_views(self):
        self.stdout.write(self.style.HTTP_INFO("\n[+] Auditando Views (CBVs)..."))

        app_configs = apps.get_app_configs()
        for app_config in app_configs:
            if app_config.name in IGNORED_APPS:
                continue

            self.stdout.write(self.style.SQL_TABLE(f"  App: {app_config.name}"))
            try:
                views_module = __import__(f"{app_config.name}.views", fromlist=["*"])
                found_views = False
                for name, obj in inspect.getmembers(views_module):
                    if inspect.isclass(obj) and issubclass(obj, View) and obj.__module__ == views_module.__name__:
                        found_views = True
                        # Verificar se a view herda de algum dos mixins de segurança
                        has_security_mixin = any(issubclass(obj, mixin) for mixin in SECURITY_MIXINS)

                        if has_security_mixin:
                            self.stdout.write(self.style.SUCCESS(f"    - {name}: OK (possui mixin de segurança)"))
                        else:
                            self.stdout.write(
                                self.style.WARNING(f"    - {name}: ATENÇÃO (não possui mixin de segurança)")
                            )

                if not found_views:
                    self.stdout.write("    - Nenhuma CBV encontrada.")

            except ImportError:
                self.stdout.write("    - Módulo de views não encontrado.")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    - Erro ao auditar views: {e}"))
