from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from chat.models import ConfiguracaoChat, Conversa, LogMensagem, Mensagem, ParticipanteConversa, PreferenciaUsuarioChat
from core.models import Tenant

User = get_user_model()


class ConversaModelTest(TestCase):
    """Testes para o modelo Conversa"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user1 = User.objects.create_user(username="user1", email="user1@example.com", password="testpass123")

        self.user2 = User.objects.create_user(username="user2", email="user2@example.com", password="testpass123")

        # Associar usuários ao tenant
        self.user1.tenant = self.tenant
        self.user2.tenant = self.tenant
        self.user1.save()
        self.user2.save()

    def test_criar_conversa_individual(self):
        """Testa a criação de uma conversa individual"""
        conversa = Conversa.objects.create(tenant=self.tenant, tipo="individual", criador=self.user1)

        self.assertEqual(conversa.tenant, self.tenant)
        self.assertEqual(conversa.tipo, "individual")
        self.assertEqual(conversa.criador, self.user1)
        self.assertEqual(conversa.status, "ativa")
        self.assertIsNotNone(conversa.uuid)

    def test_criar_conversa_grupo(self):
        """Testa a criação de uma conversa em grupo"""
        conversa = Conversa.objects.create(
            tenant=self.tenant, titulo="Grupo de Teste", tipo="grupo", criador=self.user1
        )

        self.assertEqual(conversa.titulo, "Grupo de Teste")
        self.assertEqual(conversa.tipo, "grupo")

    def test_adicionar_participante(self):
        """Testa adicionar participante à conversa"""
        conversa = Conversa.objects.create(tenant=self.tenant, tipo="individual", criador=self.user1)

        participante, created = conversa.adicionar_participante(self.user2, self.user1)

        self.assertTrue(created)
        self.assertEqual(participante.usuario, self.user2)
        self.assertEqual(participante.adicionado_por, self.user1)
        self.assertTrue(participante.ativo)

    def test_remover_participante(self):
        """Testa remover participante da conversa"""
        conversa = Conversa.objects.create(tenant=self.tenant, tipo="grupo", criador=self.user1)

        # Adicionar participante
        conversa.adicionar_participante(self.user2, self.user1)

        # Remover participante
        resultado = conversa.remover_participante(self.user2)

        self.assertTrue(resultado)

        # Verificar se foi marcado como inativo
        participante = ParticipanteConversa.objects.get(conversa=conversa, usuario=self.user2)
        self.assertFalse(participante.ativo)
        self.assertIsNotNone(participante.data_saida)

    def test_get_titulo_display(self):
        """Testa o método get_titulo_display"""
        # Conversa com título definido
        conversa_com_titulo = Conversa.objects.create(
            tenant=self.tenant, titulo="Conversa Teste", tipo="grupo", criador=self.user1
        )

        self.assertEqual(conversa_com_titulo.get_titulo_display(), "Conversa Teste")

        # Conversa individual sem título
        conversa_individual = Conversa.objects.create(tenant=self.tenant, tipo="individual", criador=self.user1)

        # Adicionar participantes
        conversa_individual.adicionar_participante(self.user1)
        conversa_individual.adicionar_participante(self.user2)

        titulo_esperado = f"{self.user1.username} & {self.user2.username}"
        self.assertEqual(conversa_individual.get_titulo_display(), titulo_esperado)


class MensagemModelTest(TestCase):
    """Testes para o modelo Mensagem"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user1 = User.objects.create_user(username="user1", email="user1@example.com", password="testpass123")

        self.user2 = User.objects.create_user(username="user2", email="user2@example.com", password="testpass123")

        self.conversa = Conversa.objects.create(tenant=self.tenant, tipo="individual", criador=self.user1)

    def test_criar_mensagem_texto(self):
        """Testa a criação de uma mensagem de texto"""
        mensagem = Mensagem.objects.create(
            tenant=self.tenant,
            conversa=self.conversa,
            remetente=self.user1,
            conteudo="Olá, como você está?",
            tipo="texto",
        )

        self.assertEqual(mensagem.tenant, self.tenant)
        self.assertEqual(mensagem.conversa, self.conversa)
        self.assertEqual(mensagem.remetente, self.user1)
        self.assertEqual(mensagem.conteudo, "Olá, como você está?")
        self.assertEqual(mensagem.tipo, "texto")
        self.assertEqual(mensagem.status, "enviada")
        self.assertFalse(mensagem.lida)
        self.assertIsNotNone(mensagem.uuid)

    def test_marcar_como_lida(self):
        """Testa marcar mensagem como lida"""
        mensagem = Mensagem.objects.create(
            tenant=self.tenant, conversa=self.conversa, remetente=self.user1, conteudo="Mensagem para marcar como lida"
        )

        self.assertFalse(mensagem.lida)
        self.assertIsNone(mensagem.data_leitura)

        mensagem.marcar_como_lida(self.user2)

        self.assertTrue(mensagem.lida)
        self.assertIsNotNone(mensagem.data_leitura)

    def test_editar_conteudo(self):
        """Testa editar conteúdo da mensagem"""
        mensagem = Mensagem.objects.create(
            tenant=self.tenant, conversa=self.conversa, remetente=self.user1, conteudo="Conteúdo original"
        )

        resultado = mensagem.editar_conteudo("Conteúdo editado", self.user1)

        self.assertTrue(resultado)
        self.assertEqual(mensagem.conteudo, "Conteúdo editado")
        self.assertEqual(mensagem.status, "editada")
        self.assertIsNotNone(mensagem.data_edicao)

    def test_editar_conteudo_usuario_diferente(self):
        """Testa que apenas o remetente pode editar a mensagem"""
        mensagem = Mensagem.objects.create(
            tenant=self.tenant, conversa=self.conversa, remetente=self.user1, conteudo="Conteúdo original"
        )

        resultado = mensagem.editar_conteudo("Tentativa de edição", self.user2)

        self.assertFalse(resultado)
        self.assertEqual(mensagem.conteudo, "Conteúdo original")
        self.assertEqual(mensagem.status, "enviada")

    def test_excluir_mensagem(self):
        """Testa excluir mensagem (soft delete)"""
        mensagem = Mensagem.objects.create(
            tenant=self.tenant, conversa=self.conversa, remetente=self.user1, conteudo="Mensagem para excluir"
        )

        resultado = mensagem.excluir_mensagem(self.user1)

        self.assertTrue(resultado)
        self.assertEqual(mensagem.status, "excluida")
        self.assertEqual(mensagem.conteudo, "[Mensagem excluída]")

    def test_is_arquivo_imagem(self):
        """Testa verificação se arquivo é imagem"""
        # Criar arquivo de teste
        arquivo_imagem = SimpleUploadedFile("test_image.jpg", b"fake image content", content_type="image/jpeg")

        mensagem = Mensagem.objects.create(
            tenant=self.tenant,
            conversa=self.conversa,
            remetente=self.user1,
            conteudo="Mensagem com imagem",
            tipo="arquivo",
            arquivo=arquivo_imagem,
        )

        self.assertTrue(mensagem.is_arquivo_imagem())


