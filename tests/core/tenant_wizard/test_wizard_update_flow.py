from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Role, Tenant, TenantUser
from core.tests.wizard_test_utils import TenantWizardTestHelper

User = get_user_model()


class WizardUpdateFlowTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser("sup", "sup@example.com", "pass")
        self.base = Tenant.objects.create(name="Empresa Base", subdomain="base")
        self.other = Tenant.objects.create(name="Outra", subdomain="outra")
        role = Role.objects.create(tenant=self.base, name="Admin")
        TenantUser.objects.create(tenant=self.base, user=self.superuser, role=role, is_tenant_admin=True)
        self.client.login(username="sup", password="pass")

    def test_update_change_subdomain_success(self):
        edit_url = reverse("core:tenant_update", args=[self.base.pk])
        r = self.client.get(edit_url)
        self.assertEqual(r.status_code, 200)
        helper = TenantWizardTestHelper(self.client)
        helper.step1_pj(name="Empresa Base", razao_social="Empresa Base LTDA", cnpj="11.222.333/0001-44")
        helper.skip_steps(2, 4)
        helper.step5_config(subdomain="base-editada")
        helper.skip_steps(6, 6)
        resp = helper.finish()
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Tenant.objects.filter(subdomain="base-editada").exists())

    def test_update_duplicate_subdomain_rejected(self):
        edit_url = reverse("core:tenant_update", args=[self.base.pk])
        self.client.get(edit_url)
        helper = TenantWizardTestHelper(self.client)
        helper.step1_pj(name="Empresa Base", razao_social="Empresa Base LTDA", cnpj="22.333.444/0001-88")
        helper.skip_steps(2, 4)
        helper.step5_config(subdomain="outra")
        helper.skip_steps(6, 6)
        resp = helper.finish()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:tenant_update", args=[self.base.pk]))
        self.assertFalse(Tenant.objects.filter(subdomain="outra", name="Empresa Base").exists())

    def test_update_change_subdomain_case_insensitive_normalization(self):
        """Garantir que subdomínio com maiúsculas é normalizado para lowercase no update."""
        edit_url = reverse("core:tenant_update", args=[self.base.pk])
        self.client.get(edit_url)
        helper = TenantWizardTestHelper(self.client)
        helper.step1_pj(name="Empresa Base", razao_social="Empresa Base LTDA", cnpj="33.444.555/0001-99")
        helper.skip_steps(2, 4)
        helper.step5_config(subdomain="Base-EditADA")  # mistura de cases
        helper.skip_steps(6, 6)
        resp = helper.finish()
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Tenant.objects.filter(subdomain="base-editada").exists())
        self.assertFalse(Tenant.objects.filter(subdomain="Base-EditADA").exists())
