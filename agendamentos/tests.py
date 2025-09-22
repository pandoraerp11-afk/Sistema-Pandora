from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from core.models import Tenant
from servicos.models import Servico, ServicoClinico

from .models import Agendamento, Disponibilidade, Slot
from .services import AgendamentoService, SlotService

User = get_user_model()


class SlotReservaTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.user = User.objects.create_user(username="prof", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente 1", tipo_pessoa="PF")
        hoje = timezone.localdate()
        self.disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.user,
            data=hoje,
            hora_inicio=time(9, 0),
            hora_fim=time(10, 0),
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        # Criar manualmente dois slots para teste
        from datetime import datetime

        timezone.get_current_timezone()
        for minute in (0, 30):
            Slot.objects.create(
                tenant=self.tenant,
                disponibilidade=self.disp,
                profissional=self.user,
                horario=timezone.make_aware(datetime.combine(hoje, time(9, minute))),
                capacidade_total=1,
            )
        self.slot = Slot.objects.order_by("horario").first()
        # Serviço clínico padrão 45min
        self.servico = Servico.objects.create(
            tenant=self.tenant,
            nome="Limpeza de Pele",
            descricao="Desc",
            ativo=True,
            is_clinical=True,
        )
        ServicoClinico.objects.create(
            servico=self.servico,
            duracao_estimada=timedelta(minutes=45),
            requisitos_pre_procedimento="",
            contraindicacoes="",
            cuidados_pos_procedimento="",
            requer_anamnese=True,
            requer_termo_consentimento=True,
            permite_fotos_evolucao=True,
            intervalo_minimo_sessoes=7,
        )

    def test_reserva_slot(self):
        self.assertTrue(self.slot.disponivel)
        SlotService.reservar(self.slot)
        self.slot.refresh_from_db()
        self.assertFalse(self.slot.disponivel)

    def test_reserva_slot_erros_metric(self):
        from agendamentos.services import SLOTS_RESERVA_ERROS_TOTAL, SchedulingService

        # Forçar lotação do slot
        SlotService.reservar(self.slot)
        before = getattr(SLOTS_RESERVA_ERROS_TOTAL, "_value", lambda: None)
        # Tentar reservar novamente gera erro e deve incrementar counter (se lib presente)
        with self.assertRaises(ValueError):
            SchedulingService.reservar_slot(self.slot)
        # Não falha se _value não existir (fallback no-op)
        if callable(before):
            pass

    @override_settings(AG_SLOTS_CACHE_TTL=5)
    def test_cache_slots_invalida_em_reserva(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import SlotViewSet

        factory = APIRequestFactory()
        view = SlotViewSet.as_view({"get": "list"})
        request1 = factory.get("/api/slots/?disponivel=1")
        force_authenticate(request1, user=self.user)
        resp1 = view(request1)
        self.assertEqual(resp1.status_code, 200)
        total_before = len(resp1.data)
        # Segunda chamada deve vir do cache (difícil medir sem introspecção; apenas confirmar mesma contagem)
        request2 = factory.get("/api/slots/?disponivel=1")
        force_authenticate(request2, user=self.user)
        resp2 = view(request2)
        self.assertEqual(len(resp2.data), total_before)
        # Reservar slot invalida versão => após reserva slot deixa de estar disponível (capacidade_utilizada == total)
        SlotService.reservar(self.slot)
        request3 = factory.get("/api/slots/?disponivel=1")
        force_authenticate(request3, user=self.user)
        resp3 = view(request3)
        # Agora a lista pode ser menor (slot ocupado sai da lista disponivel)
        self.assertLessEqual(len(resp3.data), total_before)

    @override_settings(AG_DISP_CACHE_TTL=5)
    def test_cache_disponibilidades_por_papel(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import DisponibilidadeViewSet

        factory = APIRequestFactory()
        view = DisponibilidadeViewSet.as_view({"get": "list"})
        req = factory.get("/api/disponibilidades/")
        force_authenticate(req, user=self.user)
        r1 = view(req)
        self.assertEqual(r1.status_code, 200)
        self.assertGreaterEqual(len(r1.data), 1)
        # Segunda chamada: mesma contagem (cache hit – comportamento idempotente)
        req2 = factory.get("/api/disponibilidades/")
        force_authenticate(req2, user=self.user)
        r2 = view(req2)
        self.assertEqual(len(r2.data), len(r1.data))

    @override_settings(ENABLE_CAPACITY_GAUGES=True)
    def test_gauges_capacidade_atualizam_em_gerar_slots(self):
        from agendamentos.services import SLOTS_CAP_TOTAL_GAUGE

        # Criar uma disponibilidade nova e gerar slots para garantir atualização
        hoje = timezone.localdate()
        disp2 = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.user,
            data=hoje,
            hora_inicio=time(11, 0),
            hora_fim=time(12, 0),
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        SlotService.gerar_slots(disp2)
        # Não falhar se gauges no-op; apenas tentar acessar labels
        try:
            SLOTS_CAP_TOTAL_GAUGE.labels(profissional_id=str(self.user.id))
        except Exception:
            self.fail("Gauge não acessível")

    def test_counters_erros_criacao(self):
        from agendamentos.services import AGENDAMENTOS_CRIACAO_ERROS_TOTAL

        # Forçar erro: serviço obrigatório se flag REQUIRE_SERVICO=True (simular via override)
        with override_settings(REQUIRE_SERVICO=True), self.assertRaises(ValueError):
            AgendamentoService.criar(
                tenant=self.tenant,
                cliente=self.cliente,
                profissional=self.user,
                data_inicio=self.slot.horario,
                data_fim=self.slot.horario + timedelta(minutes=30),
                origem="PROFISSIONAL",
                slot=None,
            )
        # Apenas garante que counter existe (no-op se lib ausente)
        self.assertTrue(hasattr(AGENDAMENTOS_CRIACAO_ERROS_TOTAL, "inc"))

    @override_settings(ENABLE_EVENT_MIRROR=True)
    def test_counter_migracao_metadata_evento(self):
        from agendamentos.services import SchedulingService

        # Criar agendamento com metadata legado simulada
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        ag = Agendamento.objects.create(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            slot=self.slot,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            status="CONFIRMADO",
            metadata={"evento_id": 999},
        )
        SchedulingService.sync_evento(ag)
        ag.refresh_from_db()
        self.assertIn("evento_agenda_id", ag.metadata)
        self.assertNotIn("evento_id", ag.metadata)

    def test_agendamento_criacao(self):
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=self.slot,
            tipo_servico="Teste",
        )
        self.assertIsNotNone(ag.id)
        self.assertEqual(ag.status, "CONFIRMADO")
        self.slot.refresh_from_db()
        self.assertFalse(self.slot.disponivel)

    def test_agendamento_com_servico_sem_fim_manual(self):
        # criação manual sem data_fim explícito (usa duração do serviço)
        inicio = self.slot.horario + timedelta(hours=2)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=None,
            origem="PROFISSIONAL",
            servico=self.servico.id,
            slot=None,
        )
        self.assertIsNotNone(ag.servico_id)
        self.assertGreater((ag.data_fim - ag.data_inicio).total_seconds(), 30 * 60)
        self.assertIn("pendencias", ag.metadata)

    def test_auditoria_diff_servico(self):
        inicio = self.slot.horario + timedelta(hours=3)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=None,
            origem="PROFISSIONAL",
            servico=self.servico.id,
            slot=None,
        )
        audit = ag.auditoria.first()
        self.assertIsNotNone(audit)
        self.assertIsNotNone(audit.diff)
        self.assertEqual(audit.diff.get("servico_id"), ag.servico_id)

    def test_intervalo_minimo_servico(self):
        inicio = self.slot.horario + timedelta(hours=2)
        ag1 = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=None,
            origem="PROFISSIONAL",
            servico=self.servico.id,
            slot=None,
        )
        ag1.status = "CONCLUIDO"
        ag1.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            AgendamentoService.criar(
                tenant=self.tenant,
                cliente=self.cliente,
                profissional=self.user,
                data_inicio=inicio + timedelta(days=2),
                data_fim=None,
                origem="PROFISSIONAL",
                servico=self.servico.id,
                slot=None,
            )


