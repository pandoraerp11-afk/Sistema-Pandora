import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Role, Tenant, TenantUser
from core.wizard_views import TenantCreationWizardView

User = get_user_model()


class TestWizardAdminEdit(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser("root", "root@example.com", "StrongPass!123")
        self.tenant = Tenant.objects.create(name="Empresa Edit", subdomain="empedit", tipo_pessoa="PJ")
        self.role, _ = Role.objects.get_or_create(tenant=self.tenant, name="Administrador")
        # Admin existente
        self.user1 = User.objects.create_user("adm1", "adm1@example.com", "SenhaForte!123")
        TenantUser.objects.create(
            user=self.user1, tenant=self.tenant, role=self.role, is_tenant_admin=True, cargo="Antigo"
        )
        self.view = TenantCreationWizardView()

    def _process(self, admins_list, bulk_password=None):
        payload = {"step_6": {"main": {"admins_json": json.dumps(admins_list, ensure_ascii=False)}}}
        if bulk_password:
            payload["step_6"]["main"]["bulk_admin_password"] = bulk_password
        self.view.process_admin_data(self.tenant, payload)

    def test_update_existing_admin_cargo_and_phone(self):
        self.user1.phone = ""
        self.user1.save(update_fields=["phone"])
        admins = [
            {
                "user_id": self.user1.pk,
                "email": self.user1.email,
                "nome": "Adm Um",
                "telefone": "(11) 90000-0001",
                "cargo": "Novo Cargo",
                "ativo": True,
            }
        ]
        self._process(admins)
        self.user1.refresh_from_db()
        tu = TenantUser.objects.get(user=self.user1, tenant=self.tenant)
        assert self.user1.phone == "(11) 90000-0001"
        assert tu.cargo == "Novo Cargo"

    def test_deactivate_existing_admin(self):
        admins = [{"user_id": self.user1.pk, "email": self.user1.email, "ativo": False}]
        self._process(admins)
        self.user1.refresh_from_db()
        assert self.user1.is_active is False

    def test_mix_update_and_new_creation(self):
        admins = [
            {"user_id": self.user1.pk, "email": self.user1.email, "cargo": "Persistente", "ativo": True},
            {
                "email": "novo_admin@example.com",
                "nome": "Novo Admin",
                "senha": "SenhaValida!123",
                "confirm_senha": "SenhaValida!123",
            },
        ]
        self._process(admins)
        assert User.objects.filter(email="novo_admin@example.com").exists()
        assert TenantUser.objects.filter(tenant=self.tenant).count() == 2
