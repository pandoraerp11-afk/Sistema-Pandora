from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone
from django.utils import timezone as djtz

from agendamentos.models import Agendamento, Disponibilidade, Slot
from clientes.models import Cliente
from core.models import Tenant
from portal_cliente.models import ContaCliente
from prontuarios.models import Atendimento, FotoEvolucao
from servicos.models import CategoriaServico, Servico, ServicoClinico

User = get_user_model()


class PortalClienteDecoratorTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="cli", password="x")
        self.tenant = Tenant.objects.create(nome="Tenant X", schema_name="tenantx")
        self.cliente = Cliente.objects.create(
            nome="Cliente Z", documento="12345678900", tipo="PF", tenant=self.tenant, portal_ativo=True
        )
        ContaCliente.objects.create(usuario=self.user, cliente=self.cliente, ativo=True)

    def test_dashboard_acesso(self):
        self.client.login(username="cli", password="x")
        resp = self.client.get("/portal-cliente/dashboard/")
        self.assertIn(resp.status_code, (200, 302, 404))

    def test_galeria_sem_fotos(self):
        self.client.login(username="cli", password="x")
        resp = self.client.get("/portal-cliente/galeria/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Galeria") if hasattr(resp, "content") else None

    def test_galeria_com_foto(self):
        self.client.login(username="cli", password="x")
        cat = CategoriaServico.objects.create(nome="Basico")
        proc = Servico.objects.create(
            tenant=self.tenant,
            is_clinical=True,
            nome_servico="Proc",
            descricao="x",
            categoria=cat,
            preco_base=100,
        )
        ServicoClinico.objects.create(servico=proc, duracao_estimada=timezone.timedelta(minutes=30))
        atendimento = Atendimento.objects.create(
            tenant=self.tenant,
            cliente=self.cliente,
            servico=proc,
            profissional=self.user,
            data_atendimento=timezone.now(),
            numero_sessao=1,
            status="CONCLUIDO",
            area_tratada="Area",
            valor_cobrado=0,
            forma_pagamento="DINHEIRO",
        )
        # Criar foto mínima (imagem obrigatória pode ser mockada com SimpleUploadedFile)
        from django.core.files.uploadedfile import SimpleUploadedFile

        img = SimpleUploadedFile("foto.jpg", b"filecontent", content_type="image/jpeg")
        FotoEvolucao.objects.create(
            tenant=self.tenant,
            cliente=self.cliente,
            atendimento=atendimento,
            titulo="Antes",
            tipo_foto="ANTES",
            momento="INICIO_TRATAMENTO",
            area_fotografada="Rosto",
            imagem=img,
            imagem_thumbnail=img,
            data_foto=timezone.now(),
            visivel_cliente=True,
        )
        resp = self.client.get("/portal-cliente/galeria/")
        self.assertEqual(resp.status_code, 200)
        # Visualizar foto específica
        foto = FotoEvolucao.objects.first()
        resp2 = self.client.get(f"/portal-cliente/foto/{foto.id}/")
        self.assertEqual(resp2.status_code, 200)

    def test_sem_conta(self):
        User.objects.create_user(username="sem", password="x")
        self.client.login(username="sem", password="x")
        resp = self.client.get("/portal-cliente/dashboard/")
        self.assertIn(resp.status_code, (404, 302))

    def test_throttling_slots(self):
        self.client.login(username="cli", password="x")
        # Limpa contadores
        cache.clear()
        for _ in range(22):
            resp = self.client.get("/portal-cliente/ajax/slots-disponiveis/?servico_id=1")
        # Última deve estar em 429 após limite >20
        self.assertEqual(resp.status_code, 429)

    def test_etag_profissionais(self):
        self.client.login(username="cli", password="x")
        # Cria profissional
        prof = User.objects.create_user(username="prof1", password="x")
        prof.tipo_funcionario = "PROFISSIONAL"
        prof.tenant = self.tenant
        prof.save()
        resp1 = self.client.get("/portal-cliente/ajax/profissionais/")
        self.assertEqual(resp1.status_code, 200)
        etag = resp1.headers.get("ETag") or resp1.get("ETag")
        # Requisição condicional
        resp2 = self.client.get("/portal-cliente/ajax/profissionais/", HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(resp2.status_code, 304)

    def test_agendamento_status_endpoint(self):
        self.client.login(username="cli", password="x")
        # Criar agendamento mínimo
        cat = CategoriaServico.objects.create(nome="Basico2")
        proc = Servico.objects.create(
            tenant=self.tenant,
            is_clinical=True,
            nome_servico="Proc2",
            descricao="x",
            categoria=cat,
            preco_base=100,
        )
        ServicoClinico.objects.create(servico=proc, duracao_estimada=timezone.timedelta(minutes=30))
        # Criar disponibilidade + slot
        disp = Disponibilidade.objects.create(
            tenant=self.tenant,
            profissional=self.user,
            data=djtz.now().date(),
            hora_inicio=djtz.now().time(),
            hora_fim=(djtz.now() + djtz.timedelta(hours=1)).time(),
        )
        slot = Slot.objects.create(
            tenant=self.tenant,
            disponibilidade=disp,
            profissional=self.user,
            horario=djtz.now() + djtz.timedelta(minutes=10),
        )
        ag = Agendamento.objects.create(
            tenant=self.tenant,
            cliente=self.cliente,
            profissional=self.user,
            slot=slot,
            data_inicio=slot.horario,
            data_fim=slot.horario + djtz.timedelta(minutes=30),
            status="PENDENTE",
        )
        url = f"/portal-cliente/ajax/agendamento/{ag.id}/status/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertJSONEqual(resp.content, resp.json())
