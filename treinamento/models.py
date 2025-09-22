# treinamento/models.py
from django.db import models
from django.urls import reverse

from funcionarios.models import Funcionario  # Certifique-se que esta importação está correta


class Treinamento(models.Model):  # Nome da classe é Treinamento (singular) - CORRETO
    titulo = models.CharField(max_length=200, verbose_name="Título")
    descricao = models.TextField(verbose_name="Descrição")
    instrutor = models.ForeignKey(
        Funcionario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="treinamentos_ministrados",
        verbose_name="Instrutor",
    )
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Término")
    carga_horaria = models.PositiveIntegerField(verbose_name="Carga Horária (horas)")
    local = models.CharField(max_length=200, verbose_name="Local")
    material = models.FileField(upload_to="treinamentos/", blank=True, null=True, verbose_name="Material")

    class Meta:
        verbose_name = "Treinamento"
        verbose_name_plural = "Treinamentos"
        ordering = ["-data_inicio"]

    def __str__(self):
        return self.titulo

    def get_absolute_url(self):
        # O nome da rota 'treinamento_detail' precisa corresponder ao que está em treinamento/urls.py
        return reverse("treinamento:treinamento_detail", args=[str(self.id)])
