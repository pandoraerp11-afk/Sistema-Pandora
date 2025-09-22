# cadastros_gerais/models.py
from django.db import models
from django.db.models import JSONField
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class UnidadeMedida(models.Model):
    """
    Representa as unidades de medida utilizáveis no sistema (ex: Unidade, Metro, KG).
    """

    nome = models.CharField(max_length=50, unique=True, verbose_name=_("Nome da Unidade"))
    # GARANTINDO QUE O NOME DO CAMPO É 'simbolo'
    simbolo = models.CharField(max_length=10, unique=True, verbose_name=_("Símbolo / Sigla"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))

    class Meta:
        verbose_name = _("Unidade de Medida")
        verbose_name_plural = _("Unidades de Medida")
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.simbolo})"

    def __eq__(self, other: object):
        if isinstance(other, str):
            return other in (self.simbolo, self.nome)
        return super().__eq__(other)

    # Compatibilidade legado: aceitar criação com kwargs 'codigo' e/ou 'sigla'
    def __init__(self, *args, **kwargs):
        codigo = kwargs.pop("codigo", None)
        sigla = kwargs.pop("sigla", None)
        # Prioridade: simbolo explícito > sigla > codigo
        simbolo = kwargs.get("simbolo") or sigla or codigo
        if simbolo and "simbolo" not in kwargs:
            kwargs["simbolo"] = simbolo
        super().__init__(*args, **kwargs)

    def get_absolute_url(self):
        """
        Retorna a URL para a página de edição desta unidade de medida.
        """
        return reverse("cadastros_gerais:unidade_medida_update", kwargs={"pk": self.pk})


class CategoriaAuxiliar(models.Model):
    """Categoria dinâmica para agrupar itens auxiliares (ex.: 'documento', 'rede_social')."""

    nome = models.CharField(max_length=80, unique=True, verbose_name=_("Nome"))
    slug = models.SlugField(max_length=80, unique=True, verbose_name=_("Slug"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    ordem = models.PositiveIntegerField(default=0, verbose_name=_("Ordem"))

    class Meta:
        verbose_name = _("Categoria Auxiliar")
        verbose_name_plural = _("Categorias Auxiliares")
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)


class AlvoAplicacao(models.Model):
    """Alvos (módulos) em que um Item Auxiliar se aplica (multi-seleção)."""

    code = models.CharField(max_length=20, unique=True, verbose_name=_("Código"))
    nome = models.CharField(max_length=50, verbose_name=_("Nome"))

    class Meta:
        verbose_name = _("Alvo de Aplicação")
        verbose_name_plural = _("Alvos de Aplicação")
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class ItemAuxiliar(models.Model):
    """Item configurável pertencente a uma CategoriaAuxiliar (ex.: 'CPF', 'LinkedIn')."""

    ALVOS = [
        ("cliente", _("Cliente")),
        ("fornecedor", _("Fornecedor")),
        ("funcionario", _("Funcionário")),
        ("empresa", _("Empresa/Tenant")),
        ("produto", _("Produto")),
        ("servico", _("Serviço")),
        ("outro", _("Outro")),
    ]

    # Novos choices para periodicidade de documentos
    PERIODICIDADE_CHOICES = [
        ("nenhuma", _("Nenhuma")),
        ("mensal", _("Mensal")),
        ("anual", _("Anual")),
    ]

    categoria = models.ForeignKey(
        CategoriaAuxiliar, on_delete=models.CASCADE, related_name="itens", verbose_name=_("Categoria")
    )
    nome = models.CharField(max_length=100, verbose_name=_("Nome"))
    slug = models.SlugField(max_length=120, verbose_name=_("Slug"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    # Campo legado para compatibilidade; será gradualmente substituído por 'targets'
    alvo = models.CharField(max_length=20, choices=ALVOS, default="outro", verbose_name=_("Alvo"))
    # Novo: seleção múltipla de alvos
    targets = models.ManyToManyField("AlvoAplicacao", blank=True, related_name="itens", verbose_name=_("Aplicar em"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    ordem = models.PositiveIntegerField(default=0, verbose_name=_("Ordem"))
    config = JSONField(default=dict, blank=True, verbose_name=_("Configuração (JSON)"))
    # Novos campos: versionamento e periodicidade
    versionavel = models.BooleanField(default=False, verbose_name=_("Versionável"))
    periodicidade = models.CharField(
        max_length=10, choices=PERIODICIDADE_CHOICES, default="nenhuma", verbose_name=_("Periodicidade")
    )

    class Meta:
        verbose_name = _("Item Auxiliar")
        verbose_name_plural = _("Itens Auxiliares")
        ordering = ["categoria__nome", "ordem", "nome"]
        unique_together = (("categoria", "slug"),)

    def __str__(self):
        return f"{self.nome} ({self.categoria.nome})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)

    @property
    def alvos_display(self):
        nomes = list(self.targets.values_list("nome", flat=True))
        if nomes:
            return ", ".join(nomes)
        # fallback ao campo legado
        try:
            return dict(self.ALVOS).get(self.alvo, "")
        except Exception:
            return ""
