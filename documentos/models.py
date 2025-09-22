from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import Tenant


class CategoriaDocumento(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name=_("Nome da Categoria"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    ordem = models.PositiveIntegerField(default=0, verbose_name=_("Ordem"))

    class Meta:
        verbose_name = _("Categoria de Documento")
        verbose_name_plural = _("Categorias de Documento")
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class TipoDocumento(models.Model):
    PERIODICIDADE_CHOICES = [
        ("unico", _("Único")),
        ("mensal", _("Mensal")),
        ("anual", _("Anual")),
        ("eventual", _("Eventual")),
    ]
    nome = models.CharField(max_length=100, unique=True, verbose_name=_("Nome do Documento"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    categoria = models.ForeignKey(
        CategoriaDocumento, on_delete=models.CASCADE, related_name="tipos", verbose_name=_("Categoria")
    )
    periodicidade = models.CharField(
        max_length=10, choices=PERIODICIDADE_CHOICES, default="unico", verbose_name=_("Periodicidade")
    )
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    versionavel = models.BooleanField(default=True, verbose_name=_("Versionável"))
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Tipo de Documento")
        verbose_name_plural = _("Tipos de Documento")
        ordering = ["categoria__ordem", "nome"]

    def __str__(self):
        return self.nome


class DominioDocumento(models.Model):
    """Domínio (escopo lógico) para agrupar regras por módulo/app de forma controlada.
    Evita uso livre de app_label textual e permite permissões específicas.
    """

    nome = models.CharField(max_length=100, unique=True, verbose_name=_("Nome do Domínio"))
    slug = models.SlugField(max_length=100, unique=True, verbose_name=_("Slug"))
    app_label = models.CharField(max_length=50, verbose_name=_("App Label"))
    descricao = models.CharField(max_length=255, blank=True, verbose_name=_("Descrição"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Domínio de Documento")
        verbose_name_plural = _("Domínios de Documento")
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["app_label"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self):
        return self.nome


class RegraDocumento(models.Model):
    """Regra parametrizada que define a exigência de um TipoDocumento para uma entidade específica
    (ex: Fornecedor X) e/ou suas subentidades (ex: funcionários terceirizados) com possibilidade de
    sobrescrever periodicidade e exigência.
    """

    NIVEL_APLICACAO_CHOICES = [
        ("entidade", _("Entidade (direto)")),
        ("subentidades", _("Subentidades (ex: Funcionários)")),
    ]
    EXIGENCIA_CHOICES = [
        ("obrigatorio", _("Obrigatório")),
        ("recomendado", _("Recomendado")),
        ("opcional", _("Opcional")),
    ]

    ESCOPO_CHOICES = [
        ("app", _("Plataforma (todos os tenants)")),
        ("tenant", _("Empresa (tenant atual)")),
        ("filtro", _("Filtro avançado")),
        ("entidade", _("Entidade específica")),
    ]

    # Escopo de aplicação
    escopo = models.CharField(max_length=20, choices=ESCOPO_CHOICES, default="entidade", verbose_name=_("Escopo"))
    # Mantido para compat retro; migrar para dominio. Pode ser null futuramente.
    app_label = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("App Label (Legado)"))
    dominio = models.ForeignKey(
        "DominioDocumento",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="regras",
        verbose_name=_("Domínio"),
    )
    # Tenant escopo intermediário (quando escopo='tenant')
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="regras_documento",
        verbose_name=_("Tenant"),
    )

    # Vínculo com entidade específica (quando escopo='entidade')
    entidade_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, verbose_name=_("Entidade"), blank=True, null=True
    )
    entidade_object_id = models.PositiveIntegerField(verbose_name=_("ID Entidade"), blank=True, null=True)
    entidade = GenericForeignKey("entidade_content_type", "entidade_object_id")
    tipo = models.ForeignKey(
        "TipoDocumento", on_delete=models.CASCADE, related_name="regras", verbose_name=_("Tipo de Documento")
    )
    nivel_aplicacao = models.CharField(
        max_length=20, choices=NIVEL_APLICACAO_CHOICES, default="entidade", verbose_name=_("Nível de Aplicação")
    )
    periodicidade_override = models.CharField(
        max_length=10,
        choices=TipoDocumento.PERIODICIDADE_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Periodicidade (Override)"),
    )
    exigencia = models.CharField(
        max_length=20, choices=EXIGENCIA_CHOICES, default="obrigatorio", verbose_name=_("Exigência")
    )
    validade_dias = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=_("Se informado, calcula vencimento automático"),
        verbose_name=_("Validade (dias)"),
    )
    data_base = models.DateField(blank=True, null=True, verbose_name=_("Data Base"))

    # Filtros específicos (ex.: fornecedores)
    FORN_TIPO_CHOICES = [
        ("PRODUTOS", _("Produtos")),
        ("SERVICOS", _("Serviços")),
        ("AMBOS", _("Ambos")),
    ]
    filtro_tipo_fornecimento = models.CharField(
        max_length=10, choices=FORN_TIPO_CHOICES, blank=True, null=True, verbose_name=_("Tipo de Fornecimento (Filtro)")
    )
    observacoes = models.CharField(max_length=255, blank=True, verbose_name=_("Observações"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    STATUS_CHOICES = [
        ("rascunho", _("Rascunho")),
        ("pendente", _("Pendente Aprovação")),
        ("aprovada", _("Aprovada")),
        ("inativa", _("Inativada")),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="aprovada", verbose_name=_("Status"))
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Regra de Documento")
        verbose_name_plural = _("Regras de Documentos")
        ordering = ["tipo__nome"]
        indexes = [
            models.Index(fields=["entidade_content_type", "entidade_object_id"]),
            models.Index(fields=["ativo"]),
            models.Index(fields=["app_label"]),
            models.Index(fields=["escopo"]),
            models.Index(fields=["status"]),
            models.Index(fields=["dominio"]),
        ]

    def __str__(self):
        return f"{self.entidade} -> {self.tipo} ({self.get_nivel_aplicacao_display()})"

    @property
    def periodicidade_efetiva(self):
        return self.periodicidade_override or self.tipo.periodicidade

    def clean(self):  # noqa
        from django.core.exceptions import ValidationError

        # Unicidade lógica: impedir múltiplas aprovadas ativas com mesmo escopo-chave
        if self.status in ("aprovada",) and self.ativo:
            qs = RegraDocumento.objects.filter(tipo=self.tipo, escopo=self.escopo, ativo=True, status="aprovada")
            if self.escopo in ("app", "filtro"):
                qs = qs.filter(dominio=self.dominio, tenant__isnull=True)
            elif self.escopo == "tenant":
                qs = qs.filter(tenant=self.tenant)
            elif self.escopo == "entidade":
                qs = qs.filter(
                    entidade_content_type=self.entidade_content_type, entidade_object_id=self.entidade_object_id
                )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"__all__": [_("Já existe uma regra aprovada ativa para este escopo e tipo.")]})


class Documento(models.Model):
    entidade_content_type = models.ForeignKey("contenttypes.ContentType", on_delete=models.CASCADE)
    entidade_object_id = models.PositiveIntegerField()
    entidade = GenericForeignKey("entidade_content_type", "entidade_object_id")
    tipo = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT, related_name="documentos", verbose_name=_("Tipo de Documento")
    )
    periodicidade_aplicada = models.CharField(
        max_length=10,
        choices=TipoDocumento.PERIODICIDADE_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Periodicidade Aplicada"),
        help_text=_("Se vazio usa a do tipo/regra"),
    )
    obrigatorio = models.BooleanField(default=True, verbose_name=_("Obrigatório"))
    observacao = models.CharField(max_length=255, blank=True, verbose_name=_("Observação"))
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Documento Associado")
        verbose_name_plural = _("Documentos Associados")
        unique_together = ("entidade_content_type", "entidade_object_id", "tipo")

    def __str__(self):
        return f"{self.entidade} - {self.tipo}"


class DocumentoVersao(models.Model):
    documento = models.ForeignKey(
        Documento, on_delete=models.CASCADE, related_name="versoes", verbose_name=_("Documento")
    )
    arquivo = models.FileField(upload_to="documentos/")
    competencia = models.CharField(max_length=7, blank=True, help_text=_("MM/AAAA se aplicável"))
    observacao = models.CharField(max_length=255, blank=True, verbose_name=_("Observação"))
    enviado_por = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Enviado por")
    )
    enviado_em = models.DateTimeField(auto_now_add=True, verbose_name=_("Enviado em"))
    versao = models.PositiveIntegerField(default=1, verbose_name=_("Versão"))
    status = models.CharField(
        max_length=20,
        choices=[
            ("pendente", _("Pendente")),
            ("aprovado", _("Aprovado")),
            ("reprovado", _("Reprovado")),
            ("vencido", _("Vencido")),
        ],
        default="pendente",
        verbose_name=_("Status"),
    )
    validade_data = models.DateField(blank=True, null=True, verbose_name=_("Validade"))

    class Meta:
        verbose_name = _("Versão de Documento")
        verbose_name_plural = _("Versões de Documento")
        ordering = ["-enviado_em", "-versao"]
        unique_together = ("documento", "competencia", "versao")

    def __str__(self):
        return f"{self.documento} v{self.versao} ({self.competencia})"


class WizardTenantDocumentoTemp(models.Model):
    """Armazena uploads temporários feitos no Wizard de criação/edição de Tenant
    antes de consolidar em Documentos definitivos. É descartável após conclusão.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="wizard_docs_temp")
    session_key = models.CharField(
        max_length=64, blank=True, null=True, help_text=_("Chave de sessão antes de existir tenant")
    )
    tipo = models.ForeignKey(TipoDocumento, on_delete=models.CASCADE, related_name="wizard_temp_docs")
    obrigatorio_snapshot = models.BooleanField(default=False)
    nome_tipo_cache = models.CharField(max_length=120)
    arquivo = models.FileField(upload_to="wizard_docs_temp/")
    filename_original = models.CharField(max_length=255, blank=True)
    tamanho_bytes = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Documento Temporário (Wizard)")
        verbose_name_plural = _("Documentos Temporários (Wizard)")
        indexes = [
            models.Index(fields=["tenant", "session_key"]),
            models.Index(fields=["tipo"]),
        ]

    def __str__(self):
        return f"TEMP {self.tenant_id or self.session_key} - {self.nome_tipo_cache}"
