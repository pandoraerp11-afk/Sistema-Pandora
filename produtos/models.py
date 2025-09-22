# produtos/models.py
import os
import uuid

from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def produto_imagem_path(instance, filename):
    """Gera um caminho personalizado para as imagens de produtos"""
    ext = filename.split(".")[-1]
    filename = f"{slugify(instance.produto.nome)}_{uuid.uuid4()}.{ext}"
    return os.path.join("produtos/imagens", filename)


class Categoria(models.Model):
    """Categoria hierárquica (árvore simples) para produtos.

    Campo parent opcional permite construir árvore; materialized path pode ser
    adicionado futuramente (por ora somente parent + índice facilita queries recursivas).
    """

    nome = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="filhas")
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))

    class Meta:
        verbose_name = "Categoria de Produto"
        verbose_name_plural = "Categorias de Produtos"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["parent", "nome"]),
        ]

    def __str__(self):
        return self.nome


class ProdutoManager(models.Manager):
    def create(self, **kwargs):
        # Converter valores legacy string antes de criar
        from django.apps import apps

        try:
            CategoriaModel = apps.get_model("produtos", "Categoria")
        except LookupError:
            CategoriaModel = None
        try:
            UnidadeMedidaModel = apps.get_model("cadastros_gerais", "UnidadeMedida")
        except LookupError:
            UnidadeMedidaModel = None

        # Categoria string
        cat = kwargs.get("categoria")
        if isinstance(cat, str) and CategoriaModel:
            cat_obj, _ = CategoriaModel.objects.get_or_create(nome=cat)
            kwargs["categoria"] = cat_obj

        # Unidade string
        unidade_val = kwargs.get("unidade")
        if isinstance(unidade_val, str) and UnidadeMedidaModel:
            un_obj, _ = UnidadeMedidaModel.objects.get_or_create(simbolo=unidade_val, defaults={"nome": unidade_val})
            kwargs["unidade"] = un_obj
        # Se UnidadeMedidaModel não estiver disponível, mantemos a string para __init__ capturar
        return super().create(**kwargs)


