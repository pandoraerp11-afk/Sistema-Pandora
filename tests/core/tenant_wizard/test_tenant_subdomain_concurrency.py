from django.db import IntegrityError
from django.test import TestCase

from core.models import Tenant


class TenantSubdomainConcurrencyTest(TestCase):
    def test_unique_constraint_integrity(self):
        Tenant.objects.create(name="A", subdomain="dup")
        with self.assertRaises(IntegrityError):
            Tenant.objects.create(name="B", subdomain="dup")
