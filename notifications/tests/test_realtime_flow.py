from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from agenda.models import Evento
from chat.models import Conversa, Mensagem
from core.models import Tenant
from notifications.models import Notification

User = get_user_model()


class NotificationRealtimeFlowTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa X", subdomain="empresa-x", status="active")
        self.u1 = User.objects.create_user(username="alice", password="pass")
        self.u2 = User.objects.create_user(username="bob", password="pass")
        # Conversa entre u1 e u2
        self.conversa = Conversa.objects.create(tenant=self.tenant, tipo="individual", criador=self.u1)
        self.conversa.participantes.add(self.u1, self.u2)

    def test_chat_message_creates_notifications(self):
        Mensagem.objects.create(tenant=self.tenant, conversa=self.conversa, remetente=self.u1, conteudo="Olá Bob!")
        notas = Notification.objects.filter(usuario_destinatario=self.u2, modulo_origem="chat")
        self.assertEqual(notas.count(), 1)
        n = notas.first()
        self.assertIn("Olá Bob", n.mensagem)

    def test_agenda_event_creates_notifications(self):
        evt = Evento.objects.create(
            tenant=self.tenant, titulo="Reunião", data_inicio=timezone.now() + timezone.timedelta(hours=1)
        )
        evt.participantes.add(self.u1, self.u2)
        evt.responsavel = self.u1
        evt.save()
        # Ao salvar com participantes e responsável, sinal cria notificações
        notas = Notification.objects.filter(modulo_origem="agenda")
        self.assertTrue(notas.exists())
        destinatarios = set(notas.values_list("usuario_destinatario__username", flat=True))
        self.assertIn("alice", destinatarios)
        self.assertIn("bob", destinatarios)

    def test_mark_chat_messages_read_syncs_notifications(self):
        # Cria mensagem para gerar notificação para u2
        msg = Mensagem.objects.create(tenant=self.tenant, conversa=self.conversa, remetente=self.u1, conteudo="Ping")
        # Verifica notificação criada
        nota = Notification.objects.get(usuario_destinatario=self.u2, dados_extras__mensagem_id=msg.id)
        self.assertEqual(nota.status, "nao_lida")
        # Simula leitura: marcar mensagens lidas via método conversa
        self.conversa.marcar_mensagens_como_lidas(self.u2)
        # Sincronização é via consumer normalmente; aqui chamamos helper direto
        from notifications.views import marcar_notificacoes_chat_lidas

        marcar_notificacoes_chat_lidas(self.conversa.id, self.u2, mensagem_ids=[msg.id])
        nota.refresh_from_db()
        self.assertEqual(nota.status, "lida")
