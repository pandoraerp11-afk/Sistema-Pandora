from django.db import models
from django.urls import reverse

from obras.models import Obra


# ------------------------------
class Financeiro(models.Model):
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor")
    data = models.DateField(verbose_name="Data")
    tipo = models.CharField(
        max_length=20, choices=[("receita", "Receita"), ("despesa", "Despesa")], verbose_name="Tipo"
    )
    categoria = models.CharField(
        max_length=50,
        choices=[
            ("material", "Material"),
            ("mao_obra", "Mão de Obra"),
            ("equipamento", "Equipamento"),
            ("administrativo", "Administrativo"),
            ("imposto", "Imposto"),
            ("outros", "Outros"),
        ],
        verbose_name="Categoria",
    )
    obra = models.ForeignKey(
        Obra, on_delete=models.CASCADE, related_name="financeiros", verbose_name="Obra", null=True, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=[("pendente", "Pendente"), ("pago", "Pago"), ("recebido", "Recebido"), ("cancelado", "Cancelado")],
        default="pendente",
        verbose_name="Status",
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Financeiro"
        verbose_name_plural = "Financeiro"
        ordering = ["-data"]

    def __str__(self):
        return f"{self.descricao} - {self.tipo} - {self.valor}"

    def get_absolute_url(self):
        return reverse("financeiro:financeiro_detail", args=[str(self.id)])


# ------------------------------
class ContaPagar(models.Model):
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    fornecedor = models.ForeignKey("fornecedores.Fornecedor", on_delete=models.CASCADE, verbose_name="Fornecedor")
    data_vencimento = models.DateField(verbose_name="Data de Vencimento")
    data_pagamento = models.DateField(null=True, blank=True, verbose_name="Data de Pagamento")
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor")
    status = models.CharField(
        max_length=20,
        choices=[("pendente", "Pendente"), ("pago", "Pago"), ("atrasado", "Atrasado")],
        default="pendente",
        verbose_name="Status",
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Conta a Pagar"
        verbose_name_plural = "Contas a Pagar"
        ordering = ["-data_vencimento"]

    def __str__(self):
        return f"{self.descricao} - {self.fornecedor} - R${self.valor}"

    def get_absolute_url(self):
        return reverse("financeiro:conta_pagar_detail", args=[str(self.id)])


# ------------------------------
class ContaReceber(models.Model):
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.CASCADE, verbose_name="Cliente")
    data_vencimento = models.DateField(verbose_name="Data de Vencimento")
    data_recebimento = models.DateField(null=True, blank=True, verbose_name="Data de Recebimento")
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor")
    status = models.CharField(
        max_length=20,
        choices=[("pendente", "Pendente"), ("recebido", "Recebido"), ("atrasado", "Atrasado")],
        default="pendente",
        verbose_name="Status",
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Conta a Receber"
        verbose_name_plural = "Contas a Receber"
        ordering = ["-data_vencimento"]

    def __str__(self):
        return f"{self.descricao} - {self.cliente} - R${self.valor}"

    def get_absolute_url(self):
        return reverse("financeiro:conta_receber_detail", args=[str(self.id)])