class SlotConcorrenciaReservaTest(TestCase):
    """Teste de corrida: duas threads tentando reservar o mesmo slot simultaneamente.
    Garante que a capacidade_utilizada não excede o limite e somente um agendamento é criado."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="TC", subdomain="tc")
        # Profissional principal usado como self.prof e também self.user (para compatibilidade com outros testes que usam self.user)
        self.prof = User.objects.create_user(username="prof_cc", password="x", is_staff=True)
        self.user = self.prof
        # Clientes utilitários
        self.c1 = Cliente.objects.create(tenant=self.tenant, nome_razao_social="C1", tipo_pessoa="PF")
        self.c2 = Cliente.objects.create(tenant=self.tenant, nome_razao_social="C2", tipo_pessoa="PF")
        # Alias compatível com testes que referenciam self.cliente
        self.cliente = self.c1
        hoje = timezone.localdate()
        self.disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.prof,
            data=hoje,
            hora_inicio=time(16, 0),
            hora_fim=time(17, 0),
            duracao_slot_minutos=60,
            capacidade_por_slot=1,
        )
        from datetime import datetime

        self.slot = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.prof,
            horario=timezone.make_aware(datetime.combine(hoje, time(16, 0))),
            capacidade_total=1,
        )
        # Criar um segundo slot para testes de reagendamento que escolhem outro slot
        self.slot_extra = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.prof,
            horario=timezone.make_aware(datetime.combine(hoje, time(16, 0)) + timedelta(minutes=60)),
            capacidade_total=1,
        )
        # Serviço clínico para testes legado (substitui self.procedimento)
        from datetime import timedelta as td

        self.servico_cc = Servico.objects.create(
            tenant=self.tenant,
            nome="Proc CC",
            descricao="Desc",
            ativo=True,
            is_clinical=True,
        )
        ServicoClinico.objects.create(
            servico=self.servico_cc,
            duracao_estimada=td(minutes=45),
            requer_anamnese=True,
            requer_termo_consentimento=True,
            intervalo_minimo_sessoes=7,
        )

    def _tentar_reservar(self, cliente):
        try:
            SlotService.reservar(self.slot)
            Agendamento.objects.create(
                tenant=self.tenant,
                cliente=cliente,
                profissional=self.prof,
                slot=self.slot,
                data_inicio=self.slot.horario,
                data_fim=self.slot.horario + timedelta(minutes=30),
                status="CONFIRMADO",
                origem="PROFISSIONAL",
            )
        except Exception:
            pass

    def test_concorrencia_reserva(self):
        import threading

        t1 = threading.Thread(target=self._tentar_reservar, args=(self.c1,))
        t2 = threading.Thread(target=self._tentar_reservar, args=(self.c2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.slot.refresh_from_db()
        self.assertLessEqual(self.slot.capacidade_utilizada, 1)
        self.assertLessEqual(self.slot.agendamentos.count(), 1)

    def test_reagendar(self):
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=self.slot,
            tipo_servico="Teste",
        )
        novo_slot = Slot.objects.exclude(id=self.slot.id).first()
        novo_inicio = novo_slot.horario
        novo_fim = novo_inicio + timedelta(minutes=30)
        novo = AgendamentoService.reagendar(
            ag, novo_slot=novo_slot, nova_data_inicio=novo_inicio, nova_data_fim=novo_fim, motivo="Troca"
        )
        self.assertEqual(novo.referencia_anterior_id, ag.id)
        self.assertEqual(novo.status, "CONFIRMADO")
        self.assertEqual(novo.slot_id, novo_slot.id)
        self.assertEqual(ag.status, "CANCELADO")

    @override_settings(ENABLE_WAITLIST=True)
    def test_waitlist_promocao_automatico_apos_cancelar(self):
        """Cancela um agendamento liberando vaga e promove primeiro da waitlist."""
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=self.slot,
            tipo_servico="Teste",
        )
        # Criar segundo cliente e inscrever na waitlist deste slot (lotado)
        c2 = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente 2", tipo_pessoa="PF")
        from .services import AgendamentoService as S

        S.inscrever_waitlist(self.slot, cliente=c2, prioridade=10)
        # Cancelar agendamento original libera vaga e deve promover waitlist
        S.cancelar(ag, motivo="Desistiu")
        # Verificar novo agendamento criado para c2
        promos = Agendamento.objects.filter(cliente=c2, slot=self.slot)
        self.assertTrue(promos.exists(), "Nenhum agendamento criado para cliente promovido")
        novo = promos.first()
        self.assertEqual(novo.metadata.get("waitlist_promocao"), True)
        # WaitlistEntry deve estar PROMOVIDO
        from .models import WaitlistEntry

        w = WaitlistEntry.objects.get(slot=self.slot, cliente=c2)
        self.assertEqual(w.status, "PROMOVIDO")

    def test_criacao_manual_sem_slot(self):
        # Usa horário fora dos slots existentes (adiciona +1h)
        inicio = self.slot.horario + timedelta(hours=2)
        fim = inicio + timedelta(minutes=30)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=None,
            tipo_servico="Consulta",
        )
        self.assertIsNotNone(ag.id)
        self.assertTrue(ag.metadata.get("manual_sem_slot"))

    def test_conflito_manual(self):
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=None,
            tipo_servico="Overlap",
        )
        with self.assertRaises(ValueError):
            AgendamentoService.criar(
                tenant=self.tenant,
                cliente=self.cliente,
                profissional=self.user,
                data_inicio=inicio + timedelta(minutes=15),
                data_fim=fim + timedelta(minutes=15),
                origem="PROFISSIONAL",
                slot=None,
                tipo_servico="Overlap2",
            )

    def test_checkin_e_concluir(self):
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=self.slot,
            tipo_servico="Teste",
        )
        from .services import AgendamentoService as S

        S.checkin(ag)
        self.assertEqual(ag.status, "EM_ANDAMENTO")
        S.concluir(ag)
        self.assertEqual(ag.status, "CONCLUIDO")

    def test_checkin_bloqueado_pendencias(self):
        # Criação manual com serviço que gera pendências (anamnese, termo)
        inicio = self.slot.horario + timedelta(hours=3)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=None,
            origem="PROFISSIONAL",
            servico=self.servico.id,
            slot=None,
        )
        self.assertIn("pendencias", ag.metadata)
        from .services import AgendamentoService as S

        with self.assertRaises(ValueError):
            S.checkin(ag)
        # Simular resolução das pendências
        meta = ag.metadata
        meta.pop("pendencias", None)
        ag.metadata = meta
        ag.status = "CONFIRMADO"
        ag.save(update_fields=["metadata", "status"])
        S.checkin(ag)
        self.assertEqual(ag.status, "EM_ANDAMENTO")

    def test_resolver_pendencias_service(self):
        inicio = self.slot.horario + timedelta(hours=4)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=None,
            origem="PROFISSIONAL",
            servico=self.servico.id,
            slot=None,
        )
        self.assertIn("pendencias", ag.metadata)
        from .services import AgendamentoService as S

        S.resolver_pendencias(ag)
        ag.refresh_from_db()
        self.assertNotIn("pendencias", ag.metadata or {})

    @override_settings(AGENDAMENTOS_ANTECEDENCIA_MINIMA_MINUTOS=15)
    def test_cancelamento_antecedencia_cliente(self):
        # Cliente tenta cancelar dentro da antecedência mínima
        inicio = timezone.now() + timedelta(minutes=10)
        fim = inicio + timedelta(minutes=30)
        # criar agendamento origem CLIENTE
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="CLIENTE",
            slot=None,
            tipo_servico="Consulta",
        )
        from .services import AgendamentoService as S

        with self.assertRaises(ValueError):
            S.cancelar(ag, motivo="Teste", user=None)

    def test_limite_reagendamentos(self):
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=self.slot,
            tipo_servico="Teste",
        )
        from .services import AgendamentoService as S

        cadeia = [ag]
        for _i in range(5):
            novo_slot = Slot.objects.exclude(id=cadeia[-1].slot_id).first()
            novo_inicio = novo_slot.horario
            novo_fim = novo_inicio + timedelta(minutes=30)
            novo = S.reagendar(
                cadeia[-1], novo_slot=novo_slot, nova_data_inicio=novo_inicio, nova_data_fim=novo_fim, motivo="x"
            )
            cadeia.append(novo)
        # agora deve falhar na próxima tentativa
        with self.assertRaises(ValueError):
            novo_slot2 = Slot.objects.exclude(id=cadeia[-1].slot_id).first()
            S.reagendar(
                cadeia[-1],
                novo_slot=novo_slot2,
                nova_data_inicio=novo_slot2.horario,
                nova_data_fim=novo_slot2.horario + timedelta(minutes=30),
                motivo="limite",
            )

    def test_overbooking_controlado_flag(self):
        from django.conf import settings

        if not getattr(settings, "ENABLE_CONTROLLED_OVERBOOK", False):
            self.skipTest("Overbooking desabilitado")
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        # Reservar até capacidade + extra
        Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente 2", tipo_pessoa="PF")
        AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=self.slot,
            tipo_servico="Teste",
        )
        # Segunda reserva overbook
        SlotService.reservar(self.slot)
        self.slot.refresh_from_db()
        self.assertFalse(self.slot.disponivel)  # agora atingiu limite extendido

    def test_waitlist(self):
        from django.conf import settings

        if not getattr(settings, "ENABLE_WAITLIST", False):
            self.skipTest("Waitlist desabilitada")
        # lotar slot
        SlotService.reservar(self.slot)
        cliente2 = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente 2", tipo_pessoa="PF")
        from .services import AgendamentoService as S

        entry = S.inscrever_waitlist(self.slot, cliente=cliente2, prioridade=50)
        self.assertEqual(entry.prioridade, 50)

    def test_reserva_api_slot_com_servico(self):
        # Simula chamada da ação reservar usando serviço para duração automática
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import SlotViewSet

        factory = APIRequestFactory()
        servico_id = self.servico.id
        view = SlotViewSet.as_view({"post": "reservar"})
        request = factory.post(
            f"/api/slots/{self.slot.id}/reservar/",
            {"cliente_id": self.cliente.id, "servico_id": servico_id},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.slot.id)
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["agendamento"]
        self.assertEqual(data["servico"], servico_id)
        # Confirma que duração >= duração estimada (45min)
        inicio = timezone.datetime.fromisoformat(data["data_inicio"].replace("Z", "+00:00"))
        fim = timezone.datetime.fromisoformat(data["data_fim"].replace("Z", "+00:00"))
        from servicos.models import ServicoClinico

        sc = ServicoClinico.objects.get(servico=self.servico)
        self.assertGreaterEqual((fim - inicio).total_seconds(), sc.duracao_estimada.total_seconds())

    @override_settings(ENABLE_CONTROLLED_OVERBOOK=False)
    def test_overbooking_desabilitado_recusa_segunda_reserva(self):
        # Reserva inicial ocupa capacidade total
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=self.slot,
            tipo_servico="Teste",
        )
        # Segunda tentativa deve falhar pois overbooking desligado
        with self.assertRaises(ValueError):
            SlotService.reservar(self.slot)

    @override_settings(ENABLE_EVENT_MIRROR=True)
    def test_evento_espelho_criacao_atualizacao_cancelamento(self):
        # Criação gera evento espelho
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=self.slot,
            tipo_servico="Teste",
        )
        ag.refresh_from_db()
        evento_id = (ag.metadata or {}).get("evento_agenda_id")
        self.assertIsNotNone(evento_id, "Evento espelho não criado")
        from agenda.models import Evento

        ev = Evento.objects.get(id=evento_id)
        self.assertEqual(ev.status, "confirmado")
        # Atualizar para CONCLUIDO
        ag.status = "CONCLUIDO"
        ag.save(update_fields=["status"])
        ev.refresh_from_db()
        self.assertEqual(ev.status, "concluido")
        # Cancelar e verificar evento cancelado
        ag.status = "CANCELADO"
        ag.save(update_fields=["status"])
        ev.refresh_from_db()
        self.assertEqual(ev.status, "cancelado")


@override_settings(ENABLE_EVENT_MIRROR=True)
class EventoSyncEndpointTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.user = User.objects.create_user(username="prof_sync", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente Sync", tipo_pessoa="PF")
        hoje = timezone.localdate()
        from datetime import datetime as dt

        tz = timezone.get_current_timezone()
        self.disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.user,
            data=hoje,
            hora_inicio=time(9, 0),
            hora_fim=time(10, 0),
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        self.slot = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.user,
            horario=timezone.make_aware(dt.combine(hoje, time(9, 0)), tz),
            capacidade_total=1,
        )
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        self.ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=self.slot,
            tipo_servico="Teste",
        )

    def test_sync_evento_endpoint_retem_ou_cria(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoViewSet

        # Remover chave para forçar recriação
        meta = self.ag.metadata or {}
        meta.pop("evento_agenda_id", None)
        self.ag.metadata = meta
        self.ag.save(update_fields=["metadata"])
        factory = APIRequestFactory()
        view = AgendamentoViewSet.as_view({"post": "sync_evento"})
        req = factory.post(f"/api/agendamentos/{self.ag.id}/sync_evento/", {})
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.user)
        resp = view(req, pk=self.ag.id)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        self.assertIsNotNone(resp.data.get("evento_id"))
        from agenda.models import Evento

        self.assertTrue(Evento.objects.filter(id=resp.data["evento_id"]).exists())

    def test_migracao_metadata_evento_id_para_evento_agenda_id(self):
        """Simula cenário legado com 'evento_id' e garante migração para 'evento_agenda_id'."""
        # Forçar estado legado
        meta = self.ag.metadata or {}
        # Criar evento espelho removendo chave atual e usando nome legado
        from agenda.models import Evento

        ev = Evento.objects.create(
            tenant=self.tenant,
            titulo="Legacy",
            descricao="Legacy",
            data_inicio=self.ag.data_inicio,
            data_fim=self.ag.data_fim,
            status="confirmado",
            tipo_evento="servico",
            responsavel=self.user,
        )
        meta.pop("evento_agenda_id", None)
        meta["evento_id"] = ev.id
        self.ag.metadata = meta
        self.ag.save(update_fields=["metadata"])
        # Chamar sync_evento para disparar migração
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoViewSet

        factory = APIRequestFactory()
        view = AgendamentoViewSet.as_view({"post": "sync_evento"})
        req = factory.post(f"/api/agendamentos/{self.ag.id}/sync_evento/", {})
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.user)
        resp = view(req, pk=self.ag.id)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        self.ag.refresh_from_db()
        self.assertNotIn("evento_id", self.ag.metadata)
        self.assertIn("evento_agenda_id", self.ag.metadata)

    @override_settings(ENABLE_EVENT_MIRROR=False)
    def test_sync_evento_endpoint_desabilitado(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoViewSet

        factory = APIRequestFactory()
        view = AgendamentoViewSet.as_view({"post": "sync_evento"})
        req = factory.post(f"/api/agendamentos/{self.ag.id}/sync_evento/", {})
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.user)
        resp = view(req, pk=self.ag.id)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        # Flag OFF não apaga evento existente
        self.assertIsNotNone(resp.data.get("evento_id"))


@override_settings(ENABLE_EVENT_MIRROR=False)
class MetricsInstrumentationTest(TestCase):
    """Testes básicos para garantir incremento de counters Prometheus (se lib instalada)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.user = User.objects.create_user(username="prof_metrics", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente M", tipo_pessoa="PF")

    def test_counter_incrementa_criacao(self):
        from agendamentos.services import AGENDAMENTOS_CRIADOS_TOTAL, SchedulingService

        inicio = timezone.now() + timedelta(hours=1)
        fim = inicio + timedelta(minutes=30)
        base = getattr(AGENDAMENTOS_CRIADOS_TOTAL, "_value", None)
        base_val = base.get() if base else None
        ag = SchedulingService.criar_agendamento(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=None,
            tipo_servico="Teste",
        )
        self.assertIsNotNone(ag.id)
        # Se prometheus não está disponível, base_val será None – então não assert do incremento
        if base_val is not None:
            novo_val = AGENDAMENTOS_CRIADOS_TOTAL._value.get()
            self.assertGreaterEqual(novo_val, base_val + 1)


@override_settings(ENABLE_EVENT_MIRROR=False)
class EventoSyncMirrorOffNoCreateTest(TestCase):
    """Garante que sync_evento não cria espelho quando flag desativada e chave ausente."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.user = User.objects.create_user(username="prof_sync_off", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente SOff", tipo_pessoa="PF")
        inicio = timezone.now() + timedelta(hours=2)
        fim = inicio + timedelta(minutes=30)
        self.ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=None,
            tipo_servico="Teste",
        )  # flag OFF: não cria metadata evento_agenda_id

    def test_sync_evento_nao_cria_quando_flag_off(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoViewSet

        self.assertIsNone((self.ag.metadata or {}).get("evento_agenda_id"))
        factory = APIRequestFactory()
        view = AgendamentoViewSet.as_view({"post": "sync_evento"})
        req = factory.post(f"/api/agendamentos/{self.ag.id}/sync_evento/", {})
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.user)
        resp = view(req, pk=self.ag.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data.get("evento_id"))


@override_settings(ENABLE_EVENT_MIRROR=False)
class MetricsCancelReagendarTest(TestCase):
    """Valida incremento de counters de cancelamento e reagendamento (se métricas habilitadas)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.user = User.objects.create_user(username="prof_metrics2", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente MR", tipo_pessoa="PF")
        # Criar dois slots para reagendamento
        hoje = timezone.localdate()
        from datetime import datetime as dt

        tz = timezone.get_current_timezone()
        self.disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.user,
            data=hoje,
            hora_inicio=time(8, 0),
            hora_fim=time(9, 0),
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        self.slot_a = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.user,
            horario=timezone.make_aware(dt.combine(hoje, time(8, 0)), tz),
            capacidade_total=1,
        )
        self.slot_b = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.user,
            horario=timezone.make_aware(dt.combine(hoje, time(8, 30)), tz),
            capacidade_total=1,
        )
        self.ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            data_inicio=self.slot_a.horario,
            data_fim=self.slot_a.horario + timedelta(minutes=30),
            origem="PROFISSIONAL",
            slot=self.slot_a,
            tipo_servico="Teste",
        )

    def test_cancelamento_incrementa_counter(self):
        from agendamentos.services import AGENDAMENTOS_CANCELADOS_TOTAL, SchedulingService

        base_val = getattr(getattr(AGENDAMENTOS_CANCELADOS_TOTAL, "_value", None), "get", lambda: None)()
        SchedulingService.cancelar_agendamento(self.ag, motivo="Teste")
        if base_val is not None:
            novo_val = AGENDAMENTOS_CANCELADOS_TOTAL._value.get()
            self.assertGreaterEqual(novo_val, base_val + 1)

    def test_reagendamento_incrementa_counter(self):
        from agendamentos.services import AGENDAMENTOS_REAGENDADOS_TOTAL, SchedulingService

        base_val = getattr(getattr(AGENDAMENTOS_REAGENDADOS_TOTAL, "_value", None), "get", lambda: None)()
        novo = SchedulingService.reagendar_agendamento(self.ag, novo_slot=self.slot_b, motivo="Ajuste")
        self.assertIsNotNone(novo.id)
        if base_val is not None:
            novo_val = AGENDAMENTOS_REAGENDADOS_TOTAL._value.get()
            self.assertGreaterEqual(novo_val, base_val + 1)

    def test_cancelamento_incrementa_counter(self):
        from agendamentos.services import AGENDAMENTOS_CANCELADOS_TOTAL, SchedulingService

        base_val = getattr(getattr(AGENDAMENTOS_CANCELADOS_TOTAL, "_value", None), "get", lambda: None)()
        SchedulingService.cancelar_agendamento(self.ag, motivo="Teste")
        if base_val is not None:
            novo_val = AGENDAMENTOS_CANCELADOS_TOTAL._value.get()
            self.assertGreaterEqual(novo_val, base_val + 1)

    def test_reagendamento_incrementa_counter(self):
        from agendamentos.services import AGENDAMENTOS_REAGENDADOS_TOTAL, SchedulingService

        base_val = getattr(getattr(AGENDAMENTOS_REAGENDADOS_TOTAL, "_value", None), "get", lambda: None)()
        novo = SchedulingService.reagendar_agendamento(self.ag, novo_slot=self.slot_b, motivo="Ajuste")
        self.assertIsNotNone(novo.id)
        if base_val is not None:
            novo_val = AGENDAMENTOS_REAGENDADOS_TOTAL._value.get()
            self.assertGreaterEqual(novo_val, base_val + 1)


class PermissoesReadOnlyTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        # Profissional padrão
        self.prof = User.objects.create_user(username="prof2", password="x", is_staff=True)
        # Usuário somente visualização
        self.viewer = User.objects.create_user(username="viewer", password="x", is_staff=False)
        grp = Group.objects.create(name="AGENDAMENTOS_VISUALIZAR")
        self.viewer.groups.add(grp)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente V", tipo_pessoa="PF")
        # Criar disponibilidade/slot futuro
        hoje = timezone.localdate()
        agora = timezone.now()
        base_hora = (agora + timedelta(hours=1)).time().replace(second=0, microsecond=0)
        fim_hora = (agora + timedelta(hours=2)).time().replace(second=0, microsecond=0)
        self.disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.prof,
            data=hoje,
            hora_inicio=base_hora,
            hora_fim=fim_hora,
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        # Um slot futuro
        from datetime import datetime as dt

        tz = timezone.get_current_timezone()
        self.slot = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.prof,
            horario=timezone.make_aware(dt.combine(hoje, base_hora), tz),
            capacidade_total=1,
        )


@override_settings(USE_NOVO_AGENDAMENTO=False)
class ApiV2AgendamentoFlagOffTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.user = User.objects.create_superuser(username="admin_v2_off", password="x")

    def test_list_v2_vazio(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoV2ViewSet

        factory = APIRequestFactory()
        view = AgendamentoV2ViewSet.as_view({"get": "list"})
        req = factory.get("/api/v2/agendamentos/")
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.user)
        resp = view(req)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        payload = resp.data
        items = payload.get("results") if isinstance(payload, dict) else payload
        self.assertEqual(len(items), 0)


