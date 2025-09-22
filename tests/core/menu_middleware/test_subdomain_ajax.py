from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Tenant

User = get_user_model()


class SubdomainAjaxTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser("sup", "sup@example.com", "pass")
        self.client.login(username="sup", password="pass")
        self.url = reverse("core:check_subdomain")
        Tenant.objects.create(name="Base", subdomain="existente")

    def _q(self, sub):
        return self.client.get(self.url, {"subdomain": sub})

    def test_required(self):
        r = self._q("")
        self.assertEqual(r.json()["reason"], "required")

    def test_invalid_format(self):
        r = self._q("-abc")
        self.assertEqual(r.json()["reason"], "invalid_format")

    def test_reserved(self):
        r = self._q("admin")
        self.assertEqual(r.json()["reason"], "reserved")

    def test_exists(self):
        r = self._q("existente")
        self.assertEqual(r.json()["reason"], "exists")

    def test_available(self):
        r = self._q("novo-sub")
        js = r.json()
        self.assertEqual(js["reason"], "ok")
        self.assertTrue(js["available"])
