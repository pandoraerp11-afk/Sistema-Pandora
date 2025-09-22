import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Contato, Tenant
from core.wizard_views import TenantCreationWizardView

User = get_user_model()


class TestWizardMultiContacts(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser("root", "root@example.com", "StrongPass!123")
        self.tenant = Tenant.objects.create(name="Empresa MC", subdomain="empresamc", tipo_pessoa="PJ")
        self.view = TenantCreationWizardView()

    def _process(self, contacts_list):
        payload = {"step_3": {"main": {"contacts_json": json.dumps(contacts_list, ensure_ascii=False)}}}
        # Chamamos método privado de processamento completo para reutilizar lógica
        self.view._process_complete_contacts_data(self.tenant, payload["step_3"])  # type: ignore

    def test_create_multiple_contacts(self):
        contacts = [
            {"nome": "Tech Lead", "email": "tech@example.com", "telefone": "(11) 99999-0001", "cargo": "Tecnico"},
            {"nome": "Jurídico", "email": "legal@example.com", "telefone": "(11) 99999-0002", "cargo": "Legal"},
            {"nome": "", "email": "", "telefone": ""},  # ignorado
        ]
        self._process(contacts)
        self.assertEqual(Contato.objects.filter(tenant=self.tenant).count(), 2)
        emails = set(Contato.objects.filter(tenant=self.tenant).values_list("email", flat=True))
        self.assertIn("tech@example.com", emails)
        self.assertIn("legal@example.com", emails)

    def test_replace_contacts(self):
        # Primeiro batch
        self._process([{"nome": "A", "email": "a@x.com"}])
        self.assertEqual(Contato.objects.filter(tenant=self.tenant).count(), 1)
        # Segundo replace total
        self._process([{"nome": "B", "email": "b@x.com"}])
        qs = Contato.objects.filter(tenant=self.tenant)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().email, "b@x.com")

    def test_invalid_json_graceful(self):
        # Passar string inválida deve resultar em zero contatos criados (limpeza)
        payload = {"step_3": {"main": {"contacts_json": "INVALID"}}}
        self.view._process_complete_contacts_data(self.tenant, payload["step_3"])  # type: ignore
        self.assertEqual(Contato.objects.filter(tenant=self.tenant).count(), 0)
