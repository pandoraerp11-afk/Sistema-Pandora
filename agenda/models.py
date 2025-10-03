"""Models for the agenda app."""

from typing import Any, ClassVar
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Tenant  # Importar Tenant e CustomUser


class Evento(models.Model):
    """Representa um evento na agenda."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="Empresa")
    titulo = models.CharField(max_length=200, verbose_name="Título")
    descricao = models.TextField(blank=True, default="", verbose_name="Descrição")
    data_inicio = models.DateTimeField(verbose_name="Data e Hora de Início")
    data_fim = models.DateTimeField(blank=True, null=True, verbose_name="Data e Hora de Fim")
    dia_inteiro = models.BooleanField(default=False, verbose_name="Dia Inteiro")
    # UUID para rastreabilidade (alguns testes esperam evento.uuid)
    uuid = models.UUIDField(editable=False, unique=True, null=True, blank=True)

    STATUS_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("agendado", "Agendado"),  # novo status inicial esperado pelos testes
        ("pendente", "Pendente"),  # manter para compat (pode representar aguardando confirmação)
        ("confirmado", "Confirmado"),
        ("realizado", "Realizado"),  # compatibilidade
        ("concluido", "Concluído"),
        ("cancelado", "Cancelado"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="agendado", verbose_name="Status")

    PRIORIDADE_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("baixa", "Baixa"),
        ("media", "Média"),
        ("alta", "Alta"),
        ("critica", "Crítica"),  # compat legado (tests usam 'critica')
        ("urgente", "Urgente"),
    ]
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default="media", verbose_name="Prioridade")

    local = models.CharField(max_length=255, blank=True, default="", verbose_name="Local")

    TIPO_EVENTO_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("empresa", "Evento da Empresa"),
        ("cliente", "Evento de Cliente"),
        ("atendimento", "Agendamento de Atendimento"),
        ("servico", "Agendamento de Serviço"),  # novo padrão
        ("reuniao", "Reunião"),  # compat legado (tests enviam 'reuniao' via campo 'tipo')
        ("fornecedor", "Evento com Fornecedor"),
        ("funcionario", "Evento Interno (Funcionário)"),
        ("outro", "Outro"),
    ]
    tipo_evento = models.CharField(
        max_length=20,
        choices=TIPO_EVENTO_CHOICES,
        default="outro",
        verbose_name="Tipo de Evento",
    )

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agenda_eventos_responsavel",
        verbose_name="Responsável",
    )
    participantes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="agenda_eventos_participante",
        verbose_name="Participantes",
    )

    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    class Meta:
        """Meta options for the Evento model."""

        verbose_name = "Evento"
        verbose_name_plural = "Eventos"
        ordering: ClassVar[list[str]] = ["data_inicio"]

    def __str__(self) -> str:
        """Return a string representation of the event."""
        return self.titulo

    def save(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401  # ruff: noqa: ANN401
        """Save the event instance."""
        if not self.uuid:
            self.uuid = uuid4()
        # Se criado agora e status default 'pendente' mas lógica de negócio/teste quer 'agendado'
        if self._state.adding and self.status == "pendente" and "agendado" in [c[0] for c in self.STATUS_CHOICES]:
            # Promover instâncias antigas criadas sem novo default
            self.status = "agendado"
        super().save(*args, **kwargs)

    # Métodos utilitários esperados pelos testes
    def get_duracao(self) -> timezone.timedelta:
        """Calculate the duration of the event."""
        if self.data_inicio and self.data_fim:
            return self.data_fim - self.data_inicio
        return timezone.timedelta(0)

    def esta_em_andamento(self) -> bool:
        """Check if the event is currently in progress."""
        agora = timezone.now()
        if not self.data_inicio:
            return False
        fim = self.data_fim or self.data_inicio
        return self.data_inicio <= agora <= fim

    # -------------------------
    # Compatibilidade legada: campo 'tipo' era usado nos testes
    # -------------------------
    @property
    def tipo(self) -> str:
        """Return the event type."""
        return self.tipo_evento

    @tipo.setter
    def tipo(self, value: str) -> None:
        """Set the event type."""
        # Se valor não estiver em choices atuais, converte para 'outro'
        valid_values = {c[0] for c in self.TIPO_EVENTO_CHOICES}
        self.tipo_evento = value if value in valid_values else "outro"


class LogEvento(models.Model):
    """Registra o histórico de ações em um evento."""

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="logs", verbose_name="Evento")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Usuário",
        related_name="agenda_logevento_usuario",
    )
    acao = models.CharField(max_length=255, verbose_name="Ação")
    data_hora = models.DateTimeField(auto_now_add=True, verbose_name="Data e Hora")

    class Meta:
        """Meta options for the LogEvento model."""

        verbose_name = "Log de Evento"
        verbose_name_plural = "Logs de Eventos"
        ordering: ClassVar[list[str]] = ["-data_hora"]

    def __str__(self) -> str:
        """Return a string representation of the log entry."""
        ident = getattr(self.evento, "uuid", None) or self.evento.titulo
        return f"Log de {ident} por {self.usuario.username if self.usuario else 'N/A'}: {self.acao}"


class EventoLembrete(models.Model):
    """Configuração de lembretes por evento e usuário."""

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="lembretes")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_lembretes")
    minutos_antes = models.PositiveIntegerField(default=15, help_text="Minutos antes do início do evento")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for the EventoLembrete model."""

        verbose_name = "Lembrete de Evento"
        verbose_name_plural = "Lembretes de Eventos"
        unique_together = ("evento", "usuario", "minutos_antes")

    def __str__(self) -> str:
        """Return a string representation of the reminder."""
        return f"Lembrete {self.minutos_antes}min antes para {self.usuario} em '{self.evento}'"


class AgendaConfiguracao(models.Model):
    """Configurações da Agenda por tenant (padrões de lembretes e digest)."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="agenda_config")
    # Lista de minutos padrão para criar lembretes automaticamente (ex.: [1440, 120, 15])
    lembretes_padrao = models.JSONField(default=list, blank=True)
    # Digest diário por e-mail
    digest_email_habilitado = models.BooleanField(default=False)
    # Hora do dia (0-23) para disparo do digest (no fuso do servidor)
    digest_email_hora = models.PositiveSmallIntegerField(default=8)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for the AgendaConfiguracao model."""

        verbose_name = "Configuração da Agenda"
        verbose_name_plural = "Configurações da Agenda"

    def __str__(self) -> str:
        """Return a string representation of the agenda configuration."""
        return f"Configuração da Agenda - {self.tenant.name}"
