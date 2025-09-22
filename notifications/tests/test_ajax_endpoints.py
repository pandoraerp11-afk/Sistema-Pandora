import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Tenant
from notifications.models import Notification

User = get_user_model()


class NotificationAjaxEndpointsTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Ajuste: Tenant usa campos name e subdomain (não slug)
        self.tenant = Tenant.objects.create(name="Ajax Co", subdomain="ajax-co")
        self.user = User.objects.create_user(username="ajaxuser", password="pass")
        # Cria notificações simples (campos mínimos)
        self.n1 = Notification.objects.create(
            tenant=self.tenant, usuario_destinatario=self.user, titulo="N1", mensagem="M1", tipo="info"
        )
        self.n2 = Notification.objects.create(
            tenant=self.tenant, usuario_destinatario=self.user, titulo="N2", mensagem="M2", tipo="info"
        )
        self.client.login(username="ajaxuser", password="pass")
        # Inject tenant id em sessão para middleware localizar (se middleware checa subdomínio pode não funcionar em teste).
        session = self.client.session
        session["current_tenant_id"] = self.tenant.id
        session.save()

    def _post_json(self, url_name, payload):
        url = reverse(url_name)
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_HOST=f"{self.tenant.subdomain}.testserver",
        )

    def test_batch_archive(self):
        resp = self._post_json(
            "notifications:notification-batch-action", {"operation": "archive", "ids": [self.n1.id, self.n2.id]}
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.n1.refresh_from_db()
        self.n2.refresh_from_db()
        self.assertEqual(self.n1.status, "arquivada")
        self.assertEqual(self.n2.status, "arquivada")

    def test_single_mark_read(self):
        resp = self._post_json("notifications:api_action", {"notification_id": self.n1.id, "action": "marcar_lida"})
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.n1.refresh_from_db()
        self.assertEqual(self.n1.status, "lida")
