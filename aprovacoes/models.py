# aprovacoes/models.py
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse

User = get_user_model()


class Aprovacao(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("aprovado", "Aprovado"),
        ("rejeitado", "Rejeitado"),
        ("cancelado", "Cancelado"),
    ]

    TIPO_CHOICES = [
        ("despesa", "Despesa"),
        ("compra", "Compra"),
        ("contrato", "Contrato"),
        ("investimento", "Investimento"),
        ("orcamento", "Orçamento"),
        ("outro", "Outro"),
    ]

    PRIORIDADE_CHOICES = [
        ("baixa", "Baixa"),
        ("media", "Média"),
        ("alta", "Alta"),
        ("urgente", "Urgente"),
    ]

    titulo = models.CharField(max_length=200, verbose_name="Título")
    descricao = models.TextField(verbose_name="Descrição")
    tipo_aprovacao = models.CharField(
        max_length=20, choices=TIPO_CHOICES, default="outro", verbose_name="Tipo de Aprovação"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente", verbose_name="Status")
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default="media", verbose_name="Prioridade")
    valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Valor")
    solicitante = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="aprovacoes_solicitadas",
        verbose_name="Solicitante",
        null=True,  # Permitir nulo temporariamente
        blank=True,
    )
    aprovador = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aprovacoes_gerenciadas",
        verbose_name="Aprovador",
    )
    data_solicitacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Solicitação")
    data_aprovacao = models.DateTimeField(blank=True, null=True, verbose_name="Data de Aprovação")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Aprovação"
        verbose_name_plural = "Aprovações"
        ordering = ["-data_solicitacao"]

    def __str__(self):
        return f"{self.titulo} - {self.get_status_display()}"

    def get_absolute_url(self):
        return reverse("aprovacoes:aprovacoes_detail", args=[str(self.id)])

    def get_status_color(self):
        """Retorna a cor do status para uso nos templates"""
        colors = {
            "pendente": "warning",
            "aprovado": "success",
            "rejeitado": "danger",
            "cancelado": "secondary",
        }
        return colors.get(self.status, "primary")

    def get_prioridade_color(self):
        """Retorna a cor da prioridade para uso nos templates"""
        colors = {
            "baixa": "info",
            "media": "primary",
            "alta": "warning",
            "urgente": "danger",
        }
        return colors.get(self.prioridade, "primary")

    def can_approve(self):
        """Verifica se a aprovação pode ser aprovada"""
        return self.status == "pendente"

    def can_reject(self):
        """Verifica se a aprovação pode ser rejeitada"""
        return self.status == "pendente"
