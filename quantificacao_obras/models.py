from django.conf import settings
from django.db import models

from core.models import Tenant, TimestampedModel


class ProjetoQuantificacao(TimestampedModel):
    """Representa um projeto de quantificação de obras."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="projetos_quantificacao")
    nome = models.CharField(max_length=255, verbose_name="Nome do Projeto")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_previsao_conclusao = models.DateField(null=True, blank=True, verbose_name="Previsão de Conclusão")
    status = models.CharField(
        max_length=50,
        choices=[
            ("rascunho", "Rascunho"),
            ("em_andamento", "Em Andamento"),
            ("concluido", "Concluído"),
            ("cancelado", "Cancelado"),
        ],
        default="rascunho",
        verbose_name="Status",
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projetos_quantificacao_responsavel",
    )

    class Meta:
        verbose_name = "Projeto de Quantificação"
        verbose_name_plural = "Projetos de Quantificação"
        ordering = ["-created_at"]

    def __str__(self):
        return self.nome


class ItemQuantificacao(TimestampedModel):
    """Representa um item quantificado dentro de um projeto."""

    projeto = models.ForeignKey(ProjetoQuantificacao, on_delete=models.CASCADE, related_name="itens_quantificacao")
    nome = models.CharField(max_length=255, verbose_name="Nome do Item")
    unidade_medida = models.CharField(max_length=50, verbose_name="Unidade de Medida")
    quantidade = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Quantidade")
    custo_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Custo Unitário"
    )
    custo_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Custo Total"
    )
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    tipo_item = models.CharField(
        max_length=50,
        choices=[
            ("material", "Material"),
            ("mao_de_obra", "Mão de Obra"),
            ("equipamento", "Equipamento"),
            ("servico", "Serviço"),
            ("outro", "Outro"),
        ],
        default="material",
        verbose_name="Tipo de Item",
    )

    class Meta:
        verbose_name = "Item de Quantificação"
        verbose_name_plural = "Itens de Quantificação"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.nome} ({self.quantidade} {self.unidade_medida})"

    def save(self, *args, **kwargs):
        if self.quantidade and self.custo_unitario:
            self.custo_total = self.quantidade * self.custo_unitario
        super().save(*args, **kwargs)


class AnexoQuantificacao(TimestampedModel):
    """Representa um arquivo anexo a um projeto de quantificação."""

    projeto = models.ForeignKey(ProjetoQuantificacao, on_delete=models.CASCADE, related_name="anexos_quantificacao")
    nome_arquivo = models.CharField(max_length=255, verbose_name="Nome do Arquivo")
    arquivo = models.FileField(upload_to="quantificacao_anexos/", verbose_name="Arquivo")
    tipo_arquivo = models.CharField(
        max_length=100, blank=True, verbose_name="Tipo de Arquivo"
    )  # Ex: PDF, DWG, DXF, IFC, RVT, XLSX, DOCX, JPG, PNG
    tamanho_arquivo = models.BigIntegerField(null=True, blank=True, verbose_name="Tamanho (bytes)")
    upload_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anexos_quantificacao_upload",
    )
    observacoes = models.TextField(blank=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Anexo de Quantificação"
        verbose_name_plural = "Anexos de Quantificação"
        ordering = ["-created_at"]

    def __str__(self):
        return self.nome_arquivo
