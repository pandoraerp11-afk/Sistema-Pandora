from django.db import models


class Movimento(models.Model):
    TIPO_CHOICES = (
        ("entrada", "Entrada"),
        ("saida", "Saída"),
    )

    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, verbose_name="Produto")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name="Tipo de Movimento")
    quantidade = models.PositiveIntegerField(verbose_name="Quantidade")
    data = models.DateTimeField(auto_now_add=True, verbose_name="Data do Movimento")
    observacao = models.TextField(blank=True, null=True, verbose_name="Observação")

    class Meta:
        verbose_name = "Movimento de Estoque"
        verbose_name_plural = "Movimentos de Estoque"
        ordering = ["-data"]

    def __str__(self):
        return f"{self.tipo.capitalize()} - {self.produto.nome} ({self.quantidade})"
