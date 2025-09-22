from django.db import models


class TipoDocumento(models.Model):
    CATEGORIAS = [
        ("empresa", "Empresa"),
        ("financeiro", "Financeiro"),
        ("ambiental", "Ambiental"),
        ("produto", "Produto"),
        ("funcionario", "Funcionário"),
        ("outros", "Outros"),
    ]
    PERIODICIDADE = [
        ("unico", "Único"),
        ("mensal", "Mensal"),
        ("anual", "Anual"),
        ("eventual", "Eventual"),
    ]
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS)
    periodicidade = models.CharField(max_length=10, choices=PERIODICIDADE, default="unico")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome


class FornecedorDocumentoTipo(models.Model):
    fornecedor = models.ForeignKey("fornecedores.Fornecedor", on_delete=models.CASCADE, related_name="tipos_documentos")
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.CASCADE)
    obrigatorio = models.BooleanField(default=True)
    observacao = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("fornecedor", "tipo_documento")

    def __str__(self):
        return f"{self.fornecedor} - {self.tipo_documento}"