class Produto(models.Model):
    class TipoCusto(models.TextChoices):
        PRECO_MEDIO = "preco_medio", _("Preço Médio Ponderado")
        PEPS = "peps", _("PEPS (FIFO)")
        CUSTO_PADRAO = "custo_padrao", _("Custo Padrão")
        ESPECIFICO = "especifico", _("Custo Específico")

    nome = models.CharField(max_length=200, verbose_name=_("Nome do Produto"))
    # SKU canônico (auto gerado se ausente). Mantemos campo codigo legado para compatibilidade.
    sku = models.CharField(max_length=40, unique=True, null=True, blank=True, verbose_name=_("SKU"))
    codigo = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name=_("Código Legado"))
    codigo_barras = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Código de Barras"))
    categoria = models.ForeignKey("produtos.Categoria", on_delete=models.PROTECT, verbose_name=_("Categoria"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    especificacoes_tecnicas = models.TextField(blank=True, null=True, verbose_name=_("Especificações Técnicas"))

    # --- CORREÇÃO APLICADA AQUI ---
    # Alterado de CharField para ForeignKey para o modelo central UnidadeMedida.
    unidade = models.ForeignKey(
        "cadastros_gerais.UnidadeMedida",
        on_delete=models.PROTECT,
        verbose_name=_("Unidade de Medida"),
        null=True,  # Permitir nulo temporariamente ou para produtos sem unidade definida
        blank=True,
    )

    # Tipo de produto para variantes
    class TipoProduto(models.TextChoices):
        SIMPLES = "SIMPLES", _("Simples")
        VARIANTE_PAI = "VARIANTE_PAI", _("Variante (Pai)")
        VARIANTE = "VARIANTE", _("Variante")

    tipo = models.CharField(max_length=15, choices=TipoProduto.choices, default=TipoProduto.SIMPLES)
    produto_pai = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="variantes")

    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_("Preço Unitário"))
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Preço de Custo"), default=0)
    tipo_custo = models.CharField(
        max_length=20, choices=TipoCusto.choices, default=TipoCusto.PRECO_MEDIO, verbose_name=_("Tipo de Custo")
    )
    margem_lucro = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_("Margem de Lucro (%)"), default=0)
    estoque_atual = models.PositiveIntegerField(default=0, verbose_name=_("Quantidade em Estoque"))
    estoque_minimo = models.PositiveIntegerField(default=0, verbose_name=_("Estoque Mínimo"))
    estoque_maximo = models.PositiveIntegerField(default=0, verbose_name=_("Estoque Máximo"))
    controla_estoque = models.BooleanField(default=True, verbose_name=_("Controla Estoque"))
    controla_lote = models.BooleanField(default=False, verbose_name=_("Controla por Lote"))
    controla_numero_serie = models.BooleanField(default=False, verbose_name=_("Controla por Nº de Série"))
    imagem_principal = models.ImageField(
        upload_to="produtos/principais/", blank=True, null=True, verbose_name=_("Imagem Principal")
    )
    ncm = models.CharField(max_length=10, blank=True, null=True, verbose_name=_("NCM"))
    peso = models.DecimalField(max_digits=8, decimal_places=3, blank=True, null=True, verbose_name=_("Peso (kg)"))
    altura = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, verbose_name=_("Altura (cm)"))
    largura = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, verbose_name=_("Largura (cm)"))
    profundidade = models.DecimalField(
        max_digits=8, decimal_places=2, blank=True, null=True, verbose_name=_("Profundidade (cm)")
    )
    fabricante = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Fabricante"))
    marca = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Marca"))
    modelo = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Modelo"))
    garantia = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Garantia"))

    # Status de ciclo de vida
    class StatusCiclo(models.TextChoices):
        ATIVO = "ATIVO", _("Ativo")
        SUSPENSO = "SUSPENSO", _("Suspenso")
        DESCONTINUADO = "DESCONTINUADO", _("Descontinuado")

    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))  # manter flag legado
    status_ciclo = models.CharField(max_length=15, choices=StatusCiclo.choices, default=StatusCiclo.ATIVO)
    destaque = models.BooleanField(default=False, verbose_name=_("Produto em Destaque"))
    data_cadastro = models.DateField(auto_now_add=True, verbose_name=_("Data de Cadastro"))
    ultima_atualizacao = models.DateTimeField(auto_now=True, verbose_name=_("Última Atualização"))

    objects = ProdutoManager()

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["nome"]

    def __str__(self):
        return self.sku or self.nome

    def get_absolute_url(self):
        return reverse("produtos:produto_detail", args=[str(self.id)])

    # --- Compatibilidade legado: permitir atribuir categoria/unidade via string ---
    def set_categoria_legacy(self, value):
        from produtos.models import Categoria

        if isinstance(value, Categoria):
            self.categoria = value
        elif isinstance(value, str):
            cat_obj, _ = Categoria.objects.get_or_create(nome=value)
            self.categoria = cat_obj
        else:
            raise ValueError("Categoria inválida")

    def set_unidade_legacy(self, value):
        try:
            from cadastros_gerais.models import UnidadeMedida
        except Exception:
            UnidadeMedida = None
        if UnidadeMedida and isinstance(value, UnidadeMedida):
            self.unidade = value
        elif isinstance(value, str):
            # Tentativa de buscar por sigla se modelo existir
            if UnidadeMedida:
                # Primeiro tenta simbolo; fallback para campo sigla legado se existir
                created_obj = None
                try:
                    obj, _ = UnidadeMedida.objects.get_or_create(simbolo=value, defaults={"nome": value})
                    created_obj = obj
                except Exception:
                    # Fallback: tentar atributo 'sigla'
                    try:
                        obj, _ = UnidadeMedida.objects.get_or_create(
                            sigla=value, defaults={"nome": value, "simbolo": value}
                        )  # type: ignore
                        created_obj = obj
                    except Exception:
                        created_obj = None
                if created_obj:
                    self.unidade = created_obj
            else:
                # fallback: ignorar até migração completa
                pass
        elif value is None:
            self.unidade = None
        else:
            raise ValueError("Unidade inválida")

    @property
    def unidade_display(self):
        """Retorna símbolo da unidade (compat teste antigo que compara string)."""
        try:
            return getattr(self.unidade, "simbolo", None)
        except Exception:
            return None

    def __init__(self, *args, **kwargs):
        self._categoria_legacy_name = None
        self._unidade_legacy_sigla = None
        if "categoria" in kwargs and isinstance(kwargs["categoria"], str):
            self._categoria_legacy_name = kwargs.pop("categoria")
        if "unidade" in kwargs and isinstance(kwargs["unidade"], str):
            self._unidade_legacy_sigla = kwargs.pop("unidade")
        super().__init__(*args, **kwargs)

    def calcular_preco_venda(self):
        """Calcula o preço de venda baseado no custo e margem de lucro"""
        if self.preco_custo > 0 and self.margem_lucro > 0:
            return self.preco_custo * (1 + (self.margem_lucro / 100))
        return self.preco_unitario

    def save(self, *args, **kwargs):
        creating = self.pk is None
        # Converter valores capturados no __init__ antes do primeiro save
        if self._categoria_legacy_name and not self.categoria_id:
            self.set_categoria_legacy(self._categoria_legacy_name)
            self._categoria_legacy_name = None
        if self._unidade_legacy_sigla and not self.unidade_id:
            # Só limpar flag se efetivamente atribuída
            prev_unidade = self.unidade_id
            self.set_unidade_legacy(self._unidade_legacy_sigla)
            if self.unidade_id != prev_unidade and self.unidade_id is not None:
                self._unidade_legacy_sigla = None
        # Compat adicional: se atributos ainda são string
        if isinstance(getattr(self, "categoria", None), str):
            self.set_categoria_legacy(self.categoria)
        if isinstance(getattr(self, "unidade", None), str):
            self.set_unidade_legacy(self.unidade)
        super().save(*args, **kwargs)
        # Gerar SKU pós criação se não definido (usa ID para sequência determinística)
        if (creating and not self.sku) or (self.sku is None):
            self.sku = f"PRD-{self.id:06d}"
            Produto.objects.filter(pk=self.pk).update(sku=self.sku)
        # Fallback final: criar unidade se ainda não setada e havia legacy sigla
        if not self.unidade_id and hasattr(self, "_unidade_legacy_sigla") and self._unidade_legacy_sigla:
            try:
                from cadastros_gerais.models import UnidadeMedida

                un_obj, _ = UnidadeMedida.objects.get_or_create(
                    simbolo=self._unidade_legacy_sigla, defaults={"nome": self._unidade_legacy_sigla}
                )
                self.unidade = un_obj
                Produto.objects.filter(pk=self.pk).update(unidade=un_obj)
            except Exception:
                pass


