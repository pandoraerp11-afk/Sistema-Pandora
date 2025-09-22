import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Tenant
from core.services.tenant_snapshot import build_tenant_snapshot
from core.wizard_views import TenantCreationWizardView

User = get_user_model()


class TestWizardSnapshot(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser("root", "root@example.com", "StrongPass!123")
        self.view = TenantCreationWizardView()

    def test_full_wizard_snapshot(self):
        """Valida pipeline principal de criação via snapshot simplificado (com endereço adicional)."""
        wizard_data = {
            "step_1": {
                "pj": {"tipo_pessoa": "PJ", "name": "Empresa Snap", "subdomain": "snapt", "cnpj": "11.222.333/0001-44"}
            },
            "step_2": {
                "main": {
                    "cep": "01000-000",
                    "logradouro": "Rua X",
                    "numero": "123",
                    "bairro": "Centro",
                    "cidade": "São Paulo",
                    "uf": "SP",
                    "pais": "Brasil",
                    "additional_addresses_json": json.dumps(
                        [
                            {
                                "tipo": "ENT",
                                "logradouro": "Rua Y",
                                "numero": "50",
                                "bairro": "Bairro2",
                                "cidade": "São Paulo",
                                "uf": "SP",
                                "cep": "02000000",
                                "pais": "Brasil",
                            }
                        ]
                    ),
                }
            },
            "step_3": {
                "main": {
                    "nome_contato_principal": "Contato P",
                    "telefone_emergencia": "(11) 98888-7777",
                    "contacts_json": json.dumps(
                        [
                            {
                                "nome": "Suporte",
                                "email": "suporte@snap.com",
                                "telefone": "(11) 90000-0000",
                                "cargo": "Suporte",
                            },
                            {
                                "nome": "Financeiro",
                                "email": "fin@snap.com",
                                "telefone": "(11) 91111-0000",
                                "cargo": "Financeiro",
                            },
                        ],
                        ensure_ascii=False,
                    ),
                }
            },
            "step_4": {"main": {}},
            "step_5": {"main": {"enabled_modules": ["clientes", "fornecedores", "produtos"]}},
            "step_6": {
                "main": {
                    "admins_json": json.dumps(
                        [
                            {
                                "email": "admin1@snap.com",
                                "nome": "Admin One",
                                "cargo": "Administrador",
                                "senha": "SenhaForte!123",
                                "confirm_senha": "SenhaForte!123",
                            },
                            {
                                "email": "admin2@snap.com",
                                "nome": "Admin Two",
                                "cargo": "Gerente",
                                "senha": "OutraForte!123",
                                "confirm_senha": "OutraForte!123",
                                "ativo": False,
                            },
                        ],
                        ensure_ascii=False,
                    )
                }
            },
        }

        tenant = Tenant.objects.create(name="Empresa Snap", subdomain="snapt", tipo_pessoa="PJ")

        # Endereço principal + adicionais
        self.view._process_complete_address_data(tenant, {"step_2": wizard_data["step_2"]})  # type: ignore
        # Contatos
        self.view._process_complete_contacts_data(tenant, wizard_data["step_3"])  # type: ignore
        # Módulos
        tenant.enabled_modules = {"modules": sorted(set(wizard_data["step_5"]["main"]["enabled_modules"]))}
        tenant.save(update_fields=["enabled_modules"])
        # Admins
        self.view.process_admin_data(tenant, wizard_data)  # type: ignore

        snapshot = build_tenant_snapshot(tenant)

        self.assertEqual(snapshot["tenant"]["name"], "Empresa Snap")
        self.assertEqual(snapshot["enderecos"]["principal"]["uf"], "SP")
        self.assertEqual(snapshot["contatos_count"], 2)
        self.assertEqual(len(snapshot["admins"]), 2)
        emails = sorted(a["email"] for a in snapshot["admins"])
        self.assertEqual(emails, ["admin1@snap.com", "admin2@snap.com"])
        admin2 = [a for a in snapshot["admins"] if a["email"] == "admin2@snap.com"][0]
        self.assertFalse(admin2["ativo"])
        self.assertIn("clientes", snapshot["modules"])
        self.assertGreaterEqual(snapshot["enderecos"]["adicionais_count"], 1)
