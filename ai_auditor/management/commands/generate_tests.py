from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_auditor.generators.test_generator import TestGenerator
from ai_auditor.models import AuditSession, GeneratedTest


class Command(BaseCommand):
    help = "Gera testes unitários para models, views, forms ou APIs."

    def add_arguments(self, parser):
        parser.add_argument("--tenant_id", type=int, help="ID do Tenant para gerar os testes.")
        parser.add_argument("--app_name", type=str, help="Nome do app para o qual gerar testes.")
        parser.add_argument(
            "--model_name", type=str, nargs="?", default=None, help="Nome do modelo para o qual gerar testes."
        )
        parser.add_argument(
            "--view_name", type=str, nargs="?", default=None, help="Nome da view para a qual gerar testes."
        )
        parser.add_argument(
            "--form_name", type=str, nargs="?", default=None, help="Nome do formulário para o qual gerar testes."
        )
        parser.add_argument(
            "--api_name", type=str, nargs="?", default=None, help="Nome da API para a qual gerar testes."
        )

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        app_name = options.get("app_name")
        model_name = options.get("model_name")
        view_name = options.get("view_name")
        form_name = options.get("form_name")
        api_name = options.get("api_name")

        if not tenant_id or not app_name:
            raise CommandError("Os argumentos --tenant_id e --app_name são obrigatórios.")

        try:
            tenant = apps.get_model("core", "Tenant").objects.get(id=tenant_id)
        except apps.get_model("core", "Tenant").DoesNotExist:
            raise CommandError(f"Tenant com ID {tenant_id} não encontrado.")

        self.stdout.write(
            self.style.SUCCESS(f"Iniciando geração de testes para o app {app_name} no Tenant: {tenant.name}")
        )

        session = AuditSession.objects.create(
            tenant=tenant,
            status="running",
            analysis_config={
                "action": "generate_tests",
                "app_name": app_name,
                "model_name": model_name,
                "view_name": view_name,
                "form_name": form_name,
                "api_name": api_name,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Sessão de Auditoria criada: {session.id}"))

        test_generator = TestGenerator(tenant, session)
        generated_count = 0

        if model_name:
            try:
                test_code = test_generator.generate_model_tests(app_name, model_name)
                GeneratedTest.objects.create(
                    session=session,
                    app_name=app_name,
                    model_name=model_name,
                    test_type="model",
                    test_file_path=f"ai_auditor/tests/test_{app_name}_{model_name.lower()}.py",
                    test_code=test_code,
                )
                self.stdout.write(self.style.SUCCESS(f"Testes para o modelo {model_name} gerados com sucesso."))
                generated_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao gerar testes para o modelo {model_name}: {e}"))

        if view_name:
            try:
                test_code = test_generator.generate_view_tests(app_name, view_name)
                GeneratedTest.objects.create(
                    session=session,
                    app_name=app_name,
                    test_type="view",
                    test_file_path=f"ai_auditor/tests/test_{app_name}_{view_name.lower()}_views.py",
                    test_code=test_code,
                )
                self.stdout.write(self.style.SUCCESS(f"Testes para a view {view_name} gerados com sucesso."))
                generated_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao gerar testes para a view {view_name}: {e}"))

        if form_name:
            try:
                test_code = test_generator.generate_form_tests(app_name, form_name)
                GeneratedTest.objects.create(
                    session=session,
                    app_name=app_name,
                    test_type="form",
                    test_file_path=f"ai_auditor/tests/test_{app_name}_{form_name.lower()}_forms.py",
                    test_code=test_code,
                )
                self.stdout.write(self.style.SUCCESS(f"Testes para o formulário {form_name} gerados com sucesso."))
                generated_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao gerar testes para o formulário {form_name}: {e}"))

        if api_name:
            try:
                test_code = test_generator.generate_api_tests(app_name, api_name)
                GeneratedTest.objects.create(
                    session=session,
                    app_name=app_name,
                    test_type="api",
                    test_file_path=f"ai_auditor/tests/test_{app_name}_{api_name.lower()}_api.py",
                    test_code=test_code,
                )
                self.stdout.write(self.style.SUCCESS(f"Testes para a API {api_name} gerados com sucesso."))
                generated_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao gerar testes para a API {api_name}: {e}"))

        session.tests_generated = generated_count
        session.status = "completed"
        session.completed_at = timezone.now()
        session.save()

        self.stdout.write(
            self.style.SUCCESS(f"Geração de testes finalizada. Total de testes gerados: {generated_count}")
        )
