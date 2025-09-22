# obras/models.py
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

# A importação do cliente deve ser do seu app de clientes.
# Verifique se o caminho 'clientes.models' está correto para o seu projeto.
from clientes.models import Cliente


# Função para definir o caminho de upload dos documentos de forma organizada
def get_documento_upload_path(instance, filename):
    # O arquivo será salvo em: media/obra_{id}/documentos/{nome_do_arquivo}
    return f"obra_{instance.obra.id}/documentos/{filename}"


class Obra(models.Model):
    # --- Identificação e Tipo ---
    nome = models.CharField(max_length=200, verbose_name="Nome da Obra")
    TIPO_OBRA_CHOICES = [
        ("construcao", "Construção Nova"),
        ("reforma", "Reforma"),
        ("manutencao", "Manutenção"),
        ("ampliacao", "Ampliação"),
        ("demolicao", "Demolição"),
        ("loteamento", "Loteamento"),
    ]
    tipo_obra = models.CharField(
        max_length=20, choices=TIPO_OBRA_CHOICES, default="construcao", verbose_name="Tipo de Obra"
    )
    cno = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="CNO (Cadastro Nacional de Obras)",
        help_text="Cadastro Nacional de Obras, se aplicável.",
        null=True,
        blank=True,
    )

    # --- Cliente Principal (Contratante) ---
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name="obras_principais",
        verbose_name="Cliente Principal (Contratante)",
        help_text="Cliente principal ou contratante. Deixe em branco se for uma obra da própria construtora.",
        null=True,
        blank=True,
    )

    # --- Localização ---
    endereco = models.TextField(verbose_name="Endereço")
    cidade = models.CharField(max_length=100, verbose_name="Cidade")
    estado = models.CharField(max_length=2, verbose_name="Estado")
    cep = models.CharField(max_length=10, verbose_name="CEP")

    # --- Prazos e Valores ---
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_previsao_termino = models.DateField(verbose_name="Previsão de Término")
    data_termino = models.DateField(null=True, blank=True, verbose_name="Data de Término Real")
    valor_contrato = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Valor do Contrato (Principal)")
    valor_total = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, verbose_name="Custo Total Estimado da Obra"
    )

    # --- Status e Progresso ---
    STATUS_OBRA_CHOICES = [
        ("planejamento", "Planejamento"),
        ("em_andamento", "Em Andamento"),
        ("pausada", "Pausada"),
        ("concluida", "Concluída"),
        ("cancelada", "Cancelada"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_OBRA_CHOICES, default="planejamento", verbose_name="Status da Obra"
    )
    progresso = models.PositiveSmallIntegerField(
        verbose_name="Progresso (%)", default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # --- Outras Informações ---
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações Gerais")

    class Meta:
        verbose_name = "Obra"
        verbose_name_plural = "Obras"
        ordering = ["-data_inicio"]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("obras:obra_detail", args=[str(self.id)])


class ModeloUnidade(models.Model):
    """Modelo/planta de unidade para uma Obra (ex.: Tipo 01, 02, 03, 04)."""

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="modelos", verbose_name="Obra")
    codigo = models.CharField(max_length=20, verbose_name="Código", help_text="Ex.: 01, 02, 03, 04")
    nome = models.CharField(max_length=100, verbose_name="Nome do Modelo", help_text="Ex.: Apto Tipo 01")
    TIPO_UNIDADE_CHOICES = [
        ("apartamento", "Apartamento"),
        ("sala_comercial", "Sala Comercial"),
        ("casa", "Casa"),
        ("lote", "Lote"),
        ("andar", "Andar Corporativo"),
        ("loja", "Loja"),
    ]
    tipo_unidade = models.CharField(
        max_length=20, choices=TIPO_UNIDADE_CHOICES, default="apartamento", verbose_name="Tipo"
    )
    dormitorios = models.PositiveSmallIntegerField(default=0, verbose_name="Dormitórios")
    suites = models.PositiveSmallIntegerField(default=0, verbose_name="Suítes")
    banheiros = models.PositiveSmallIntegerField(default=1, verbose_name="Banheiros")
    vagas = models.PositiveSmallIntegerField(default=0, verbose_name="Vagas de Garagem")
    area_privativa = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Área Privativa (m²)"
    )
    area_total = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Área Total (m²)"
    )
    preco_sugerido = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Preço Sugerido"
    )
    ambientes = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Ambientes",
        help_text='Lista de ambientes com nome e área. Ex.: [{"nome":"Sala","area":20}]',
    )

    class Meta:
        verbose_name = "Modelo de Unidade"
        verbose_name_plural = "Modelos de Unidade"
        unique_together = ("obra", "codigo")
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    def _generate_next_codigo(self):
        """Gera próximo código sequencial por obra. Usa zero-fill com largura mínima 2.
        Considera apenas códigos totalmente numéricos; se não houver, começa em 1.
        Garante unicidade incrementando até achar um livre.
        """
        if not self.obra_id:
            # Sem obra não há como sequenciar; fallback
            return "01"
        # Coleta códigos existentes da mesma obra
        existing = list(ModeloUnidade.objects.filter(obra_id=self.obra_id).values_list("codigo", flat=True))
        numeric_vals = []
        width = 2
        for c in existing:
            c_str = str(c).strip()
            if c_str.isdigit():
                numeric_vals.append(int(c_str))
                width = max(width, len(c_str))
        next_num = (max(numeric_vals) + 1) if numeric_vals else 1
        # Tenta até encontrar um código livre
        attempt = next_num
        while True:
            candidate = str(attempt).zfill(width)
            if not ModeloUnidade.objects.filter(obra_id=self.obra_id, codigo=candidate).exists():
                return candidate
            attempt += 1

    def save(self, *args, **kwargs):
        # Auto-gerar código se não informado ou vazio
        if not self.codigo or not str(self.codigo).strip():
            self.codigo = self._generate_next_codigo()
        super().save(*args, **kwargs)


