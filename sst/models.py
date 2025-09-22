# sst/models.py
from django.db import models
from django.urls import reverse

from funcionarios.models import Funcionario  # Certifique-se que esta importação está correta


class DocumentoSST(models.Model):  # Nome da classe é DocumentoSST - CORRETO
    titulo = models.CharField(max_length=200, verbose_name="Título")
    descricao = models.TextField(verbose_name="Descrição")
    tipo = models.CharField(
        max_length=50,
        choices=[
            ("procedimento", "Procedimento de Segurança"),
            ("analise_risco", "Análise de Risco"),
            ("treinamento", "Registro de Treinamento"),  # Se refere a um registro, não ao app Treinamento
            ("acidente", "Registro de Acidente"),
            ("epi", "Controle de EPI"),
            ("outro", "Outro"),
        ],
        default="procedimento",
        verbose_name="Tipo",
    )
    data_criacao = models.DateField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateField(auto_now=True, verbose_name="Data de Atualização")
    responsavel = models.ForeignKey(
        Funcionario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_sst",
        verbose_name="Responsável",
    )  # Adicionado blank=True
    arquivo = models.FileField(
        upload_to="sst_documentos/", blank=True, null=True, verbose_name="Arquivo"
    )  # Alterado upload_to para ser mais específico

    class Meta:
        verbose_name = "Documento SST"
        verbose_name_plural = "Documentos SST"
        ordering = ["-data_criacao"]

    def __str__(self):
        return f"{self.titulo} ({self.get_tipo_display()})"  # Usando get_tipo_display para mostrar o label da choice

    def get_absolute_url(self):
        # O nome da rota 'documento_sst_detail' precisa corresponder ao que está em sst/urls.py
        # Ajustado para 'sst_detail' para corresponder ao seu urls.py para 'sst'
        return reverse("sst:sst_detail", args=[str(self.id)])
