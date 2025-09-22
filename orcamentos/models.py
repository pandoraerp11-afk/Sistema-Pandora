from django.db import models
from django.urls import reverse

from clientes.models import Cliente
from obras.models import Obra


class Orcamento(models.Model):
    numero = models.CharField(max_length=20, unique=True, verbose_name="Número")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="orcamentos", verbose_name="Cliente")
    obra = models.ForeignKey(
        Obra, on_delete=models.CASCADE, related_name="orcamentos", verbose_name="Obra", null=True, blank=True
    )
    data_emissao = models.DateField(verbose_name="Data de Emissão")
    data_validade = models.DateField(verbose_name="Data de Validade")
    valor_total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Valor Total")
    desconto = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Desconto")
    status = models.CharField(
        max_length=20,
        choices=[
            ("rascunho", "Rascunho"),
            ("enviado", "Enviado"),
            ("aprovado", "Aprovado"),
            ("rejeitado", "Rejeitado"),
            ("cancelado", "Cancelado"),
        ],
        default="rascunho",
        verbose_name="Status",
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Orçamento"
        verbose_name_plural = "Orçamentos"
        ordering = ["-data_emissao"]

    def __str__(self):
        return f"Orçamento #{self.numero} - {self.cliente}"

    def get_absolute_url(self):
        return reverse("orcamentos:orcamento_detail", args=[str(self.id)])

    @property
    def valor_liquido(self):
        return self.valor_total - self.desconto
