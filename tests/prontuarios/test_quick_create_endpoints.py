import unittest

from django.test import TestCase
from rest_framework.test import APIClient

from core.models import CustomUser, Tenant

try:
    from servicos.models import Servico  # noqa: F401
except Exception:  # pragma: no cover
    Servico = None


@unittest.skip("Endpoint quick_create_procedimento removido na migração para Servico/ServicoClinico")
class QuickCreateEndpointsTest(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1", status="active")
        self.user = CustomUser.objects.create_user(username="u1", password="x")
        logged = self.client_api.login(username="u1", password="x")
        assert logged, "Falha ao logar usuário de teste"
        self.client_api.force_authenticate(user=self.user)
        session = self.client_api.session
        session["tenant_id"] = self.tenant.id
        session.save()

    # Tests removidos
    pass
