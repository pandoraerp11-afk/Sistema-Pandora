"""Testes de fluxo em tempo real de notificações (chat e agenda)."""

import os

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from agenda.models import Evento
from chat.models import Conversa, Mensagem
from core.models import Tenant, TenantUser
from notifications.models import Notification
from notifications.views import marcar_notificacoes_chat_lidas

User = get_user_model()


class NotificationRealtimeFlowTest(TestCase):
    """Testes de criação e sincronização de notificações oriundas de chat e agenda."""

    def setUp(self) -> None:
        """Cria tenant, usuários (com vínculo) e conversa base."""
        pwd = os.environ.get("TEST_PASSWORD", "x")
        self.tenant = Tenant.objects.create(name="Empresa X", subdomain="empresa-x", status="active")
        self.u1 = User.objects.create_user(username="alice", password=pwd)
        self.u2 = User.objects.create_user(username="bob", password=pwd)
        # Garantir vínculo tenant para lógica de leitura (tenant_memberships)
        TenantUser.objects.create(user=self.u1, tenant=self.tenant)
        TenantUser.objects.create(user=self.u2, tenant=self.tenant)
        # Conversa entre u1 e u2
        self.conversa = Conversa.objects.create(tenant=self.tenant, tipo="individual", criador=self.u1)
        self.conversa.participantes.add(self.u1, self.u2)

    def test_chat_message_creates_notifications(self) -> None:
        """Mensagem gera notificação para destinatário."""
        Mensagem.objects.create(tenant=self.tenant, conversa=self.conversa, remetente=self.u1, conteudo="Olá Bob!")
        notas = Notification.objects.filter(usuario_destinatario=self.u2, modulo_origem="chat")
        assert notas.count() == 1
        n = notas.first()
        assert n is not None
        assert "Olá Bob" in n.mensagem

    def test_agenda_event_creates_notifications(self) -> None:
        """Evento de agenda gera notificações para responsável e participantes."""
        # Cria evento inicial sem participantes para em seguida alterar status e gerar notificações
        evt = Evento.objects.create(
            tenant=self.tenant,
            titulo="Reunião",
            data_inicio=timezone.now() + timezone.timedelta(hours=1),
        )
        evt.participantes.add(self.u1, self.u2)
        evt.responsavel = self.u1
        # Alterar status para disparar lógica de atualização que gera notificações
        evt.status = "confirmado"
        evt.save()
        notas = Notification.objects.filter(modulo_origem="agenda")
        assert notas.exists()
        destinatarios = set(notas.values_list("usuario_destinatario__username", flat=True))
        assert "alice" in destinatarios
        assert "bob" in destinatarios

    def test_mark_chat_messages_read_syncs_notifications(self) -> None:
        """Marcação de mensagens lidas reflete em notificações ('lida')."""
        # Cria mensagem para gerar notificação para u2
        msg = Mensagem.objects.create(tenant=self.tenant, conversa=self.conversa, remetente=self.u1, conteudo="Ping")
        # Verifica notificação criada
        nota = Notification.objects.get(usuario_destinatario=self.u2, dados_extras__mensagem_id=msg.id)
        assert nota.status == "nao_lida"
        # Simula leitura: marcar mensagens lidas via método conversa
        self.conversa.marcar_mensagens_como_lidas(self.u2)
        # Sincronização via helper direto
        marcar_notificacoes_chat_lidas(self.conversa.id, self.u2, mensagem_ids=[msg.id])
        nota.refresh_from_db()
        assert nota.status == "lida"
