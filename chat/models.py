import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from core.models import Tenant, TimestampedModel

User = get_user_model()


class Conversa(TimestampedModel):
    """
    Modelo para representar uma conversa entre usuários.
    Suporta conversas individuais e em grupo.
    """

    TIPO_CHOICES = [
        ("individual", "Individual"),
        ("grupo", "Grupo"),
    ]

    STATUS_CHOICES = [
        ("ativa", "Ativa"),
        ("arquivada", "Arquivada"),
        ("bloqueada", "Bloqueada"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="Empresa", related_name="conversas")

    titulo = models.CharField(max_length=200, verbose_name="Título", blank=True)
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default="individual", verbose_name="Tipo")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="ativa", verbose_name="Status")

    # Participantes da conversa
    participantes = models.ManyToManyField(
        User,
        through="ParticipanteConversa",
        through_fields=("conversa", "usuario"),
        related_name="conversas_participando",
        verbose_name="Participantes",
    )

    # Criador da conversa
    criador = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="conversas_criadas", verbose_name="Criador"
    )

    # Última atividade
    ultima_atividade = models.DateTimeField(auto_now=True, verbose_name="Última Atividade")

    # UUID para identificação única
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def get_titulo_display(self):
        """Retorna o título da conversa ou gera um baseado nos participantes."""
        if self.titulo:
            return self.titulo

        if self.tipo == "individual":
            participantes = list(self.participantes.all()[:2])
            if len(participantes) == 2:
                return f"{participantes[0].username} & {participantes[1].username}"
            elif len(participantes) == 1:
                return f"Conversa com {participantes[0].username}"

        return f"Conversa em Grupo ({self.participantes.count()} participantes)"

    def get_ultima_mensagem(self):
        """Retorna a última mensagem da conversa."""
        return self.mensagens.first()

    def get_mensagens_nao_lidas_para_usuario(self, usuario):
        """Retorna o número de mensagens não lidas para um usuário específico."""
        return self.mensagens.filter(lida=False).exclude(remetente=usuario).count()

    def marcar_mensagens_como_lidas(self, usuario):
        """Marca todas as mensagens da conversa como lidas para um usuário."""
        self.mensagens.filter(lida=False).exclude(remetente=usuario).update(lida=True, data_leitura=timezone.now())

    def adicionar_participante(self, usuario, adicionado_por=None):
        """Adiciona um participante à conversa."""
        participante, created = ParticipanteConversa.objects.get_or_create(
            conversa=self, usuario=usuario, defaults={"adicionado_por": adicionado_por, "data_entrada": timezone.now()}
        )
        return participante, created

    def remover_participante(self, usuario):
        """Remove um participante da conversa."""
        try:
            participante = ParticipanteConversa.objects.get(conversa=self, usuario=usuario)
            participante.data_saida = timezone.now()
            participante.ativo = False
            participante.save()
            return True
        except ParticipanteConversa.DoesNotExist:
            return False

    def __str__(self):
        return self.get_titulo_display()

    class Meta:
        verbose_name = "Conversa"
        verbose_name_plural = "Conversas"
        ordering = ["-ultima_atividade"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "tipo"]),
            models.Index(fields=["ultima_atividade"]),
        ]


class ParticipanteConversa(TimestampedModel):
    """
    Modelo intermediário para participantes de conversas.
    """

    conversa = models.ForeignKey(
        Conversa, on_delete=models.CASCADE, related_name="participantes_detalhes", verbose_name="Conversa"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="participacoes_conversa", verbose_name="Usuário"
    )

    # Metadados da participação
    data_entrada = models.DateTimeField(default=timezone.now, verbose_name="Data de Entrada")
    data_saida = models.DateTimeField(null=True, blank=True, verbose_name="Data de Saída")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    # Última visualização (para recibos de leitura por participante)
    ultima_visualizacao = models.DateTimeField(null=True, blank=True, verbose_name="Última Visualização")

    # Quem adicionou este participante
    adicionado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participantes_adicionados",
        verbose_name="Adicionado Por",
    )

    # Configurações de notificação
    notificacoes_habilitadas = models.BooleanField(default=True, verbose_name="Notificações Habilitadas")

    def __str__(self):
        return f"{self.usuario.username} em {self.conversa.get_titulo_display()}"

    class Meta:
        verbose_name = "Participante da Conversa"
        verbose_name_plural = "Participantes das Conversas"
        unique_together = ("conversa", "usuario")


