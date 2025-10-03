"""Testes para comandos de limpeza e dedupe de notificações."""

import os
from datetime import timedelta
from io import StringIO
from typing import Any  # noqa: F401 (usado em comentários futuros se necessário)

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Tenant
from notifications.models import (
    ConfiguracaoNotificacao,
    Notification,
    NotificationAdvanced,
    NotificationRecipient,
    TenantNotificationSettings,
)

User = get_user_model()


class ManagementCommandsNotificationTest(TestCase):
    """Testes cobrindo expiração/remoção e deduplicação de notificações simples e avançadas."""

    def setUp(self) -> None:
        """Configura tenant, usuários e configurações de retenção."""
        self.tenant = Tenant.objects.create(name="Empresa Cmd", subdomain="empresa-cmd", status="active")
        pwd = os.getenv("TEST_PASSWORD", "x")
        self.user1 = User.objects.create_user(username="u1", password=pwd)  # nosec S106
        self.user2 = User.objects.create_user(username="u2", password=pwd)  # nosec S106
        # Config simples
        self.cfg = ConfiguracaoNotificacao.objects.create(
            tenant=self.tenant,
            dias_expiracao_padrao=10,
            dias_retencao_lidas=5,
            dias_retencao_arquivadas=30,
        )
        # Config avançada
        self.tset = TenantNotificationSettings.objects.create(
            tenant=self.tenant,
            notification_retention_days=15,
        )

    def _retroceder(self, obj: object, dias: int) -> None:
        """Retrocede artificialmente a data de criação do objeto em 'dias'."""
        obj.__class__.objects.filter(pk=obj.pk).update(  # type: ignore[attr-defined]
            created_at=timezone.now() - timedelta(days=dias),
        )

    def test_notifications_cleanup_simple_and_advanced(self) -> None:
        """Valida expiração e remoção de simples e avançadas conforme políticas."""
        # Simples
        n_naolida = Notification.objects.create(
            tenant=self.tenant,
            usuario_destinatario=self.user1,
            titulo="A",
            mensagem="A",
            tipo="info",
        )
        n_lida = Notification.objects.create(
            tenant=self.tenant,
            usuario_destinatario=self.user1,
            titulo="B",
            mensagem="B",
            tipo="info",
            status="lida",
        )
        n_arch = Notification.objects.create(
            tenant=self.tenant,
            usuario_destinatario=self.user1,
            titulo="C",
            mensagem="C",
            tipo="info",
            status="arquivada",
        )
        self._retroceder(n_naolida, 20)  # expira (>10)
        # Criada há 7 dias: < limite_lidas (5) p/ deletar? (ajuste correto é >5 e <10). Corrigir comentário:
        # Necessário: created_at < now-5 (retention lidas) e >= now-10 (não expirar): usamos 7 dias.
        self._retroceder(n_lida, 7)  # deletar sem expirar
        self._retroceder(n_arch, 40)  # deletar (>30)

        # Avançadas
        adv_pending = NotificationAdvanced.objects.create(
            tenant=self.tenant,
            title="AdvPend",
            content="X",
            priority="medium",
        )
        adv_read = NotificationAdvanced.objects.create(
            tenant=self.tenant,
            title="AdvRead",
            content="X",
            priority="medium",
            status="read",
        )
        adv_arch = NotificationAdvanced.objects.create(
            tenant=self.tenant,
            title="AdvArch",
            content="X",
            priority="medium",
            status="archived",
        )
        # Recipients (necessário para consistência)
        for adv in (adv_pending, adv_read, adv_arch):
            NotificationRecipient.objects.create(notification=adv, user=self.user2)
        self._retroceder(adv_pending, 25)  # expira (> retention 15)
        self._retroceder(adv_read, 20)
        NotificationAdvanced.objects.filter(pk=adv_read.pk).update(read_date=timezone.now() - timedelta(days=20))
        self._retroceder(adv_arch, 50)

        # Dry run
        out = StringIO()
        call_command("notifications_cleanup", "--dry-run", stdout=out)
        adv_pending.refresh_from_db()
        n_naolida.refresh_from_db()
        assert adv_pending.status == "pending"
        assert n_naolida.status == "nao_lida"

        # Execução real
        out = StringIO()
        call_command("notifications_cleanup", stdout=out)
        # Refresh
        adv_pending.refresh_from_db()
        n_naolida.refresh_from_db()
        assert n_naolida.status == "expirada"
        adv_pending.refresh_from_db()
        assert adv_pending.status == "expired"
        # Lida simples removida
        assert not Notification.objects.filter(pk=n_lida.pk).exists()
        # Arquivada simples removida
        assert not Notification.objects.filter(pk=n_arch.pk).exists()
        # Lida avançada removida (read old)
        assert not NotificationAdvanced.objects.filter(pk=adv_read.pk).exists()
        # Arquivada avançada removida
        assert not NotificationAdvanced.objects.filter(pk=adv_arch.pk).exists()

    def test_notifications_dedupe_simple_and_advanced(self) -> None:
        """Garante que duplicatas são arquivadas mantendo somente uma ativa."""
        # Simples duplicadas agenda
        for _i in range(3):
            Notification.objects.create(
                tenant=self.tenant,
                usuario_destinatario=self.user1,
                titulo="Evt",
                mensagem="Evt",
                tipo="info",
                modulo_origem="agenda",
                dados_extras={"evento_id": 123},
            )
        # Avançadas duplicadas
        base_args = {
            "tenant": self.tenant,
            "title": "TituloX",
            "content": "Y",
            "priority": "medium",
            "source_module": "agenda",
            "source_object_type": "Evento",
            "source_object_id": "123",
        }
        adv_main = NotificationAdvanced.objects.create(**base_args)
        adv_dup1 = NotificationAdvanced.objects.create(**base_args)
        adv_dup2 = NotificationAdvanced.objects.create(**base_args)
        for adv in (adv_main, adv_dup1, adv_dup2):
            NotificationRecipient.objects.create(notification=adv, user=self.user2)
        out = StringIO()
        call_command("notifications_dedupe", "--window-minutes", "10", stdout=out)
        # Simples: 1 ativa + 2 arquivadas
        simples = Notification.objects.filter(modulo_origem="agenda", dados_extras__evento_id=123)
        assert simples.count() == 3
        arquivadas = simples.filter(status="arquivada").count()
        assert arquivadas == 2
        # Avançadas: 1 mantida, 2 archived
        adv_all = NotificationAdvanced.objects.filter(source_module="agenda", source_object_id="123")
        assert adv_all.count() == 3
        archived_adv = adv_all.filter(status="archived").count()
        assert archived_adv == 2
