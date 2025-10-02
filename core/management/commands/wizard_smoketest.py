"""Comando de smoke test para o Tenant Wizard.

Executa o fluxo mínimo de criação de um tenant em memória simulando todos os steps
relevantes até o finish_wizard, validando:
 - Normalização de módulos + aliases;
 - Criação de admins com geração automática de senha;
 - Subdomínio único;
 - Integridade geral.

Uso:
  python manage.py wizard_smoketest --subdomain testealias --with-admins
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand, CommandError
from django.test.client import RequestFactory

from core.models import CustomUser
from core.services.wizard_context import WizardContext
from core.wizard_views import STEP_CONFIG, TenantCreationWizardView

User = get_user_model()


@dataclass
class StepDataBundle:
    """Estrutura agregando os blocos simulados de cada step necessário.

    Mantemos somente os steps realmente consultados durante a consolidação.
    """

    step_1: dict[str, Any]
    step_2: dict[str, Any]
    step_3: dict[str, Any]
    step_5: dict[str, Any]
    step_6: dict[str, Any]


class Command(BaseCommand):
    """Management command para simular criação completa de Tenant pelo wizard.

    Útil para validar rapidamente se o fluxo consolidado continua íntegro
    após refatorações sem depender da interface web.
    """

    help = "Smoke test programático do wizard de criação de Tenant"

    HTTP_ERROR_THRESHOLD = 400

    class _ParserProto(Protocol):  # pragma: no cover - tipagem auxiliar
        def add_argument(self, *args: object, **kwargs: object) -> object: ...

    def add_arguments(self, parser: _ParserProto) -> None:  # parser: ArgumentParser compat
        """Adicionar argumentos de linha de comando."""
        parser.add_argument("--subdomain", required=True, help="Subdomínio para o tenant de teste")
        parser.add_argument("--name", default="Empresa Demo", help="Nome fantasia")
        parser.add_argument(
            "--with-admins",
            action="store_true",
            help="Inclui dois admins simulados com geração automática de senha",
        )

    def handle(self, **options: str) -> None:
        """Executar smoke test construindo dados de sessão e chamando finish."""
        sub = str(options["subdomain"]).strip()
        name = str(options["name"]).strip()
        with_admins = bool(options.get("with_admins"))

        if not sub:
            msg = "Subdomínio não pode ser vazio"
            raise CommandError(msg)

        # Garantir superusuário
        su, _ = User.objects.get_or_create(
            username="wizard_smoke_root",
            defaults={
                "email": "wizard_smoke_root@example.com",
                "is_superuser": True,
                "is_staff": True,
            },
        )
        if not su.has_usable_password():  # pragma: no cover
            su.set_password("Temp123!wizard")
            su.save(update_fields=["password"])

        factory = RequestFactory()
        request = factory.post("/core/wizard/")
        request.user = su
        session = SessionStore()
        session.create()
        request.session = session

        bundle = self._build_steps_bundle(name=name, subdomain=sub, with_admins=with_admins)
        wizard_data: dict[str, Any] = {
            "step_1": bundle.step_1,
            "step_2": bundle.step_2,
            "step_3": bundle.step_3,
            "step_5": bundle.step_5,
        }
        if with_admins:
            wizard_data["step_6"] = bundle.step_6

        request.session["tenant_wizard_data"] = wizard_data
        request.session.save()

        view = TenantCreationWizardView()
        view.setup(request)
        view.set_current_step(STEP_CONFIG)

        ctx = WizardContext(raw=wizard_data, is_editing=False, editing_tenant=None)
        if not view.validate_wizard_data_integrity(ctx):
            msg = "Falha na integridade dos dados antes do finish (fallback ou dados incompletos)"
            raise CommandError(msg)

        response = view.finish_wizard()
        status = getattr(response, "status_code", None)
        if status and status >= self.HTTP_ERROR_THRESHOLD:
            msg = f"Finish retornou status inesperado: {status}"
            raise CommandError(msg)

        self.stdout.write(self.style.SUCCESS("✓ Smoke test finalizado sem erros"))
        self.stdout.write(f"Subdomínio: {sub}")
        if with_admins:
            emails = ["admin1@example.com", "admin2@example.com"]
            usuarios = list(CustomUser.objects.filter(email__in=emails))
            self.stdout.write(f"Admins criados: {len(usuarios)}")
            for u in usuarios:
                self.stdout.write(f" - {u.email} (senha_hash_len={len(u.password)})")

    # -------------------------------------------------
    def _build_steps_bundle(self, *, name: str, subdomain: str, with_admins: bool) -> StepDataBundle:
        # Estrutura simplificada conforme campos esperados pelos métodos usados no finish
        step_1 = {
            "pj": {
                "tipo_pessoa": "PJ",
                "name": name,
                "razao_social": f"Razão {name}",
                "cnpj": "12.345.678/0001-99",
            },
        }
        step_2 = {"main": {"cep": "01001-000", "logradouro": "Rua Teste", "numero": "123"}}
        step_3 = {"main": {"telefone": "+5511999999999", "email": "contato@exemplo.com"}}
        step_5 = {
            "main": {"enabled_modules": ["agendamentos", "clientes", "agenda"]},
            "main-subdomain": subdomain,
        }
        step_6: dict[str, Any] = {}
        if with_admins:
            step_6 = {
                "main": {
                    "admins_json": json.dumps(
                        [
                            {"email": "admin1@example.com", "nome": "Admin 1"},
                            {"email": "admin2@example.com", "nome": "Admin 2"},
                        ],
                        ensure_ascii=False,
                    ),
                    "gerar_senha_auto": True,
                },
            }
        return StepDataBundle(step_1=step_1, step_2=step_2, step_3=step_3, step_5=step_5, step_6=step_6)