class Mensagem(TimestampedModel):
    """
    Modelo para mensagens do chat.
    """

    TIPO_CHOICES = [
        ("texto", "Texto"),
        ("arquivo", "Arquivo"),
        ("imagem", "Imagem"),
        ("sistema", "Sistema"),
    ]

    STATUS_CHOICES = [
        ("enviada", "Enviada"),
        ("entregue", "Entregue"),
        ("lida", "Lida"),
        ("editada", "Editada"),
        ("excluida", "Excluída"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="Empresa", related_name="mensagens_chat")

    conversa = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name="mensagens", verbose_name="Conversa")

    remetente = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="mensagens_enviadas_chat", verbose_name="Remetente"
    )

    # Conteúdo da mensagem
    conteudo = models.TextField(verbose_name="Conteúdo")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="texto", verbose_name="Tipo")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="enviada", verbose_name="Status")

    # Arquivo anexo (opcional)
    arquivo = models.FileField(upload_to="chat/arquivos/%Y/%m/", null=True, blank=True, verbose_name="Arquivo")
    nome_arquivo_original = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Nome Original do Arquivo"
    )

    # Metadados
    lida = models.BooleanField(default=False, verbose_name="Lida")
    data_leitura = models.DateTimeField(null=True, blank=True, verbose_name="Data de Leitura")
    data_edicao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Edição")

    # Mensagem respondida (para threads)
    resposta_para = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="respostas", verbose_name="Resposta Para"
    )

    # UUID para identificação única
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def marcar_como_lida(self, usuario=None):
        """Marca a mensagem como lida."""
        if not self.lida and self.remetente != usuario:
            self.lida = True
            self.data_leitura = timezone.now()
            self.save(update_fields=["lida", "data_leitura"])

            # Log da ação
            LogMensagem.objects.create(mensagem=self, usuario=usuario, acao="Mensagem marcada como lida.")

    def editar_conteudo(self, novo_conteudo, usuario):
        """Edita o conteúdo da mensagem."""
        if self.remetente == usuario:
            conteudo_anterior = self.conteudo
            self.conteudo = novo_conteudo
            self.status = "editada"
            self.data_edicao = timezone.now()
            self.save(update_fields=["conteudo", "status", "data_edicao"])

            # Log da ação
            LogMensagem.objects.create(
                mensagem=self,
                usuario=usuario,
                acao=f"Mensagem editada. Conteúdo anterior: {conteudo_anterior[:100]}...",
            )
            return True
        return False

    def excluir_mensagem(self, usuario):
        """Exclui a mensagem (soft delete)."""
        if self.remetente == usuario:
            self.status = "excluida"
            self.conteudo = "[Mensagem excluída]"
            self.save(update_fields=["status", "conteudo"])

            # Log da ação
            LogMensagem.objects.create(mensagem=self, usuario=usuario, acao="Mensagem excluída pelo remetente.")
            return True
        return False

    def get_nome_arquivo(self):
        """Retorna o nome original do arquivo ou o nome do campo arquivo."""
        if self.nome_arquivo_original:
            return self.nome_arquivo_original
        elif self.arquivo:
            return self.arquivo.name.split("/")[-1]
        return None

    def is_arquivo_imagem(self):
        """Verifica se o arquivo anexo é uma imagem."""
        if self.arquivo:
            extensoes_imagem = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]
            nome_arquivo = self.arquivo.name.lower()
            return any(nome_arquivo.endswith(ext) for ext in extensoes_imagem)
        return False

    def __str__(self):
        return f"{self.remetente.username}: {self.conteudo[:50]}..."

    class Meta:
        verbose_name = "Mensagem"
        verbose_name_plural = "Mensagens"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conversa", "created_at"]),
            models.Index(fields=["remetente", "created_at"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["lida", "created_at"]),
        ]


