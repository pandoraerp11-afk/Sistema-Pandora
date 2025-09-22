from django.db import models

from cadastros_gerais.models_tipo_documento import TipoDocumento


class FornecedorDocumentoVersao(models.Model):
    fornecedor = models.ForeignKey(
        "fornecedores.Fornecedor", on_delete=models.CASCADE, related_name="documentos_enviados"
    )
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.CASCADE)
    arquivo = models.FileField(upload_to="documentos_fornecedores/")
    competencia = models.CharField(max_length=7, blank=True, help_text="MM/AAAA se aplicável")
    observacao = models.CharField(max_length=255, blank=True)
    enviado_por = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    enviado_em = models.DateTimeField(auto_now_add=True)
    versao = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-enviado_em"]
        unique_together = ("fornecedor", "tipo_documento", "competencia", "versao")

    def __str__(self):
        return f"{self.fornecedor} - {self.tipo_documento} v{self.versao} ({self.competencia})"
