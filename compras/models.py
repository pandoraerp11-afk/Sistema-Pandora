# compras/models.py
from django.db import models
from django.urls import reverse

from fornecedores.models import Fornecedor  # Supondo que Fornecedor está em fornecedores.models
from obras.models import Obra  # Supondo que Obra está em obras.models


class Compra(models.Model):  # Nome da classe é Compra (singular) - CORRETO
    numero = models.CharField(max_length=20, unique=True, verbose_name="Número")
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.CASCADE, related_name="compras", verbose_name="Fornecedor"
    )
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="compras", verbose_name="Obra")
    data_pedido = models.DateField(verbose_name="Data do Pedido")
    data_entrega_prevista = models.DateField(verbose_name="Data de Entrega Prevista")
    data_entrega_real = models.DateField(null=True, blank=True, verbose_name="Data de Entrega Real")
    valor_total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Valor Total")
    status = models.CharField(
        max_length=20,
        choices=[
            ("pendente", "Pendente"),
            ("aprovado", "Aprovado"),
            ("em_transito", "Em Trânsito"),
            ("entregue", "Entregue"),
            ("cancelado", "Cancelado"),
        ],
        default="pendente",
        verbose_name="Status",
    )
    forma_pagamento = models.CharField(
        max_length=20,
        choices=[
            ("a_vista", "À Vista"),
            ("30_dias", "30 Dias"),
            ("60_dias", "60 Dias"),
            ("90_dias", "90 Dias"),
            ("parcelado", "Parcelado"),
        ],
        default="30_dias",
        verbose_name="Forma de Pagamento",
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ["-data_pedido"]

    def __str__(self):
        return f"Compra #{self.numero} - {self.fornecedor}"

    def get_absolute_url(self):
        # O nome da rota 'compra_detail' precisa corresponder ao que está em compras/urls.py
        return reverse(
            "compras:compras_detail", args=[str(self.id)]
        )  # Ajustado para 'compras_detail' conforme seu urls.py