class LogMensagem(models.Model):
    """
    Log de ações realizadas nas mensagens.
    """

    mensagem = models.ForeignKey(Mensagem, on_delete=models.CASCADE, related_name="logs", verbose_name="Mensagem")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuário")
    acao = models.CharField(max_length=255, verbose_name="Ação")
    data_hora = models.DateTimeField(auto_now_add=True, verbose_name="Data e Hora")

    def __str__(self):
        return f"Log de {self.mensagem.uuid} por {self.usuario.username if self.usuario else 'Sistema'}: {self.acao}"

    class Meta:
        verbose_name = "Log de Mensagem"
        verbose_name_plural = "Logs de Mensagens"
        ordering = ["-data_hora"]


class ConversaFavorita(models.Model):
    """Marca conversas favoritas por usuário."""

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="conversas_favoritas")
    conversa = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name="favoritos")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("usuario", "conversa")
        indexes = [models.Index(fields=["usuario", "conversa"])]

    def __str__(self):
        return f"Favorita {self.usuario_id}->{self.conversa_id}"


class MensagemReacao(models.Model):
    """Reações (emoji) em mensagens."""

    mensagem = models.ForeignKey(Mensagem, on_delete=models.CASCADE, related_name="reacoes")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reacoes_mensagem")
    emoji = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("mensagem", "usuario", "emoji")
        indexes = [models.Index(fields=["mensagem", "emoji"]), models.Index(fields=["usuario"])]

    def __str__(self):
        return f"Reacao {self.emoji} msg={self.mensagem_id} user={self.usuario_id}"


class MensagemFixada(models.Model):
    """Mensagens fixadas em uma conversa."""

    conversa = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name="mensagens_fixadas")
    mensagem = models.ForeignKey(Mensagem, on_delete=models.CASCADE, related_name="fixacoes")
    fixada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="mensagens_fixadas_acao")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("conversa", "mensagem")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["conversa", "created_at"])]

    def __str__(self):
        return f"Fixada {self.mensagem_id} em {self.conversa_id}"


class ConfiguracaoChat(TimestampedModel):
    """
    Configurações do chat por tenant.
    """

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="configuracao_chat", verbose_name="Empresa"
    )

    # Configurações de arquivo
    tamanho_maximo_arquivo_mb = models.PositiveIntegerField(default=10, verbose_name="Tamanho Máximo de Arquivo (MB)")
    tipos_arquivo_permitidos = models.JSONField(default=list, blank=True, verbose_name="Tipos de Arquivo Permitidos")

    # Configurações de retenção
    dias_retencao_mensagens = models.PositiveIntegerField(default=365, verbose_name="Dias de Retenção de Mensagens")

    # Configurações de moderação
    moderacao_habilitada = models.BooleanField(default=False, verbose_name="Moderação Habilitada")
    palavras_bloqueadas = models.JSONField(default=list, blank=True, verbose_name="Palavras Bloqueadas")

    # Configurações de notificação
    notificacoes_push_habilitadas = models.BooleanField(default=True, verbose_name="Push Notifications Habilitadas")
    notificacoes_email_habilitadas = models.BooleanField(
        default=False, verbose_name="Notificações por E-mail Habilitadas"
    )

    def __str__(self):
        return f"Configurações do Chat - {self.tenant.name}"

    class Meta:
        verbose_name = "Configuração do Chat"
        verbose_name_plural = "Configurações do Chat"


class PreferenciaUsuarioChat(TimestampedModel):
    """
    Preferências de chat por usuário.
    """

    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="preferencia_chat", verbose_name="Usuário"
    )

    # Configurações de notificação
    notificacoes_habilitadas = models.BooleanField(default=True, verbose_name="Notificações Habilitadas")
    som_notificacao_habilitado = models.BooleanField(default=True, verbose_name="Som de Notificação Habilitado")

    # Configurações de privacidade
    status_online_visivel = models.BooleanField(default=True, verbose_name="Status Online Visível")
    ultima_visualizacao_visivel = models.BooleanField(default=True, verbose_name="Última Visualização Visível")

    # Configurações de interface
    tema_escuro = models.BooleanField(default=False, verbose_name="Tema Escuro")
    tamanho_fonte = models.CharField(
        max_length=10,
        choices=[("pequeno", "Pequeno"), ("medio", "Médio"), ("grande", "Grande")],
        default="medio",
        verbose_name="Tamanho da Fonte",
    )

    def __str__(self):
        return f"Preferências de Chat - {self.usuario.username}"

    class Meta:
        verbose_name = "Preferência de Chat do Usuário"
        verbose_name_plural = "Preferências de Chat dos Usuários"