class Unidade(models.Model):
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="unidades", verbose_name="Obra")
    modelo = models.ForeignKey(
        "ModeloUnidade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unidades",
        verbose_name="Modelo",
    )
    bloco = models.CharField(max_length=50, null=True, blank=True, verbose_name="Bloco/Torre")
    andar = models.IntegerField(null=True, blank=True, verbose_name="Andar")
    numero = models.CharField(max_length=20, null=True, blank=True, verbose_name="Número")
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name="unidades_adquiridas",
        verbose_name="Cliente (Proprietário da Unidade)",
        null=True,
        blank=True,
    )
    identificador = models.CharField(
        max_length=100, verbose_name="Identificador da Unidade", help_text="Ex: Apartamento 101, Lote 15, Sala 302"
    )
    TIPO_UNIDADE_CHOICES = [
        ("apartamento", "Apartamento"),
        ("sala_comercial", "Sala Comercial"),
        ("casa", "Casa"),
        ("lote", "Lote"),
        ("andar", "Andar Corporativo"),
        ("loja", "Loja"),
    ]
    tipo_unidade = models.CharField(max_length=20, choices=TIPO_UNIDADE_CHOICES, verbose_name="Tipo de Unidade")
    area_m2 = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Área (m²)", null=True, blank=True)

    STATUS_UNIDADE_CHOICES = [
        ("disponivel", "Disponível"),
        ("reservado", "Reservado"),
        ("vendido", "Vendido"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_UNIDADE_CHOICES, default="disponivel", verbose_name="Status da Unidade"
    )

    class Meta:
        verbose_name = "Unidade da Obra"
        verbose_name_plural = "Unidades da Obra"
        ordering = ["identificador"]
        unique_together = (("obra", "identificador"),)

    def __str__(self):
        return f"{self.identificador} (Obra: {self.obra.nome})"


class DocumentoObra(models.Model):
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="documentos", verbose_name="Obra")
    descricao = models.CharField(max_length=255, verbose_name="Descrição do Documento")
    arquivo = models.FileField(upload_to=get_documento_upload_path, verbose_name="Arquivo")
    data_upload = models.DateTimeField(auto_now_add=True, verbose_name="Data de Upload")

    CATEGORIA_CHOICES = [
        ("projeto", "Projeto"),
        ("licenca", "Licença / Alvará"),
        ("contrato", "Contrato"),
        ("orcamento", "Orçamento"),
        ("memorial", "Memorial Descritivo"),
        ("foto", "Foto de Andamento"),
        ("outro", "Outro"),
    ]
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default="outro", verbose_name="Categoria")

    class Meta:
        verbose_name = "Documento da Obra"
        verbose_name_plural = "Documentos da Obra"
        ordering = ["-data_upload"]

    def __str__(self):
        return self.descricao
