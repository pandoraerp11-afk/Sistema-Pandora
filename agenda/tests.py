from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from agenda.models import Evento, LogEvento
from core.models import Tenant

User = get_user_model()


class EventoModelTest(TestCase):
    """Testes para o modelo Evento"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

        # Associar usuário ao tenant
        self.user.tenant = self.tenant
        self.user.save()

    def test_criar_evento(self):
        """Testa a criação de um evento"""
        evento = Evento.objects.create(
            tenant=self.tenant,
            titulo="Reunião de Teste",
            descricao="Descrição da reunião de teste",
            data_inicio=timezone.now(),
            data_fim=timezone.now() + timedelta(hours=1),
            responsavel=self.user,
        )

        self.assertEqual(evento.titulo, "Reunião de Teste")
        self.assertEqual(evento.tenant, self.tenant)
        self.assertEqual(evento.responsavel, self.user)
        self.assertEqual(evento.status, "agendado")
        self.assertIsNotNone(evento.uuid)

    def test_str_evento(self):
        """Testa a representação string do evento"""
        evento = Evento.objects.create(
            tenant=self.tenant,
            titulo="Evento Teste",
            data_inicio=timezone.now(),
            data_fim=timezone.now() + timedelta(hours=1),
            responsavel=self.user,
        )

        self.assertEqual(str(evento), "Evento Teste")

    def test_evento_em_andamento(self):
        """Testa se o evento está em andamento"""
        agora = timezone.now()
        evento = Evento.objects.create(
            tenant=self.tenant,
            titulo="Evento em Andamento",
            data_inicio=agora - timedelta(minutes=30),
            data_fim=agora + timedelta(minutes=30),
            responsavel=self.user,
        )

        self.assertTrue(evento.esta_em_andamento())

    def test_evento_nao_em_andamento(self):
        """Testa se o evento não está em andamento"""
        agora = timezone.now()
        evento = Evento.objects.create(
            tenant=self.tenant,
            titulo="Evento Futuro",
            data_inicio=agora + timedelta(hours=1),
            data_fim=agora + timedelta(hours=2),
            responsavel=self.user,
        )

        self.assertFalse(evento.esta_em_andamento())

    def test_duracao_evento(self):
        """Testa o cálculo da duração do evento"""
        agora = timezone.now()
        evento = Evento.objects.create(
            tenant=self.tenant,
            titulo="Evento com Duração",
            data_inicio=agora,
            data_fim=agora + timedelta(hours=2),
            responsavel=self.user,
        )

        duracao = evento.get_duracao()
        self.assertEqual(duracao.total_seconds(), 7200)  # 2 horas = 7200 segundos


class EventoViewTest(TestCase):
    """Testes para as views do módulo Agenda"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.client = Client()

        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

        # Associar usuário ao tenant
        self.user.tenant = self.tenant
        self.user.save()

        # Login do usuário
        self.client.login(username="testuser", password="testpass123")

    def test_evento_list_view(self):
        """Testa a view de listagem de eventos"""
        # Criar alguns eventos
        for i in range(3):
            Evento.objects.create(
                tenant=self.tenant,
                titulo=f"Evento {i + 1}",
                data_inicio=timezone.now() + timedelta(days=i),
                data_fim=timezone.now() + timedelta(days=i, hours=1),
                responsavel=self.user,
            )

        response = self.client.get(reverse("agenda:evento_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evento 1")
        self.assertContains(response, "Evento 2")
        self.assertContains(response, "Evento 3")

    def test_evento_create_view(self):
        """Testa a view de criação de evento"""
        response = self.client.get(reverse("agenda:evento_create"))
        self.assertEqual(response.status_code, 200)

        # Testar criação via POST
        data = {
            "titulo": "Novo Evento",
            "descricao": "Descrição do novo evento",
            "data_inicio": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "data_fim": (timezone.now() + timedelta(days=1, hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": "reuniao",
            "prioridade": "media",
        }

        response = self.client.post(reverse("agenda:evento_create"), data)
        self.assertEqual(response.status_code, 302)  # Redirect após criação

        # Verificar se o evento foi criado
        evento = Evento.objects.get(titulo="Novo Evento")
        self.assertEqual(evento.responsavel, self.user)
        self.assertEqual(evento.tenant, self.tenant)

    def test_evento_detail_view(self):
        """Testa a view de detalhes do evento"""
        evento = Evento.objects.create(
            tenant=self.tenant,
            titulo="Evento Detalhado",
            data_inicio=timezone.now(),
            data_fim=timezone.now() + timedelta(hours=1),
            responsavel=self.user,
        )

        response = self.client.get(reverse("agenda:evento_detail", kwargs={"pk": evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evento Detalhado")

    def test_evento_update_view(self):
        """Testa a view de atualização do evento"""
        evento = Evento.objects.create(
            tenant=self.tenant,
            titulo="Evento Original",
            data_inicio=timezone.now(),
            data_fim=timezone.now() + timedelta(hours=1),
            responsavel=self.user,
        )

        response = self.client.get(reverse("agenda:evento_update", kwargs={"pk": evento.pk}))
        self.assertEqual(response.status_code, 200)

        # Testar atualização via POST
        data = {
            "titulo": "Evento Atualizado",
            "descricao": "Descrição atualizada",
            "data_inicio": evento.data_inicio.strftime("%Y-%m-%d %H:%M:%S"),
            "data_fim": evento.data_fim.strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": "reuniao",
            "prioridade": "alta",
        }

        response = self.client.post(reverse("agenda:evento_update", kwargs={"pk": evento.pk}), data)
        self.assertEqual(response.status_code, 302)

        # Verificar se o evento foi atualizado
        evento.refresh_from_db()
        self.assertEqual(evento.titulo, "Evento Atualizado")
        self.assertEqual(evento.prioridade, "alta")

    def test_evento_delete_view(self):
        """Testa a view de exclusão do evento"""
        evento = Evento.objects.create(
            tenant=self.tenant,
            titulo="Evento para Excluir",
            data_inicio=timezone.now(),
            data_fim=timezone.now() + timedelta(hours=1),
            responsavel=self.user,
        )

        response = self.client.get(reverse("agenda:evento_delete", kwargs={"pk": evento.pk}))
        self.assertEqual(response.status_code, 200)

        # Testar exclusão via POST
        response = self.client.post(reverse("agenda:evento_delete", kwargs={"pk": evento.pk}))
        self.assertEqual(response.status_code, 302)

        # Verificar se o evento foi excluído
        with self.assertRaises(Evento.DoesNotExist):
            Evento.objects.get(pk=evento.pk)


class LogEventoTest(TestCase):
    """Testes para o modelo LogEvento"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

        self.evento = Evento.objects.create(
            tenant=self.tenant,
            titulo="Evento para Log",
            data_inicio=timezone.now(),
            data_fim=timezone.now() + timedelta(hours=1),
            responsavel=self.user,
        )

    def test_criar_log_evento(self):
        """Testa a criação de um log de evento"""
        log = LogEvento.objects.create(evento=self.evento, usuario=self.user, acao="Evento criado")

        self.assertEqual(log.evento, self.evento)
        self.assertEqual(log.usuario, self.user)
        self.assertEqual(log.acao, "Evento criado")
        self.assertIsNotNone(log.data_hora)

    def test_str_log_evento(self):
        """Testa a representação string do log de evento"""
        log = LogEvento.objects.create(evento=self.evento, usuario=self.user, acao="Teste de log")

        expected_str = f"Log de {self.evento.uuid} por {self.user.username}: Teste de log"
        self.assertEqual(str(log), expected_str)


class AgendaIntegrationTest(TestCase):
    """Testes de integração para o módulo Agenda"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.client = Client()

        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

        # Associar usuário ao tenant
        self.user.tenant = self.tenant
        self.user.save()

        # Login do usuário
        self.client.login(username="testuser", password="testpass123")

    def test_fluxo_completo_evento(self):
        """Testa o fluxo completo de criação, visualização, edição e exclusão de evento"""
        # 1. Criar evento
        data_criacao = {
            "titulo": "Evento Completo",
            "descricao": "Teste de fluxo completo",
            "data_inicio": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "data_fim": (timezone.now() + timedelta(days=1, hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": "reuniao",
            "prioridade": "alta",
        }

        response = self.client.post(reverse("agenda:evento_create"), data_criacao)
        self.assertEqual(response.status_code, 302)

        evento = Evento.objects.get(titulo="Evento Completo")

        # 2. Visualizar evento
        response = self.client.get(reverse("agenda:evento_detail", kwargs={"pk": evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evento Completo")

        # 3. Editar evento
        data_edicao = {
            "titulo": "Evento Editado",
            "descricao": "Descrição editada",
            "data_inicio": evento.data_inicio.strftime("%Y-%m-%d %H:%M:%S"),
            "data_fim": evento.data_fim.strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": "reuniao",
            "prioridade": "critica",
        }

        response = self.client.post(reverse("agenda:evento_update", kwargs={"pk": evento.pk}), data_edicao)
        self.assertEqual(response.status_code, 302)

        evento.refresh_from_db()
        self.assertEqual(evento.titulo, "Evento Editado")
        self.assertEqual(evento.prioridade, "critica")

        # 4. Excluir evento
        response = self.client.post(reverse("agenda:evento_delete", kwargs={"pk": evento.pk}))
        self.assertEqual(response.status_code, 302)

        with self.assertRaises(Evento.DoesNotExist):
            Evento.objects.get(pk=evento.pk)
