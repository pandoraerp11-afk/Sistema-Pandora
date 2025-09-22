# formularios/models.py
from django.db import models
from django.urls import reverse


class Formulario(models.Model):  # Nome da classe é Formulario (singular) - CORRETO
    titulo = models.CharField(max_length=200, verbose_name="Título")
    descricao = models.TextField(verbose_name="Descrição")
    tipo = models.CharField(
        max_length=50,
        choices=[
            ("inspecao", "Inspeção"),
            ("avaliacao", "Avaliação"),
            ("checklist", "Checklist"),
            ("pesquisa", "Pesquisa"),
            ("outro", "Outro"),
        ],
        default="checklist",
        verbose_name="Tipo",
    )
    data_criacao = models.DateField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateField(auto_now=True, verbose_name="Data de Atualização")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        verbose_name = "Formulário"
        verbose_name_plural = "Formulários"
        ordering = ["titulo"]

    def __str__(self):
        return f"{self.titulo} ({self.tipo})"  # No models.py original, era self.get_tipo_display(), mas tipo já é string. Se tipo for chave, use get_tipo_display.

    def get_absolute_url(self):
        # O nome da rota 'formulario_detail' precisa corresponder ao que está em formularios/urls.py
        return reverse("formularios:formularios_detail", args=[str(self.id)])  # Ajustado para 'formularios_detail'
