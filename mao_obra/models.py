# mao_obra/models.py
from django.db import models
from django.urls import reverse

from core.models import Tenant
from funcionarios.models import Funcionario
from obras.models import Obra


class MaoObra(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="Empresa")
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="mao_obra", verbose_name="Funcionário"
    )
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="mao_obra_registros", verbose_name="Obra")
    data = models.DateField(verbose_name="Data")
    atividade = models.CharField(max_length=200, verbose_name="Atividade")
    horas_trabalhadas = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Horas Trabalhadas")
    valor_hora = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor por Hora")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    # Campos de auditoria
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Mão de Obra"
        verbose_name_plural = "Registros de Mão de Obra"
        ordering = ["-data", "-created_at"]
        unique_together = [["tenant", "funcionario", "obra", "data"]]  # Evita registros duplicados no mesmo dia
        indexes = [
            models.Index(fields=["tenant", "data"]),
            models.Index(fields=["tenant", "funcionario"]),
            models.Index(fields=["tenant", "obra"]),
        ]

    def __str__(self):
        return f"{self.funcionario} - {self.atividade} ({self.data})"

    def get_absolute_url(self):
        return reverse("mao_obra:mao_obra_detail", args=[str(self.id)])

    @property
    def valor_total(self):
        """Calcula o valor total (horas * valor_hora)"""
        return self.horas_trabalhadas * self.valor_hora

    @property
    def duracao_formatada(self):
        """Retorna as horas trabalhadas em formato legível"""
        horas = int(self.horas_trabalhadas)
        minutos = int((self.horas_trabalhadas - horas) * 60)

        if minutos > 0:
            return f"{horas}h {minutos}min"
        return f"{horas}h"
