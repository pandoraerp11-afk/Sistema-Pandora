# apropriacao/models.py
from django.db import models
from django.urls import reverse

from funcionarios.models import Funcionario  # Certifique-se que esta importação está correta
from obras.models import Obra  # Certifique-se que esta importação está correta


class Apropriacao(models.Model):  # Nome da classe é Apropriacao (singular) - CORRETO
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="apropriacoes", verbose_name="Obra")
    data = models.DateField(verbose_name="Data")
    responsavel = models.ForeignKey(
        Funcionario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="apropriacoes",
        verbose_name="Responsável",
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Apropriação"
        verbose_name_plural = "Apropriações"
        ordering = ["-data"]

    def __str__(self):
        # Adicionei uma verificação para o caso de obra não ter sido carregada ou não ter nome
        obra_nome = self.obra.nome if hasattr(self.obra, "nome") and self.obra.nome else "Obra não especificada"
        return f"{self.descricao} - {obra_nome} ({self.data})"

    def get_absolute_url(self):
        # O nome da rota 'apropriacao_detail' precisa corresponder ao que está em apropriacao/urls.py
        return reverse("apropriacao:apropriacao_detail", args=[str(self.id)])
