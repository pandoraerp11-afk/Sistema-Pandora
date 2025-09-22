from django.db import models
from django.utils.translation import gettext_lazy as _

from clientes.models import Cliente
from core.models import CustomUser, Tenant, TimestampedModel
from servicos.models import Servico

STATUS_AGENDAMENTO = [
    ("PENDENTE", "Pendente"),
    ("CONFIRMADO", "Confirmado"),
    ("EM_ANDAMENTO", "Em Andamento"),
    ("CONCLUIDO", "Concluído"),
    ("CANCELADO", "Cancelado"),
    ("REAGENDADO", "Reagendado"),
    ("NO_SHOW", "Não Compareceu"),
]

ORIGEM_AGENDAMENTO = [
    ("CLIENTE", "Cliente"),
    ("PROFISSIONAL", "Profissional"),
    ("OPERADOR", "Operador"),
    ("SISTEMA", "Sistema"),
]


class Disponibilidade(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="disponibilidades")
    profissional = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="disponibilidades")
    data = models.DateField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    duracao_slot_minutos = models.PositiveIntegerField(default=30)
    capacidade_por_slot = models.PositiveIntegerField(default=1)
    recorrente = models.BooleanField(default=False)
    regra_recorrencia = models.CharField(max_length=50, blank=True, null=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Disponibilidade"
        verbose_name_plural = "Disponibilidades"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "profissional", "data", "hora_inicio", "hora_fim"], name="unique_disp_intervalo_prof"
            )
        ]


class Slot(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="slots")
    disponibilidade = models.ForeignKey(Disponibilidade, on_delete=models.CASCADE, related_name="slots")
    profissional = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="slots")
    horario = models.DateTimeField()
    capacidade_total = models.PositiveIntegerField(default=1)
    capacidade_utilizada = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Slot"
        verbose_name_plural = "Slots"
        constraints = [models.UniqueConstraint(fields=["profissional", "horario"], name="unique_slot_prof_horario")]
        ordering = ["horario"]

    @property
    def disponivel(self):
        from django.conf import settings

        limite = self.capacidade_total
        if getattr(settings, "ENABLE_CONTROLLED_OVERBOOK", False):
            limite += getattr(settings, "AGENDAMENTOS_OVERBOOK_EXTRA", 1)
        return self.ativo and self.capacidade_utilizada < limite


class WaitlistEntry(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="waitlist_entries")
    slot = models.ForeignKey(Slot, on_delete=models.CASCADE, related_name="waitlist")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="waitlist_entries")
    prioridade = models.PositiveIntegerField(default=100)
    status = models.CharField(max_length=20, default="ATIVO")  # ATIVO, PROMOVIDO, CANCELADO

    class Meta:
        ordering = ["prioridade", "created_at"]
        unique_together = [("slot", "cliente")]


class Agendamento(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="agendamentos")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="agendamentos")
    profissional = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="agendamentos_profissional")
    slot = models.ForeignKey(Slot, on_delete=models.SET_NULL, null=True, blank=True, related_name="agendamentos")
    data_inicio = models.DateTimeField()
    data_fim = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_AGENDAMENTO, default="PENDENTE")
    origem = models.CharField(max_length=15, choices=ORIGEM_AGENDAMENTO, default="OPERADOR")
    # Campo legado tipo_servico removido em migração 0004_remover_tipo_servico
    servico = models.ForeignKey(
        Servico, on_delete=models.CASCADE, related_name="agendamentos", help_text="Serviço unificado associado"
    )
    metadata = models.JSONField(default=dict, blank=True)
    referencia_anterior = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reagendamentos"
    )

    class Meta:
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"
        indexes = [
            models.Index(fields=["tenant", "profissional", "data_inicio"]),
            models.Index(fields=["tenant", "cliente", "data_inicio"]),
            models.Index(fields=["tenant", "status"]),
        ]

    # Compatibilidade legada removida: tipo_servico e agendamento.procedimento


class AuditoriaAgendamento(TimestampedModel):
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE, related_name="auditoria")
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    tipo_evento = models.CharField(max_length=30)
    de_status = models.CharField(max_length=20, blank=True, null=True)
    para_status = models.CharField(max_length=20, blank=True, null=True)
    motivo = models.TextField(blank=True, null=True)
    diff = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "Auditoria de Agendamento"
        verbose_name_plural = "Auditorias de Agendamento"
        ordering = ["-created_at"]


class ProfissionalProcedimento(TimestampedModel):
    """Vincula um profissional aos procedimentos que está habilitado a executar (por tenant).

    Compatível com a proposta de competência Profissional x Procedimento.
    Por padrão, a validação é controlada por feature flag (settings.ENFORCE_COMPETENCIA).
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="competencias_prof_proc")
    profissional = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="competencias_procedimento")
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="profissionais_habilitados")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Competência do Profissional em Serviço")
        verbose_name_plural = _("Competências de Profissionais em Serviços")
        constraints = [
            models.UniqueConstraint(fields=["tenant", "profissional", "servico"], name="uniq_competencia_prof_servico")
        ]
        indexes = [
            models.Index(fields=["tenant", "profissional"]),
            models.Index(fields=["tenant", "servico"]),
        ]

    def __str__(self):
        return f"{self.profissional} habilitado em {getattr(self.servico, 'nome_servico', self.servico_id)} ({self.tenant_id})"
