# relatorios/models.py
from django.db import models
from django.urls import reverse


class Relatorio(models.Model):  # Nome da classe é Relatorio (singular) - CORRETO
    titulo = models.CharField(max_length=200, verbose_name="Título")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    tipo = models.CharField(
        max_length=50,
        choices=[
            ("financeiro", "Financeiro"),
            ("obra", "Obra"),
            ("estoque", "Estoque"),
            ("funcionarios", "Funcionários"),
            ("clientes", "Clientes"),
            ("personalizado", "Personalizado"),
        ],
        default="personalizado",
        verbose_name="Tipo",
    )
    arquivo = models.FileField(upload_to="relatorios/", blank=True, null=True, verbose_name="Arquivo")

    class Meta:
        verbose_name = "Relatório"
        verbose_name_plural = "Relatórios"
        ordering = ["-data_criacao"]

    def __str__(self):
        return self.titulo

    def get_absolute_url(self):
        # O nome da rota 'relatorio_detail' precisa corresponder ao que está em relatorios/urls.py
        return reverse("relatorios:relatorios_detail", args=[str(self.id)])  # Ajustado para 'relatorios_detail'