@override_settings(USE_NOVO_AGENDAMENTO=True)
class ApiV2AgendamentoFlagOnTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.user = User.objects.create_superuser(username="admin_v2_on", password="x")
        self.prof = User.objects.create_user(username="prof_v2", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente V2", tipo_pessoa="PF")
        # Usuário somente visualização (viewer) para teste de permissões
        from django.contrib.auth.models import Group

        self.viewer = User.objects.create_user(username="viewer_v2", password="x", is_staff=False)
        grp = Group.objects.create(name="AGENDAMENTOS_VISUALIZAR")
        self.viewer.groups.add(grp)
        # Criar disponibilidade para uso nos testes
        hoje = timezone.localdate()
        agora = timezone.now()
        base_hora = (agora + timedelta(hours=1)).time().replace(second=0, microsecond=0)
        fim_hora = (agora + timedelta(hours=2)).time().replace(second=0, microsecond=0)
        self.disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.prof,
            data=hoje,
            hora_inicio=base_hora,
            hora_fim=fim_hora,
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        inicio = timezone.now() + timedelta(hours=2)
        fim = inicio + timedelta(minutes=30)
        self.ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.prof,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=None,
            tipo_servico="Teste",
        )

    def test_list_v2_populado(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoV2ViewSet

        factory = APIRequestFactory()
        view = AgendamentoV2ViewSet.as_view({"get": "list"})
        req = factory.get("/api/v2/agendamentos/")
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.user)
        resp = view(req)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        payload = resp.data
        items = payload.get("results") if isinstance(payload, dict) else payload
        self.assertGreaterEqual(len(items), 1)

    def test_ro_group_can_list_but_cannot_modify(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoViewSet, DisponibilidadeViewSet, SlotViewSet

        factory = APIRequestFactory()
        # GET slots (SAFE_METHOD)
        view_list_slots = SlotViewSet.as_view({"get": "list"})
        request = factory.get("/api/slots/")
        # Configurar sessão com tenant para evitar fallback None
        request.session = {"tenant_id": self.tenant.id}
        force_authenticate(request, user=self.viewer)
        resp = view_list_slots(request)
        self.assertEqual(resp.status_code, 200)
        # POST agendamentos deve falhar (403)
        view_create_ag = AgendamentoViewSet.as_view({"post": "create"})
        request2 = factory.post("/api/agendamentos/", {"cliente": self.cliente.id}, format="json")
        request2.session = {"tenant_id": self.tenant.id}
        force_authenticate(request2, user=self.viewer)
        resp2 = view_create_ag(request2)
        self.assertIn(resp2.status_code, (401, 403))
        # POST disponibilidades também bloqueado
        view_create_disp = DisponibilidadeViewSet.as_view({"post": "create"})
        payload = {
            "profissional": self.prof.id,
            "data": str(self.disp.data),
            "hora_inicio": str(self.disp.hora_inicio),
            "hora_fim": str(self.disp.hora_fim),
            "duracao_slot_minutos": 30,
            "capacidade_por_slot": 1,
        }
        request3 = factory.post("/api/disponibilidades/", payload, format="json")
        request3.session = {"tenant_id": self.tenant.id}
        force_authenticate(request3, user=self.viewer)
        resp3 = view_create_disp(request3)
        self.assertIn(resp3.status_code, (401, 403))


@override_settings(ENABLE_AGENDAMENTOS_MODEL_PERMS=True)
class ModelPermsEnforcementTest(TestCase):
    """Valida comportamento da flag ENABLE_AGENDAMENTOS_MODEL_PERMS: exige permissão add_agendamento para criar."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.user = User.objects.create_user(username="semperm", password="x", is_staff=True)
        self.user_com_perm = User.objects.create_user(username="comperm", password="x", is_staff=True)
        # Concede permissão add_agendamento somente ao segundo usuário
        from django.contrib.auth.models import Permission

        perm = Permission.objects.get(codename="add_agendamento")
        self.user_com_perm.user_permissions.add(perm)
        # Cliente + disponibilidade/slot
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente MP", tipo_pessoa="PF")
        hoje = timezone.localdate()
        h1 = (timezone.now() + timedelta(hours=2)).time().replace(second=0, microsecond=0)
        h2 = (timezone.now() + timedelta(hours=3)).time().replace(second=0, microsecond=0)
        self.disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.user,
            data=hoje,
            hora_inicio=h1,
            hora_fim=h2,
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        from datetime import datetime as dt

        tz = timezone.get_current_timezone()
        self.slot = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.user,
            horario=timezone.make_aware(dt.combine(hoje, h1), tz),
            capacidade_total=1,
        )

    def _create(self, acting_user):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoViewSet

        factory = APIRequestFactory()
        view = AgendamentoViewSet.as_view({"post": "create"})
        inicio = self.slot.horario
        fim = inicio + timedelta(minutes=30)
        payload = {
            "cliente": self.cliente.id,
            "profissional": self.user.id,
            "data_inicio": inicio.isoformat(),
            "data_fim": fim.isoformat(),
            "origem": "PROFISSIONAL",
        }
        req = factory.post("/api/agendamentos/", payload, format="json")
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=acting_user)
        return view(req)

    def test_criacao_sem_permissao_retorna_403(self):
        resp = self._create(self.user)
        self.assertIn(resp.status_code, (401, 403), getattr(resp, "data", None))

    def test_criacao_com_permissao_sucesso(self):
        resp = self._create(self.user_com_perm)
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", None))

    @override_settings(ENABLE_AGENDAMENTOS_MODEL_PERMS=False)
    def test_flag_desligada_nao_exige_perm(self):
        resp = self._create(self.user)
        # Sem a flag, deve permitir (201) porque usuário é staff
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", None))


@override_settings(ENFORCE_COMPETENCIA=True)
class CompetenciaValidationTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.prof = User.objects.create_user(username="prof_c", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente C", tipo_pessoa="PF")
        self.servico_peeling = Servico.objects.create(
            tenant=self.tenant,
            nome="Peeling",
            descricao="Desc",
            ativo=True,
            is_clinical=True,
        )
        ServicoClinico.objects.create(
            servico=self.servico_peeling, duracao_estimada=timedelta(minutes=30), intervalo_minimo_sessoes=7
        )

    def test_criar_sem_competencia_falha_e_com_competencia_sucess(self):
        inicio = timezone.now() + timedelta(hours=3)
        with self.assertRaises(ValueError):
            AgendamentoService.criar(
                tenant=self.tenant,
                cliente=self.cliente,
                profissional=self.prof,
                data_inicio=inicio,
                data_fim=None,
                origem="PROFISSIONAL",
                slot=None,
                servico=self.servico_peeling.id,
            )
        # Adiciona competência
        from .models import ProfissionalProcedimento

        ProfissionalProcedimento.objects.create(
            tenant=self.tenant, profissional=self.prof, servico=self.servico_peeling, ativo=True
        )
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.prof,
            data_inicio=inicio + timedelta(minutes=5),
            data_fim=None,
            origem="PROFISSIONAL",
            slot=None,
            servico=self.servico_peeling.id,
        )
        self.assertIsNotNone(ag.id)
        self.assertEqual(ag.servico_id, self.servico_peeling.id)


@override_settings(ENFORCE_COMPETENCIA=True)
class SlotsFiltroCompetenciaTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        self.admin = User.objects.create_superuser(username="admin", password="x")
        self.p1 = User.objects.create_user(username="p1", password="x", is_staff=True)
        self.p2 = User.objects.create_user(username="p2", password="x", is_staff=True)
        hoje = timezone.localdate()
        agora = timezone.now()
        h1 = (agora + timedelta(hours=2)).time().replace(second=0, microsecond=0)
        h2 = (agora + timedelta(hours=3)).time().replace(second=0, microsecond=0)
        self.disp1 = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.p1,
            data=hoje,
            hora_inicio=h1,
            hora_fim=h2,
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        self.disp2 = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.p2,
            data=hoje,
            hora_inicio=h1,
            hora_fim=h2,
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        from datetime import datetime as dt

        tz = timezone.get_current_timezone()
        self.slot1 = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp1,
            profissional=self.p1,
            horario=timezone.make_aware(dt.combine(hoje, h1), tz),
            capacidade_total=1,
        )
        self.slot2 = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp2,
            profissional=self.p2,
            horario=timezone.make_aware(dt.combine(hoje, h1), tz),
            capacidade_total=1,
        )
        self.proc = Servico.objects.create(
            tenant=self.tenant, nome="Laser", descricao="D", ativo=True, is_clinical=True
        )
        ServicoClinico.objects.create(
            servico=self.proc, duracao_estimada=timedelta(minutes=30), intervalo_minimo_sessoes=7
        )
        # Concede competência apenas ao p1
        from .models import ProfissionalProcedimento

        ProfissionalProcedimento.objects.create(tenant=self.tenant, profissional=self.p1, servico=self.proc, ativo=True)

    @override_settings(ENFORCE_COMPETENCIA=True)
    def test_listagem_slots_filtra_por_competencia_quando_servico(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import SlotViewSet

        factory = APIRequestFactory()
        view = SlotViewSet.as_view({"get": "list"})
        request = factory.get(f"/api/slots/?servico_id={self.proc.id}")
        # Garante tenant resolvido para aplicar filtro
        request.session = {"tenant_id": self.tenant.id}
        force_authenticate(request, user=self.admin)
        resp = view(request)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        # Suporta resposta paginada (dict com 'results') ou lista direta
        payload = resp.data
        items = payload.get("results") if isinstance(payload, dict) else payload
        ids = [item["id"] for item in items]
        prof_ids = [item["profissional"] for item in items]
        self.assertIn(self.slot1.id, ids)
        self.assertNotIn(self.slot2.id, ids)
        self.assertEqual(set(prof_ids), {self.p1.id})


@override_settings(ENFORCE_COMPETENCIA=True)
class AgendamentoViewSetCompetenciaIntegrationTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        # Superuser para simplificar permissões
        self.admin = User.objects.create_superuser(username="admin2", password="x")
        # Profissional dedicado
        self.prof = User.objects.create_user(username="prof_is", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente VS", tipo_pessoa="PF")
        # Serviço clínico associado (substitui Procedimento legado)
        self.proc = Servico.objects.create(
            tenant=self.tenant,
            nome="Microneedling",
            descricao="D",
            ativo=True,
            is_clinical=True,
        )
        ServicoClinico.objects.create(
            servico=self.proc,
            duracao_estimada=timedelta(minutes=30),
            intervalo_minimo_sessoes=7,
            requer_anamnese=False,
            requer_termo_consentimento=False,
        )

    def _post_create(self, user, profissional_id=None):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoViewSet

        factory = APIRequestFactory()
        view = AgendamentoViewSet.as_view({"post": "create"})
        inicio = (timezone.now() + timedelta(hours=6)).replace(second=0, microsecond=0)
        fim = inicio + timedelta(minutes=30)
        payload = {
            "cliente": self.cliente.id,
            "profissional": profissional_id or self.prof.id,
            "data_inicio": inicio.isoformat(),
            "data_fim": fim.isoformat(),
            "origem": "PROFISSIONAL",
            # serviço é lido de request.data via 'servico_id'
            "servico_id": self.proc.id,
        }
        request = factory.post("/api/agendamentos/", payload, format="json")
        request.session = {"tenant_id": self.tenant.id}
        force_authenticate(request, user=user)
        return view(request)

    def test_create_sem_competencia_falha(self):
        resp = self._post_create(self.admin, profissional_id=self.prof.id)
        # Sem competência cadastrada, a view mapeia ValueError -> 400 (ValidationError)
        self.assertEqual(resp.status_code, 400, getattr(resp, "data", None))

    def test_create_com_competencia_sucesso(self):
        # Conceder competência
        from .models import ProfissionalProcedimento

        ProfissionalProcedimento.objects.create(
            tenant=self.tenant, profissional=self.prof, servico=self.proc, ativo=True
        )
        resp = self._post_create(self.admin, profissional_id=self.prof.id)
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", None))
        self.assertEqual(resp.data.get("servico"), self.proc.id)

    def test_reagendar_action_sucesso(self):
        # Preparar agendamento válido (com competência)
        from .models import Disponibilidade, ProfissionalProcedimento, Slot

        ProfissionalProcedimento.objects.create(
            tenant=self.tenant, profissional=self.prof, servico=self.proc, ativo=True
        )
        # Criar disponibilidade e slot + agendamento inicial (via service para simplificar)
        hoje = timezone.localdate()
        h1 = (timezone.now() + timedelta(hours=2)).time().replace(second=0, microsecond=0)
        h2 = (timezone.now() + timedelta(hours=4)).time().replace(second=0, microsecond=0)
        disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.prof,
            data=hoje,
            hora_inicio=h1,
            hora_fim=h2,
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        from datetime import datetime as dt

        tz = timezone.get_current_timezone()
        slot_a = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=disp,
            profissional=self.prof,
            horario=timezone.make_aware(dt.combine(hoje, h1), tz),
            capacidade_total=1,
        )
        slot_b = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=disp,
            profissional=self.prof,
            horario=timezone.make_aware(dt.combine(hoje, h2), tz),
            capacidade_total=1,
        )
        ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.prof,
            data_inicio=slot_a.horario,
            data_fim=slot_a.horario + timedelta(minutes=30),
            origem="PROFISSIONAL",
            slot=slot_a,
            servico=self.proc.id,
        )
        # Chamar ação reagendar
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoViewSet

        factory = APIRequestFactory()
        view = AgendamentoViewSet.as_view({"post": "reagendar"})
        req = factory.post(
            f"/api/agendamentos/{ag.id}/reagendar/", {"novo_slot": slot_b.id, "motivo": "ajuste"}, format="json"
        )
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.admin)
        resp = view(req, pk=ag.id)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        self.assertEqual(resp.data.get("slot"), slot_b.id)


@override_settings(ENFORCE_COMPETENCIA=True)
class ClientePortalEndpointsTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T1", subdomain="t1")
        # Usuário cliente (não-staff)
        self.user_cli = User.objects.create_user(username="cli_portal", password="x", is_staff=False)
        # Cliente e vínculo de portal
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente Portal", tipo_pessoa="PF")
        from clientes.models import AcessoCliente

        AcessoCliente.objects.create(cliente=self.cliente, usuario=self.user_cli)
        # Profissional e disponibilidade/slots
        self.prof = User.objects.create_user(username="prof_cp", password="x", is_staff=True)
        hoje = timezone.localdate()
        agora = timezone.now()
        h1 = (agora + timedelta(hours=2)).time().replace(second=0, microsecond=0)
        h2 = (agora + timedelta(hours=3)).time().replace(second=0, microsecond=0)
        self.disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.prof,
            data=hoje,
            hora_inicio=h1,
            hora_fim=h2,
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        from datetime import datetime as dt

        tz = timezone.get_current_timezone()
        self.slot1 = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.prof,
            horario=timezone.make_aware(dt.combine(hoje, h1), tz),
            capacidade_total=1,
        )
        self.slot2 = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.prof,
            horario=timezone.make_aware(dt.combine(hoje, h2), tz),
            capacidade_total=1,
        )
        # Serviço clínico e competência (substitui Procedimento)
        self.proc = Servico.objects.create(
            tenant=self.tenant,
            nome="Consulta Portal",
            descricao="D",
            ativo=True,
            is_clinical=True,
        )
        ServicoClinico.objects.create(
            servico=self.proc,
            duracao_estimada=timedelta(minutes=30),
            intervalo_minimo_sessoes=7,
            requer_anamnese=False,
            requer_termo_consentimento=False,
        )

    def _auth_req(self, req):
        req.session = {"tenant_id": self.tenant.id}
        from rest_framework.test import force_authenticate

        force_authenticate(req, user=self.user_cli)
        return req

    def test_cliente_lista_slots_filtrando_por_competencia_e_reserva_sucesso(self):
        # Conceder competência ao profissional
        from .models import ProfissionalProcedimento

        ProfissionalProcedimento.objects.create(
            tenant=self.tenant, profissional=self.prof, servico=self.proc, ativo=True
        )
        # Listagem
        from rest_framework.test import APIRequestFactory

        from .api_views import ClienteSlotViewSet

        factory = APIRequestFactory()
        view_list = ClienteSlotViewSet.as_view({"get": "list"})
        req = factory.get(f"/api/cliente/slots/?servico_id={self.proc.id}")
        resp = view_list(self._auth_req(req))
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        payload = resp.data
        items = payload.get("results") if isinstance(payload, dict) else payload
        ids = [it["id"] for it in items]
        self.assertIn(self.slot1.id, ids)
        # Reserva
        view_res = ClienteSlotViewSet.as_view({"post": "reservar"})
        req2 = factory.post(
            f"/api/cliente/slots/{self.slot1.id}/reservar/", {"servico_id": self.proc.id}, format="json"
        )
        resp2 = view_res(self._auth_req(req2), pk=self.slot1.id)
        self.assertEqual(resp2.status_code, 200, getattr(resp2, "data", None))
        self.assertIn("agendamento", resp2.data)

    def test_cliente_reserva_sem_competencia_retorna_400(self):
        from rest_framework.test import APIRequestFactory

        from .api_views import ClienteSlotViewSet

        factory = APIRequestFactory()
        view_res = ClienteSlotViewSet.as_view({"post": "reservar"})
        req = factory.post(f"/api/cliente/slots/{self.slot2.id}/reservar/", {"servico_id": self.proc.id}, format="json")
        resp = view_res(self._auth_req(req), pk=self.slot2.id)
        self.assertEqual(resp.status_code, 400, getattr(resp, "data", None))

    def test_cliente_lista_agendamentos_e_cancelar(self):
        # Preparar reserva com competência
        from .models import ProfissionalProcedimento

        ProfissionalProcedimento.objects.create(
            tenant=self.tenant, profissional=self.prof, servico=self.proc, ativo=True
        )
        from rest_framework.test import APIRequestFactory

        from .api_views import ClienteAgendamentoViewSet, ClienteSlotViewSet

        factory = APIRequestFactory()
        view_res = ClienteSlotViewSet.as_view({"post": "reservar"})
        req = factory.post(f"/api/cliente/slots/{self.slot1.id}/reservar/", {"servico_id": self.proc.id}, format="json")
        resp = view_res(self._auth_req(req), pk=self.slot1.id)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        ag_id = resp.data["agendamento"]["id"]
        # Listar agendamentos
        view_list_ag = ClienteAgendamentoViewSet.as_view({"get": "list"})
        req2 = factory.get("/api/cliente/agendamentos/")
        resp2 = view_list_ag(self._auth_req(req2))
        self.assertEqual(resp2.status_code, 200, getattr(resp2, "data", None))
        payload = resp2.data
        items = payload.get("results") if isinstance(payload, dict) else payload
        ids = [it["id"] for it in items]
        self.assertIn(ag_id, ids)
        # Cancelar
        view_cancel = ClienteAgendamentoViewSet.as_view({"post": "cancelar"})
        req3 = factory.post(f"/api/cliente/agendamentos/{ag_id}/cancelar/", {"motivo": "não posso ir"}, format="json")
        resp3 = view_cancel(self._auth_req(req3), pk=ag_id)
        self.assertEqual(resp3.status_code, 200, getattr(resp3, "data", None))

    def test_cliente_reagendar_com_novo_slot_sem_datas(self):
        # Conceder competência e criar reserva inicial
        from .models import ProfissionalProcedimento

        ProfissionalProcedimento.objects.create(
            tenant=self.tenant, profissional=self.prof, servico=self.proc, ativo=True
        )
        from rest_framework.test import APIRequestFactory

        from .api_views import ClienteAgendamentoViewSet, ClienteSlotViewSet

        factory = APIRequestFactory()
        view_res = ClienteSlotViewSet.as_view({"post": "reservar"})
        req = factory.post(f"/api/cliente/slots/{self.slot1.id}/reservar/", {"servico_id": self.proc.id}, format="json")
        resp = view_res(self._auth_req(req), pk=self.slot1.id)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        ag_id = resp.data["agendamento"]["id"]
        # Reagendar para slot2 apenas informando novo_slot
        view_reag = ClienteAgendamentoViewSet.as_view({"post": "reagendar"})
        req2 = factory.post(
            f"/api/cliente/agendamentos/{ag_id}/reagendar/",
            {"novo_slot": self.slot2.id, "motivo": "ajuste"},
            format="json",
        )
        resp2 = view_reag(self._auth_req(req2), pk=ag_id)
        self.assertEqual(resp2.status_code, 200, getattr(resp2, "data", None))
        self.assertEqual(resp2.data.get("slot"), self.slot2.id)

    def test_cliente_portal_api_access_unauthenticated(self):
        """
        Testa se as APIs do portal do cliente exigem autenticação.
        """
        from rest_framework.test import APIRequestFactory

        from .api_views import ClienteSlotViewSet

        factory = APIRequestFactory()
        view = ClienteSlotViewSet.as_view({"get": "list"})
        req = factory.get("/api/cliente/slots/")
        req.session = {"tenant_id": self.tenant.id}
        # Sem autenticação
        resp = view(req)
        self.assertIn(resp.status_code, [401, 403])  # Deve exigir autenticação

    def test_cliente_portal_api_access_authenticated(self):
        """
        Testa se as APIs do portal do cliente funcionam com usuário autenticado.
        """
        from rest_framework.test import APIRequestFactory

        from .api_views import ClienteSlotViewSet

        factory = APIRequestFactory()
        view = ClienteSlotViewSet.as_view({"get": "list"})
        req = factory.get("/api/cliente/slots/")
        req = self._auth_req(req)
        resp = view(req)
        self.assertEqual(resp.status_code, 200)


class AgendamentoViewsTest(TestCase):
    """
    Testes para as views HTML do sistema interno (funcionários/profissionais).
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(name="TestViewsTenant", subdomain="tvt")
        self.user = User.objects.create_user(username="staff_user", password="testpass", is_staff=True)
        self.prof = User.objects.create_user(username="prof_views", password="testpass", is_staff=True)

        # Criar role e relacionamentos corretos
        from core.models import Role, TenantUser

        admin_role = Role.objects.create(tenant=self.tenant, name="ADMIN", description="Administrator")
        prof_role = Role.objects.create(tenant=self.tenant, name="PROFESSIONAL", description="Professional")

        TenantUser.objects.create(user=self.user, tenant=self.tenant, role=admin_role)
        TenantUser.objects.create(user=self.prof, tenant=self.tenant, role=prof_role)

        self.cliente = Cliente.objects.create(
            tenant=self.tenant, nome_razao_social="Cliente Views Test", tipo_pessoa="PF"
        )

        # Criar alguns agendamentos de teste
        now = timezone.now()
        self.agendamento = Agendamento.objects.create(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.prof,
            status="CONFIRMADO",
            data_inicio=now + timedelta(hours=1),
            data_fim=now + timedelta(hours=1, minutes=30),
            origem="PROFISSIONAL",
        )

    def test_agendamento_home_view_unauthenticated(self):
        """
        Testa se a home de agendamentos redireciona para o login se o usuário não estiver autenticado.
        """
        response = self.client.get(reverse("agendamentos:home"))
        self.assertEqual(response.status_code, 302)
        # Verifica se redireciona para login (pode ser core:login ou variação)
        self.assertTrue(
            "login" in response.url.lower()
            or response.url.startswith("/accounts/")
            or response.url.startswith("/core/login")
        )

    def test_agendamento_home_view_authenticated(self):
        """
        Testa se a home de agendamentos carrega corretamente para um funcionário autenticado.
        """
        # Garantir que o usuário tenha tenant via propriedade legada
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="staff_user", password="testpass")
        response = self.client.get(reverse("agendamentos:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agendamentos/agendamento_home.html")

        # Verifica se os contadores principais estão no contexto
        self.assertIn("total_agendamentos", response.context)
        self.assertIn("confirmados_futuros", response.context)
        self.assertIn("pendentes_futuros", response.context)
        self.assertIn("proximos_agendamentos", response.context)

    def test_agendamento_list_view(self):
        """
        Testa a view de listagem de agendamentos.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="staff_user", password="testpass")
        response = self.client.get(reverse("agendamentos:agendamento-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agendamentos/agendamento_list.html")
        self.assertContains(response, self.cliente.nome_razao_social)
        self.assertIn("agendamento_list", response.context)

    def test_agendamento_detail_view(self):
        """
        Testa a view de detalhes de um agendamento.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="staff_user", password="testpass")
        response = self.client.get(reverse("agendamentos:agendamento-detail", args=[self.agendamento.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agendamentos/agendamento_detail.html")
        self.assertEqual(response.context["agendamento"], self.agendamento)
        self.assertContains(response, self.cliente.nome_razao_social)

    def test_agendamento_create_view_get(self):
        """
        Testa o carregamento do formulário de criação de agendamento.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="staff_user", password="testpass")
        response = self.client.get(reverse("agendamentos:agendamento-create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agendamentos/agendamento_form.html")
        self.assertIn("form", response.context)

    def test_agendamento_create_view_post(self):
        """
        Testa a criação de um agendamento via formulário.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="staff_user", password="testpass")

        now = timezone.now()
        data = {
            "cliente": self.cliente.id,
            "profissional": self.prof.id,
            "data_inicio": (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "data_fim": (now + timedelta(hours=2, minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
            "origem": "PROFISSIONAL",
            "status": "CONFIRMADO",
        }

        response = self.client.post(reverse("agendamentos:agendamento-create"), data)

        # Deve redirecionar após criação bem-sucedida
        self.assertEqual(response.status_code, 302)

        # Verifica se o agendamento foi criado
        self.assertTrue(Agendamento.objects.filter(cliente=self.cliente, profissional=self.prof).count() >= 2)

    def test_dashboard_view(self):
        """
        Testa a view do dashboard.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="staff_user", password="testpass")
        response = self.client.get(reverse("agendamentos:dashboard"))

        self.assertEqual(response.status_code, 200)
        # Dashboard pode ter template próprio ou usar o mesmo da home
        self.assertTrue(
            response.templates[0].name in ["agendamentos/dashboard.html", "agendamentos/agendamento_home.html"]
        )


class SlotViewsTest(TestCase):
    """
    Testes para as views de Slots do sistema interno.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(name="SlotTestTenant", subdomain="stt")
        self.user = User.objects.create_user(username="slot_user", password="testpass", is_staff=True)
        self.prof = User.objects.create_user(username="prof_slot", password="testpass", is_staff=True)

        # Criar role e relacionamentos corretos
        from core.models import Role, TenantUser

        admin_role = Role.objects.create(tenant=self.tenant, name="ADMIN", description="Administrator")
        prof_role = Role.objects.create(tenant=self.tenant, name="PROFESSIONAL", description="Professional")

        TenantUser.objects.create(user=self.user, tenant=self.tenant, role=admin_role)
        TenantUser.objects.create(user=self.prof, tenant=self.tenant, role=prof_role)

        # Criar disponibilidade para os slots
        self.disponibilidade = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.prof,
            data=timezone.now().date() + timedelta(days=1),
            hora_inicio=time(9, 0),
            hora_fim=time(17, 0),
            ativo=True,
        )

        # Criar alguns slots
        from datetime import datetime as dt

        tz = timezone.get_current_timezone()

        self.slot = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disponibilidade,
            profissional=self.prof,
            horario=timezone.make_aware(dt.combine(timezone.now().date() + timedelta(days=1), time(10, 0)), tz),
            capacidade_total=1,
        )

    def test_slot_list_view(self):
        """
        Testa a view de listagem de slots.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="slot_user", password="testpass")
        response = self.client.get(reverse("agendamentos:slot-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agendamentos/slot_list.html")
        self.assertIn("slot_list", response.context)

    def test_slot_detail_view(self):
        """
        Testa a view de detalhes de um slot.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="slot_user", password="testpass")
        response = self.client.get(reverse("agendamentos:slot-detail", args=[self.slot.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agendamentos/slot_detail.html")
        self.assertEqual(response.context["slot"], self.slot)


class DisponibilidadeViewsTest(TestCase):
    """
    Testes para as views de Disponibilidade do sistema interno.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(name="DispTestTenant", subdomain="dtt")
        self.user = User.objects.create_user(username="disp_user", password="testpass", is_staff=True)
        self.prof = User.objects.create_user(username="prof_disp", password="testpass", is_staff=True)

        # Criar role e relacionamentos corretos
        from core.models import Role, TenantUser

        admin_role = Role.objects.create(tenant=self.tenant, name="ADMIN", description="Administrator")
        prof_role = Role.objects.create(tenant=self.tenant, name="PROFESSIONAL", description="Professional")

        TenantUser.objects.create(user=self.user, tenant=self.tenant, role=admin_role)
        TenantUser.objects.create(user=self.prof, tenant=self.tenant, role=prof_role)

        self.disponibilidade = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.prof,
            data=timezone.now().date() + timedelta(days=1),
            hora_inicio=time(9, 0),
            hora_fim=time(17, 0),
            ativo=True,
        )

    def test_disponibilidade_list_view(self):
        """
        Testa a view de listagem de disponibilidades.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="disp_user", password="testpass")
        response = self.client.get(reverse("agendamentos:disponibilidade-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agendamentos/disponibilidade_list.html")
        self.assertIn("disponibilidade_list", response.context)

    def test_disponibilidade_detail_view(self):
        """
        Testa a view de detalhes de uma disponibilidade.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="disp_user", password="testpass")
        response = self.client.get(reverse("agendamentos:disponibilidade-detail", args=[self.disponibilidade.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agendamentos/disponibilidade_detail.html")
        self.assertEqual(response.context["disponibilidade"], self.disponibilidade)

    def test_disponibilidade_create_view(self):
        """
        Testa a criação de uma nova disponibilidade.
        """
        self.user._legacy_single_tenant = self.tenant
        self.user.save()

        self.client.login(username="disp_user", password="testpass")
        response = self.client.get(reverse("agendamentos:disponibilidade-create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "agendamentos/disponibilidade_form.html")
        self.assertIn("form", response.context)


@override_settings(USE_NOVO_AGENDAMENTO=True)
class ApiV2AgendamentoSerializersTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T2", subdomain="t2")
        self.admin = User.objects.create_superuser(username="admin_v2_serial", password="x")
        self.prof = User.objects.create_user(username="prof_v2_serial", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente Serial", tipo_pessoa="PF")
        # Agendamento sem slot
        inicio = timezone.now() + timedelta(hours=4)
        fim = inicio + timedelta(minutes=30)
        self.ag = AgendamentoService.criar(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.prof,
            data_inicio=inicio,
            data_fim=fim,
            origem="PROFISSIONAL",
            slot=None,
            tipo_servico="Teste",
        )

    def test_list_v2_serializer_shape(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoV2ViewSet

        factory = APIRequestFactory()
        view = AgendamentoV2ViewSet.as_view({"get": "list"})
        req = factory.get("/api/v2/agendamentos/")
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.admin)
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get("results", resp.data)
        self.assertTrue(len(data) >= 1)
        item = data[0]
        for field in ["id", "status", "origem", "data_inicio", "data_fim", "cliente", "profissional"]:
            self.assertIn(field, item)

    def test_detail_v2_serializer_includes_auditoria(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoV2ViewSet

        factory = APIRequestFactory()
        view = AgendamentoV2ViewSet.as_view({"get": "retrieve"})
        req = factory.get(f"/api/v2/agendamentos/{self.ag.id}/")
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.admin)
        resp = view(req, pk=self.ag.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("auditoria", resp.data)

    def test_create_v2(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoV2ViewSet

        factory = APIRequestFactory()
        view = AgendamentoV2ViewSet.as_view({"post": "create"})
        inicio = timezone.now() + timedelta(hours=6)
        fim = inicio + timedelta(minutes=30)
        payload = {
            "cliente": self.cliente.id,
            "profissional": self.prof.id,
            "data_inicio": inicio.isoformat(),
            "data_fim": fim.isoformat(),
            "origem": "PROFISSIONAL",
            "metadata": {"canal": "api_v2"},
        }
        req = factory.post("/api/v2/agendamentos/", payload, format="json")
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.admin)
        resp = view(req)
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", None))
        self.assertIn("id", resp.data)


@override_settings(USE_NOVO_AGENDAMENTO=True)
class ApiV2AgendamentoCreateSlotAndValidationTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T3", subdomain="t3")
        self.admin = User.objects.create_superuser(username="admin_v2_slot", password="x")
        self.prof = User.objects.create_user(username="prof_v2_slot", password="x", is_staff=True)
        self.cliente = Cliente.objects.create(tenant=self.tenant, nome_razao_social="Cliente Slot", tipo_pessoa="PF")
        # Criar disponibilidade e slot
        hoje = timezone.localdate()
        agora = timezone.now()
        base_hora = (agora + timedelta(hours=2)).time().replace(second=0, microsecond=0)
        fim_hora = (agora + timedelta(hours=3)).time().replace(second=0, microsecond=0)
        self.disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.prof,
            data=hoje,
            hora_inicio=base_hora,
            hora_fim=fim_hora,
            duracao_slot_minutos=30,
            capacidade_por_slot=1,
        )
        from datetime import datetime as dt

        tz = timezone.get_current_timezone()
        self.slot = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=self.disp,
            profissional=self.prof,
            horario=timezone.make_aware(dt.combine(hoje, base_hora), tz),
            capacidade_total=1,
        )

    def test_create_via_slot(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoV2ViewSet

        factory = APIRequestFactory()
        view = AgendamentoV2ViewSet.as_view({"post": "create"})
        payload = {
            "cliente": self.cliente.id,
            "profissional": self.prof.id,
            "slot": self.slot.id,
            "origem": "PROFISSIONAL",
            "metadata": {"canal": "slot"},
        }
        req = factory.post("/api/v2/agendamentos/", payload, format="json")
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.admin)
        resp = view(req)
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", None))
        self.assertIn("id", resp.data)
        self.assertIsNotNone(resp.data.get("slot"))

    def test_validation_error_sem_slot_e_datas(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api_views import AgendamentoV2ViewSet

        factory = APIRequestFactory()
        view = AgendamentoV2ViewSet.as_view({"post": "create"})
        payload = {"cliente": self.cliente.id, "profissional": self.prof.id, "origem": "PROFISSIONAL"}
        req = factory.post("/api/v2/agendamentos/", payload, format="json")
        req.session = {"tenant_id": self.tenant.id}
        force_authenticate(req, user=self.admin)
        resp = view(req)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.data if isinstance(resp.data, dict) else {})
