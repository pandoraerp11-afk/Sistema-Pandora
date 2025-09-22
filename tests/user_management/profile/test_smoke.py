from django.conf import settings
from django.test import SimpleTestCase


class SmokeTests(SimpleTestCase):
    def test_settings_loaded(self):
        self.assertIn("user_management.apps.UserManagementConfig", settings.INSTALLED_APPS)
        self.assertTrue(settings.DEBUG in (True, False))
