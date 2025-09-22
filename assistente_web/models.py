from django.conf import settings
from django.db import models
from django.utils import timezone


class ConversaAssistente(models.Model):
    """Modelo para armazenar conversas com o assistente de IA"""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversas_assistente")
    titulo = models.CharField(max_length=200, blank=True)
    data_inicio = models.DateTimeField(default=timezone.now)
    data_fim = models.DateTimeField(null=True, blank=True)
    ativa = models.BooleanField(default=True)
    modo_entrada = models.CharField(max_length=10, choices=[("voice", "Voz"), ("text", "Texto")], default="text")

    class Meta:
        verbose_name = "Conversa com Assistente"
        verbose_name_plural = "Conversas com Assistente"
        ordering = ["-data_inicio"]

    def __str__(self):
        return f"Conversa {self.id} - {self.usuario.username} - {self.data_inicio.strftime('%d/%m/%Y %H:%M')}"


class MensagemAssistente(models.Model):
    """Modelo para armazenar mensagens individuais da conversa"""

    conversa = models.ForeignKey(ConversaAssistente, on_delete=models.CASCADE, related_name="mensagens")
    tipo = models.CharField(
        max_length=10, choices=[("user", "Usuário"), ("assistant", "Assistente"), ("system", "Sistema")]
    )
    conteudo = models.TextField()
    intencao = models.CharField(max_length=100, blank=True, null=True)
    entidades = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    processado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Mensagem do Assistente"
        verbose_name_plural = "Mensagens do Assistente"
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.tipo}: {self.conteudo[:50]}..."


class MemoriaAssistente(models.Model):
    """Modelo para armazenar informações memorizadas pelo assistente"""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memorias_assistente")
    chave = models.CharField(max_length=200)
    valor = models.TextField()
    fonte = models.CharField(max_length=50, default="user")
    data_criacao = models.DateTimeField(default=timezone.now)
    data_atualizacao = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Memória do Assistente"
        verbose_name_plural = "Memórias do Assistente"
        unique_together = ["usuario", "chave"]
        ordering = ["-data_atualizacao"]

    def __str__(self):
        return f"{self.usuario.username}: {self.chave} = {self.valor[:30]}..."


class SkillExecution(models.Model):
    """Modelo para rastrear execuções de skills"""

    conversa = models.ForeignKey(ConversaAssistente, on_delete=models.CASCADE, related_name="execucoes_skills")
    skill_name = models.CharField(max_length=100)
    parametros = models.JSONField(default=dict)
    resultado = models.TextField(blank=True, null=True)
    sucesso = models.BooleanField(default=False)
    erro = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    tempo_execucao = models.FloatField(null=True, blank=True)  # em segundos

    class Meta:
        verbose_name = "Execução de Skill"
        verbose_name_plural = "Execuções de Skills"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.skill_name} - {self.timestamp.strftime('%d/%m/%Y %H:%M')} - {'✓' if self.sucesso else '✗'}"


class ConfiguracaoAssistente(models.Model):
    """Modelo para configurações personalizadas do assistente por usuário"""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="config_assistente")
    modo_preferido = models.CharField(max_length=10, choices=[("voice", "Voz"), ("text", "Texto")], default="text")
    auto_speak = models.BooleanField(default=True, help_text="Reproduzir respostas em voz automaticamente")
    skills_habilitadas = models.JSONField(default=list, help_text="Lista de skills habilitadas para este usuário")
    configuracoes_avancadas = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Configuração do Assistente"
        verbose_name_plural = "Configurações do Assistente"

    def __str__(self):
        return f"Config: {self.usuario.username}"