class ProdutoImagem(models.Model):
    """Modelo para armazenar múltiplas imagens de um produto"""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="imagens")
    imagem = models.ImageField(upload_to=produto_imagem_path, verbose_name=_("Imagem"))
    titulo = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Título"))
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem de Exibição")
    data_upload = models.DateTimeField(auto_now_add=True, verbose_name="Data de Upload")

    class Meta:
        verbose_name = "Imagem do Produto"
        verbose_name_plural = "Imagens do Produto"
        ordering = ["ordem", "data_upload"]

    def __str__(self):
        return f"Imagem {self.ordem} - {self.produto.nome}"


class ProdutoVariacao(models.Model):
    """Modelo para armazenar variações de um produto (tamanho, cor, etc.)"""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="variacoes")
    nome = models.CharField(max_length=100, verbose_name="Nome da Variação")
    descricao = models.CharField(max_length=200, blank=True, null=True, verbose_name="Descrição")
    preco_adicional = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Preço Adicional")
    estoque = models.PositiveIntegerField(default=0, verbose_name="Estoque")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        verbose_name = "Variação do Produto"
        verbose_name_plural = "Variações do Produto"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.produto.nome} - {self.nome}"


class ProdutoDocumento(models.Model):
    """Modelo para armazenar documentos relacionados ao produto (manuais, certificados, etc.)"""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="documentos")
    titulo = models.CharField(max_length=100, verbose_name="Título")
    arquivo = models.FileField(upload_to="produtos/documentos/", verbose_name="Arquivo")
    tipo = models.CharField(
        max_length=50,
        choices=[
            ("manual", "Manual"),
            ("certificado", "Certificado"),
            ("ficha_tecnica", "Ficha Técnica"),
            ("outro", "Outro"),
        ],
        default="outro",
        verbose_name="Tipo de Documento",
    )
    data_upload = models.DateTimeField(auto_now_add=True, verbose_name="Data de Upload")

    class Meta:
        verbose_name = "Documento do Produto"
        verbose_name_plural = "Documentos do Produto"
        ordering = ["titulo"]

    def __str__(self):
        return f"{self.titulo} - {self.produto.nome}"


# ----------------- Atributos Dinâmicos & BOM (Modernização) -----------------


class ProdutoAtributoDef(models.Model):
    TIPO_CHOICES = [
        ("texto", "Texto"),
        ("num", "Numérico"),
        ("bool", "Booleano"),
        ("lista", "Lista"),
        ("json", "JSON"),
    ]
    nome = models.CharField(max_length=80, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="texto")
    unidade = models.ForeignKey("cadastros_gerais.UnidadeMedida", on_delete=models.SET_NULL, null=True, blank=True)
    obrigatorio = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Definição Atributo Produto"
        verbose_name_plural = "Definições Atributos Produto"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class ProdutoAtributoValor(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="atributos_valores")
    atributo_def = models.ForeignKey(ProdutoAtributoDef, on_delete=models.CASCADE, related_name="valores")
    valor_textual = models.CharField(max_length=255, null=True, blank=True)
    valor_num = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    valor_json = models.JSONField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Valor Atributo Produto"
        verbose_name_plural = "Valores Atributos Produto"
        unique_together = ("produto", "atributo_def")
        indexes = [
            models.Index(fields=["produto", "atributo_def"], name="prod_attr_prod_def_idx"),
        ]

    def __str__(self):
        return f"{self.produto_id}:{self.atributo_def_id}"


class ProdutoBOMItem(models.Model):
    produto_pai = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="bom_itens")
    componente = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="como_componente")
    quantidade_por_unidade = models.DecimalField(max_digits=14, decimal_places=6)
    perda_perc = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Item BOM"
        verbose_name_plural = "Itens BOM"
        unique_together = ("produto_pai", "componente")
        indexes = [
            models.Index(fields=["produto_pai"], name="bom_prod_pai_idx"),
        ]

    def __str__(self):
        return f"BOM {self.produto_pai_id}->{self.componente_id}"
