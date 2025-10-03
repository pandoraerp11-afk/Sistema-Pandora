"""Testes adicionais cobrindo melhorias modernas do wizard (alias, fallback e flags).

Metas:
 - Alias de módulos: "agendamentos" -> "agenda" sem duplicar;
 - Fallback de subdomínio a partir do POST quando ausente de step_5;
 - Geração automática de senhas quando generate_passwords_auto (gerar_senha_auto) ativo.
"""

import json
from typing import Any

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from core.models import CustomUser, Tenant
from core.services.wizard_context import WizardContext
from core.wizard_views import STEP_CONFIG, TenantCreationWizardView

User = get_user_model()


class TestWizardModuleAliasAndFlags(TestCase):
    """Suite específica para validar extensões modernas do wizard."""

    def setUp(self) -> None:
        """Criar superuser e configurar view/request para testes."""
        self.superuser = User.objects.create_superuser(
            "root",
            "root@example.com",
            "StrongPass!123",
        )
        self.factory = RequestFactory()
        self.request = self.factory.post("/core/wizard/")
        self.request.user = self.superuser
        self.request.session = self.client.session  # Django fornece backend real
        self.view = TenantCreationWizardView()
        # setup() de View garante request/args/kwargs como no dispatch
        self.view.setup(self.request)

    def _fake_valid_forms(self, enabled_modules: list[str] | None = None) -> dict[str, Any]:
        """Cria estrutura simulando forms válidos do step config."""

        class _DummyForm:
            def __init__(self, cleaned: dict[str, Any]) -> None:
                self.cleaned_data = cleaned

            def is_valid(self) -> bool:
                return True

        return {"main": _DummyForm({"enabled_modules": enabled_modules or []})}

    def test_module_alias_agendamentos_to_agenda(self) -> None:
        """Alias 'agendamentos' vira 'agenda' apenas uma vez e mantém outros módulos."""
        Tenant.objects.create(name="AliasCo", subdomain="aliasco", tipo_pessoa="PJ")
        self.request.POST = self.request.POST.copy()
        self.request.POST.setlist("enabled_modules", ["agendamentos", "agenda", "clientes"])  # alias + destino
        self.request.POST["main-subdomain"] = "aliasco"
        forms = self._fake_valid_forms(["clientes"])
        step_data = self.view.process_step_data(forms, STEP_CONFIG)
        mods = sorted(step_data["main"].get("enabled_modules", []))
        assert "agenda" in mods
        assert "clientes" in mods
        assert "agendamentos" not in mods
        assert mods.count("agenda") == 1

    def test_subdomain_fallback_when_missing_in_wizard_data(self) -> None:
        """Fallback de subdomínio do POST quando step_5 ausente ainda valida integridade."""
        self.request.POST = self.request.POST.copy()
        self.request.POST["main-subdomain"] = "novosub"
        wizard_data = {
            "step_1": {
                "pj": {
                    "tipo_pessoa": "PJ",
                    "name": "Empresa Fallback",
                    "cnpj": "99.999.999/0001-99",
                },
            },
        }
        ctx = WizardContext(raw=wizard_data, is_editing=False, editing_tenant=None)
        ok = self.view.validate_wizard_data_integrity(ctx)
        assert ok is True

    def test_generate_passwords_auto_for_admins(self) -> None:
        """Flag gerar_senha_auto cria senhas para linhas sem senha explícita."""
        tenant = Tenant.objects.create(name="AutoPwd", subdomain="autopwd", tipo_pessoa="PJ")
        payload = {
            "step_6": {
                "main": {
                    "admins_json": json.dumps(
                        [
                            {"email": "a1@example.com", "nome": "A1"},
                            {"email": "a2@example.com", "nome": "A2"},
                        ],
                        ensure_ascii=False,
                    ),
                    "gerar_senha_auto": True,
                },
            },
        }
        self.view.process_admin_data(tenant, payload)
        u1 = CustomUser.objects.get(email="a1@example.com")
        u2 = CustomUser.objects.get(email="a2@example.com")
        assert u1.has_usable_password()
        assert u2.has_usable_password()
        assert len(u1.password) > 30
