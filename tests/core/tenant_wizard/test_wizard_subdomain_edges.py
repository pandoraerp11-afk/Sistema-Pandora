from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Role, Tenant, TenantUser
from tests.core.tenant_wizard.wizard_test_utils import TenantWizardTestHelper

CustomUser = get_user_model()


class WizardSubdomainEdgeCasesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = CustomUser.objects.create_superuser("superuser", "super@example.com", "password123")
        self.base_tenant = Tenant.objects.create(name="Empresa Base", subdomain="base")
        self.role = Role.objects.create(tenant=self.base_tenant, name="Admin")
        TenantUser.objects.create(tenant=self.base_tenant, user=self.superuser, role=self.role, is_tenant_admin=True)
        self.client.login(username="superuser", password="password123")
        self.helper = TenantWizardTestHelper(self.client)
        self.helper.start()
        self.helper.step1_pj()
        self.helper.skip_steps(2, 4)

    def _go_finish(self):
        # Skip step 6
        self.helper.skip_steps(6, 6)
        return self.helper.finish()

    def test_subdomain_min_length(self):
        # 1 caractere válido
        self.helper.step5_config(subdomain="a")
        resp = self._go_finish()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:tenant_list"))
        self.assertTrue(Tenant.objects.filter(subdomain="a").exists())

    def test_subdomain_max_length(self):
        # 63 chars: primeiro e último alfanumérico
        core = "a" + ("-" * 61) + "b"  # size 63? Actually a + 61 hyphens + b => 63
        # Ajustar para garantir pattern (não terminar com '-')
        self.helper.step5_config(subdomain=core)
        resp = self._go_finish()
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Tenant.objects.filter(subdomain=core).exists())

    def test_subdomain_invalid_start_hyphen(self):
        # Deve falhar formato e não avançar para finish
        self.helper.step5_config_expect_error(subdomain="-abc")
        # Espera-se 200 (mesmo step re-renderizado) ou 302? Caso atual: view avança livre. Validaremos não criação no finish.
        # Prosseguir skip 6 e tentar finalizar
        self.helper.skip_steps(6, 6)
        resp_finish = self.helper.finish()
        # Deve redirecionar de volta para create sem criar tenant
        self.assertEqual(resp_finish.status_code, 302)
        self.assertEqual(resp_finish.url, reverse("core:tenant_create"))
        self.assertFalse(Tenant.objects.filter(subdomain="-abc").exists())

    def test_subdomain_reserved(self):
        self.helper.step5_config(subdomain="admin")
        resp = self._go_finish()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:tenant_create"))
        self.assertFalse(Tenant.objects.filter(subdomain="admin").exists())

    def test_subdomain_duplicate_case_insensitive(self):
        Tenant.objects.create(name="Existente Up", subdomain="duplicado")
        self.helper.step5_config(subdomain="DUPLICADO")
        resp = self._go_finish()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:tenant_create"))
        self.assertEqual(Tenant.objects.filter(subdomain="duplicado").count(), 1)

    def test_subdomain_invalid_trailing_hyphen(self):
        # Não pode terminar com hífen
        self.helper.step5_config(subdomain="abc-")
        resp = self._go_finish()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:tenant_create"))
        self.assertFalse(Tenant.objects.filter(subdomain="abc-").exists())

    def test_subdomain_too_long_64(self):
        # 64 caracteres deve falhar (regex limita 63)
        too_long = "a" + ("b" * 62) + "c"  # 64 chars
        self.helper.step5_config(subdomain=too_long)
        resp = self._go_finish()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:tenant_create"))
        self.assertFalse(Tenant.objects.filter(subdomain=too_long).exists())

    def test_subdomain_uppercase_normalized(self):
        # Maiúsculas devem ser normalizadas para minúsculas e criar com sucesso
        self.helper.step5_config(subdomain="EmpresaX")
        resp = self._go_finish()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:tenant_list"))
        self.assertTrue(Tenant.objects.filter(subdomain="empresax").exists())