class ParticipanteConversaTest(TestCase):
    """Testes para o modelo ParticipanteConversa"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user1 = User.objects.create_user(username="user1", email="user1@example.com", password="testpass123")

        self.user2 = User.objects.create_user(username="user2", email="user2@example.com", password="testpass123")

        self.conversa = Conversa.objects.create(tenant=self.tenant, tipo="grupo", criador=self.user1)

    def test_criar_participante(self):
        """Testa a criação de um participante"""
        participante = ParticipanteConversa.objects.create(
            conversa=self.conversa, usuario=self.user2, adicionado_por=self.user1
        )

        self.assertEqual(participante.conversa, self.conversa)
        self.assertEqual(participante.usuario, self.user2)
        self.assertEqual(participante.adicionado_por, self.user1)
        self.assertTrue(participante.ativo)
        self.assertTrue(participante.notificacoes_habilitadas)

    def test_str_participante(self):
        """Testa a representação string do participante"""
        participante = ParticipanteConversa.objects.create(conversa=self.conversa, usuario=self.user2)

        expected_str = f"{self.user2.username} em {self.conversa.get_titulo_display()}"
        self.assertEqual(str(participante), expected_str)


class ChatViewTest(TestCase):
    """Testes para as views do módulo Chat"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.client = Client()

        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user1 = User.objects.create_user(username="user1", email="user1@example.com", password="testpass123")

        self.user2 = User.objects.create_user(username="user2", email="user2@example.com", password="testpass123")

        # Associar usuários ao tenant
        self.user1.tenant = self.tenant
        self.user2.tenant = self.tenant
        self.user1.save()
        self.user2.save()

        # Login do usuário
        self.client.login(username="user1", password="testpass123")

    def test_conversa_list_view(self):
        """Testa a view de listagem de conversas"""
        # Criar algumas conversas
        for i in range(3):
            conversa = Conversa.objects.create(
                tenant=self.tenant, titulo=f"Conversa {i + 1}", tipo="grupo", criador=self.user1
            )
            conversa.adicionar_participante(self.user1)

        response = self.client.get(reverse("chat:conversa_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Conversa 1")
        self.assertContains(response, "Conversa 2")
        self.assertContains(response, "Conversa 3")

    def test_conversa_create_view(self):
        """Testa a view de criação de conversa"""
        response = self.client.get(reverse("chat:conversa_create"))
        self.assertEqual(response.status_code, 200)

    def test_conversa_detail_view(self):
        """Testa a view de detalhes da conversa"""
        conversa = Conversa.objects.create(
            tenant=self.tenant, titulo="Conversa Detalhada", tipo="individual", criador=self.user1
        )

        # Adicionar usuário como participante
        conversa.adicionar_participante(self.user1)

        response = self.client.get(reverse("chat:conversa_detail", kwargs={"pk": conversa.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Conversa Detalhada")


class ConfiguracaoChatTest(TestCase):
    """Testes para o modelo ConfiguracaoChat"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

    def test_criar_configuracao(self):
        """Testa a criação de configuração do chat"""
        config = ConfiguracaoChat.objects.create(
            tenant=self.tenant,
            tamanho_maximo_arquivo_mb=20,
            moderacao_habilitada=True,
            notificacoes_push_habilitadas=False,
        )

        self.assertEqual(config.tenant, self.tenant)
        self.assertEqual(config.tamanho_maximo_arquivo_mb, 20)
        self.assertTrue(config.moderacao_habilitada)
        self.assertFalse(config.notificacoes_push_habilitadas)

    def test_str_configuracao(self):
        """Testa a representação string da configuração"""
        config = ConfiguracaoChat.objects.create(tenant=self.tenant)

        expected_str = f"Configurações do Chat - {self.tenant.name}"
        self.assertEqual(str(config), expected_str)


class PreferenciaUsuarioChatTest(TestCase):
    """Testes para o modelo PreferenciaUsuarioChat"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

    def test_criar_preferencia(self):
        """Testa a criação de preferência de usuário"""
        preferencia = PreferenciaUsuarioChat.objects.create(
            usuario=self.user, notificacoes_habilitadas=False, tema_escuro=True, tamanho_fonte="grande"
        )

        self.assertEqual(preferencia.usuario, self.user)
        self.assertFalse(preferencia.notificacoes_habilitadas)
        self.assertTrue(preferencia.tema_escuro)
        self.assertEqual(preferencia.tamanho_fonte, "grande")

    def test_str_preferencia(self):
        """Testa a representação string da preferência"""
        preferencia = PreferenciaUsuarioChat.objects.create(usuario=self.user)

        expected_str = f"Preferências de Chat - {self.user.username}"
        self.assertEqual(str(preferencia), expected_str)


class LogMensagemTest(TestCase):
    """Testes para o modelo LogMensagem"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

        self.conversa = Conversa.objects.create(tenant=self.tenant, tipo="individual", criador=self.user)

        self.mensagem = Mensagem.objects.create(
            tenant=self.tenant, conversa=self.conversa, remetente=self.user, conteudo="Mensagem para log"
        )

    def test_criar_log_mensagem(self):
        """Testa a criação de um log de mensagem"""
        log = LogMensagem.objects.create(mensagem=self.mensagem, usuario=self.user, acao="Mensagem enviada")

        self.assertEqual(log.mensagem, self.mensagem)
        self.assertEqual(log.usuario, self.user)
        self.assertEqual(log.acao, "Mensagem enviada")
        self.assertIsNotNone(log.data_hora)

    def test_str_log_mensagem(self):
        """Testa a representação string do log de mensagem"""
        log = LogMensagem.objects.create(mensagem=self.mensagem, usuario=self.user, acao="Teste de log")

        expected_str = f"Log de {self.mensagem.uuid} por {self.user.username}: Teste de log"
        self.assertEqual(str(log), expected_str)


class ChatIntegrationTest(TestCase):
    """Testes de integração para o módulo Chat"""

    def setUp(self):
        """Configuração inicial para os testes"""
        self.client = Client()

        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="empresa-teste")

        self.user1 = User.objects.create_user(username="user1", email="user1@example.com", password="testpass123")

        self.user2 = User.objects.create_user(username="user2", email="user2@example.com", password="testpass123")

        # Associar usuários ao tenant
        self.user1.tenant = self.tenant
        self.user2.tenant = self.tenant
        self.user1.save()
        self.user2.save()

        # Login do usuário
        self.client.login(username="user1", password="testpass123")

    def test_fluxo_completo_conversa(self):
        """Testa o fluxo completo de conversa e mensagens"""
        # 1. Criar conversa
        conversa = Conversa.objects.create(
            tenant=self.tenant, titulo="Conversa de Teste", tipo="individual", criador=self.user1
        )

        # 2. Adicionar participantes
        conversa.adicionar_participante(self.user1)
        conversa.adicionar_participante(self.user2, self.user1)

        # 3. Enviar mensagem
        mensagem = Mensagem.objects.create(
            tenant=self.tenant, conversa=conversa, remetente=self.user1, conteudo="Olá! Como você está?"
        )

        # 4. Verificar se a mensagem foi criada
        self.assertEqual(mensagem.conversa, conversa)
        self.assertEqual(mensagem.remetente, self.user1)
        self.assertFalse(mensagem.lida)

        # 5. Marcar mensagem como lida pelo destinatário
        mensagem.marcar_como_lida(self.user2)
        self.assertTrue(mensagem.lida)

        # 6. Responder à mensagem
        resposta = Mensagem.objects.create(
            tenant=self.tenant,
            conversa=conversa,
            remetente=self.user2,
            conteudo="Estou bem, obrigado!",
            resposta_para=mensagem,
        )

        self.assertEqual(resposta.resposta_para, mensagem)

        # 7. Verificar contagem de mensagens não lidas
        mensagens_nao_lidas = conversa.get_mensagens_nao_lidas_para_usuario(self.user1)
        self.assertEqual(mensagens_nao_lidas, 1)  # A resposta não foi lida pelo user1

    def test_configuracao_e_preferencias_chat(self):
        """Testa configurações e preferências do chat"""
        # Criar configuração do tenant
        config = ConfiguracaoChat.objects.create(
            tenant=self.tenant,
            tamanho_maximo_arquivo_mb=15,
            moderacao_habilitada=True,
            tipos_arquivo_permitidos=[".pdf", ".jpg", ".png"],
        )

        # Criar preferência do usuário
        preferencia = PreferenciaUsuarioChat.objects.create(
            usuario=self.user1, notificacoes_habilitadas=True, tema_escuro=False, tamanho_fonte="medio"
        )

        # Verificar se as configurações foram salvas corretamente
        self.assertEqual(config.tamanho_maximo_arquivo_mb, 15)
        self.assertTrue(config.moderacao_habilitada)
        self.assertEqual(config.tipos_arquivo_permitidos, [".pdf", ".jpg", ".png"])

        self.assertTrue(preferencia.notificacoes_habilitadas)
        self.assertFalse(preferencia.tema_escuro)
        self.assertEqual(preferencia.tamanho_fonte, "medio")
