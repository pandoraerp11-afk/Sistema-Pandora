import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Tenant, TenantUser
from core.services.tenant_snapshot import build_tenant_snapshot
from core.wizard_views import TenantCreationWizardView

User = get_user_model()


class TestWizardSnapshotEdit(TestCase):
    def setUp(self):
        self.view = TenantCreationWizardView()

    def _create_base(self):
        wizard_data = {
            "step_1": {
                "pj": {"tipo_pessoa": "PJ", "name": "Empresa Base", "subdomain": "basex", "cnpj": "00.111.222/0001-55"}
            },
            "step_2": {
                "main": {
                    "cep": "01000-000",
                    "logradouro": "Av A",
                    "numero": "10",
                    "bairro": "Centro",
                    "cidade": "SP",
                    "uf": "SP",
                    "pais": "Brasil",
                    "additional_addresses_json": json.dumps(
                        [
                            {
                                "tipo": "ENT",
                                "logradouro": "Rua B",
                                "numero": "20",
                                "bairro": "B2",
                                "cidade": "SP",
                                "uf": "SP",
                                "cep": "02000000",
                            }
                        ]
                    ),
                }
            },
            "step_3": {
                "main": {
                    "contacts_json": json.dumps(
                        [
                            {"nome": "Contato1", "email": "c1@x.com"},
                        ],
                        ensure_ascii=False,
                    )
                }
            },
            "step_5": {"main": {"enabled_modules": ["clientes"]}},
            "step_6": {
                "main": {
                    "admins_json": json.dumps(
                        [
                            {
                                "email": "admin@x.com",
                                "nome": "Admin X",
                                "cargo": "gerente",
                                "senha": "SenhaForte!123",
                                "confirm_senha": "SenhaForte!123",
                            }
                        ],
                        ensure_ascii=False,
                    )
                }
            },
        }
        tenant = Tenant.objects.create(name="Empresa Base", subdomain="basex", tipo_pessoa="PJ")
        self.view._process_complete_address_data(tenant, {"step_2": wizard_data["step_2"]})  # type: ignore
        self.view._process_complete_contacts_data(tenant, wizard_data["step_3"])  # type: ignore
        tenant.enabled_modules = {"modules": ["clientes"]}
        tenant.save(update_fields=["enabled_modules"])
        self.view.process_admin_data(tenant, wizard_data)  # type: ignore
        return tenant

    def test_edit_snapshot_diff(self):
        tenant = self._create_base()
        base_snapshot = build_tenant_snapshot(tenant)
        self.assertGreaterEqual(base_snapshot["enderecos"]["adicionais_count"], 1)
        # Edit: substituir contatos, adicionar módulo, alterar admin, desativar
        contatos_json = json.dumps(
            [
                {"nome": "Suporte Novo", "email": "suporte@x.com", "cargo": "Suporte"},
                {"nome": "Financeiro Novo", "email": "fin@x.com", "cargo": "Financeiro"},
            ],
            ensure_ascii=False,
        )
        self.view._process_complete_contacts_data(tenant, {"main": {"contacts_json": contatos_json}})  # type: ignore
        tenant.enabled_modules = {"modules": ["clientes", "fornecedores"]}
        tenant.save(update_fields=["enabled_modules"])
        tu = TenantUser.objects.get(tenant=tenant, user__email="admin@x.com")
        admin_json = json.dumps(
            [
                {
                    "user_id": tu.user.id,
                    "email": tu.user.email,
                    "nome": "Admin X Editado",
                    "cargo": "Diretor",
                    "ativo": False,
                }
            ]
        )
        wizard_data_edit = {"step_6": {"main": {"admins_json": admin_json}}}
        self.view.process_admin_data(tenant, wizard_data_edit)  # type: ignore
        edited_snapshot = build_tenant_snapshot(tenant)
        self.assertNotEqual(base_snapshot["contatos_count"], edited_snapshot["contatos_count"])
        self.assertIn("fornecedores", edited_snapshot["modules"])
        admin = [a for a in edited_snapshot["admins"] if a["email"] == "admin@x.com"][0]
        self.assertEqual(admin["cargo"], "Diretor")
        self.assertFalse(admin["ativo"])
