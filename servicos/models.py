# servicos/models.py

import os
import uuid
from decimal import Decimal

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from clientes.models import Cliente
from core.models import Tenant

# Importações necessárias e corretas
from fornecedores.models import Fornecedor


def servico_imagem_path(instance, filename):
    ext = filename.split(".")[-1]
    servico_slug = slugify(instance.servico.nome_servico) if instance.servico else "servico_desconhecido"
    unique_id = uuid.uuid4()
    filename = f"{servico_slug}_{unique_id}.{ext}"
    return os.path.join("servicos", "imagens", filename)


def servico_documento_path(instance, filename):
    ext = filename.split(".")[-1]
    servico_slug = slugify(instance.servico.nome_servico) if instance.servico else "servico_desconhecido"
    unique_id = uuid.uuid4()
    filename = f"{servico_slug}_doc_{unique_id}.{ext}"
    return os.path.join("servicos", "documentos", filename)


class CategoriaServico(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name=_("Nome"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    slug = models.SlugField(max_length=120, unique=True, blank=True, verbose_name=_("Slug (URL Amigável)"))

    class Meta:
        verbose_name = _("Categoria de Serviço")
        verbose_name_plural = _("Categorias de Serviços")
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        original_slug = self.slug
        counter = 1
        while CategoriaServico.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            self.slug = f"{original_slug}-{counter}"
            counter += 1
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("servicos:categoria_list")


class RegraCobranca(models.Model):
    nome = models.CharField(max_length=100, verbose_name=_("Nome da Regra"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    unidade_medida = models.ForeignKey(
        "cadastros_gerais.UnidadeMedida",
        on_delete=models.PROTECT,
        verbose_name=_("Unidade de Medida"),
        related_name="regras_cobranca",
    )
    valor_base = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Valor Base"))
    valor_minimo = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name=_("Valor Mínimo (Opcional)"), blank=True, null=True
    )
    incremento = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name=_("Incremento Padrão"))
    taxa_adicional = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name=_("Taxa Adicional (%)"), blank=True, null=True
    )

    TIPO_CALCULO_CHOICES = [
        ("fixo", _("Valor Fixo")),
        ("unidade", _("Por Unidade (Baseado na Unidade de Medida)")),
        ("personalizado", _("Fórmula Personalizada (Avançado)")),
    ]
    tipo_calculo = models.CharField(
        max_length=20, choices=TIPO_CALCULO_CHOICES, default="unidade", verbose_name=_("Tipo de Cálculo")
    )
    formula_personalizada = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Fórmula Personalizada"),
        help_text=_("Usar 'Q' para quantidade. Ex: (Q * valor_base) + (Q // 10 * taxa_adicional)"),
    )
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))

    class Meta:
        verbose_name = _("Regra de Cobrança")
        verbose_name_plural = _("Regras de Cobrança")
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_calculo_display()})"

    def calcular_valor(self, quantidade=1):
        if not isinstance(quantidade, (int, float, Decimal)):
            try:
                quantidade = Decimal(str(quantidade).replace(",", "."))
            except (ValueError, TypeError):
                quantidade = Decimal("1")

        quantidade = Decimal(quantidade)
        valor_calculado = self.valor_base * quantidade

        if self.tipo_calculo == "fixo":
            valor_calculado = self.valor_base
        elif self.tipo_calculo == "personalizado" and self.formula_personalizada:
            try:
                valor_calculado = eval(
                    self.formula_personalizada,
                    {
                        "Q": quantidade,
                        "valor_base": self.valor_base,
                        "taxa_adicional": self.taxa_adicional or Decimal("0"),
                    },
                )
            except Exception:
                valor_calculado = self.valor_base * quantidade

        if self.taxa_adicional and self.taxa_adicional > 0:
            valor_calculado += valor_calculado * (self.taxa_adicional / Decimal("100"))

        if self.valor_minimo and valor_calculado < self.valor_minimo:
            valor_calculado = self.valor_minimo

        return round(valor_calculado, 2)


class Servico(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="servicos",
        verbose_name=_("Empresa (Tenant)"),
        null=True,  # Temporariamente nulo para a migração
        blank=True,
    )
    is_clinical = models.BooleanField(
        default=False,
        verbose_name=_("É um Serviço Clínico?"),
        help_text=_("Marque se este serviço tiver características de saúde/estética."),
    )

    TIPO_CHOICES = [
        ("OFERTADO", _("Serviço Ofertado (Venda)")),
        ("RECEBIDO", _("Serviço Contratado (Compra)")),
    ]
    tipo_servico = models.CharField(
        max_length=10, choices=TIPO_CHOICES, default="OFERTADO", verbose_name=_("Tipo de Serviço")
    )

    nome_servico = models.CharField(max_length=200, verbose_name=_("Nome do Serviço"))
    slug = models.SlugField(max_length=220, unique=True, blank=True, verbose_name=_("Slug (URL Amigável)"))
    codigo = models.CharField(
        max_length=50, blank=True, null=True, unique=True, verbose_name=_("Código do Serviço"), editable=False
    )
    descricao = models.TextField(verbose_name=_("Descrição Completa"))
    descricao_curta = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Descrição Curta (Resumo)")
    )
    categoria = models.ForeignKey(
        CategoriaServico, on_delete=models.PROTECT, verbose_name=_("Categoria"), related_name="servicos"
    )

    preco_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Preço Base (Padrão/Venda)"),
        default=Decimal("0.00"),
        help_text=_(
            "Para 'Serviços Ofertados', este é o seu preço de venda. Para 'Serviços Contratados', este é apenas um valor de referência."
        ),
    )
    regra_cobranca = models.ForeignKey(
        RegraCobranca,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Regra de Cobrança (Padrão/Venda)"),
        related_name="servicos_padrao",
        help_text=_("Regra de cobrança para seus 'Serviços Ofertados'."),
    )

    tempo_estimado = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Tempo Estimado de Execução")
    )
    prazo_entrega = models.PositiveIntegerField(
        blank=True, null=True, verbose_name=_("Prazo de Entrega (em dias úteis)")
    )

    materiais_inclusos = models.TextField(blank=True, null=True, verbose_name=_("Materiais Inclusos"))
    materiais_nao_inclusos = models.TextField(blank=True, null=True, verbose_name=_("Materiais Não Inclusos"))
    requisitos = models.TextField(blank=True, null=True, verbose_name=_("Requisitos para o Cliente"))

    disponivel_online = models.BooleanField(default=True, verbose_name=_("Disponível para Contratação Online"))
    requer_visita_tecnica = models.BooleanField(default=False, verbose_name=_("Requer Visita Técnica Prévia"))
    requer_aprovacao = models.BooleanField(default=False, verbose_name=_("Requer Aprovação de Orçamento Prévio"))

    palavras_chave = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Palavras-chave (SEO)"),
        help_text=_("Separadas por vírgula"),
    )
    destaque = models.BooleanField(default=False, verbose_name=_("Serviço em Destaque"))

    ativo = models.BooleanField(default=True, verbose_name=_("Ativo (Visível no Catálogo)"))
    data_cadastro = models.DateTimeField(default=timezone.now, verbose_name=_("Data de Cadastro"))
    ultima_atualizacao = models.DateTimeField(auto_now=True, verbose_name=_("Última Atualização"))

    imagem_principal = models.ImageField(
        upload_to="servicos/principais/", blank=True, null=True, verbose_name=_("Imagem Principal")
    )

    clientes = models.ManyToManyField(
        Cliente, blank=True, related_name="servicos_ofertados", verbose_name=_("Clientes Associados a este Serviço")
    )

    fornecedores = models.ManyToManyField(
        Fornecedor, through="ServicoFornecedor", related_name="servicos_prestados", verbose_name=_("Fornecedores")
    )

    class Meta:
        verbose_name = _("Serviço (Catálogo)")
        verbose_name_plural = _("Serviços (Catálogo)")
        ordering = ["nome_servico"]

    def __str__(self):
        return f"{self.nome_servico} ({self.get_tipo_servico_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome_servico)
            original_slug = self.slug
            counter = 1
            while Servico.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1

        if not self.codigo:
            prefix = "SOF" if self.tipo_servico == "OFERTADO" else "SCT"
            last_id = Servico.objects.all().order_by("id").last()
            next_id = (last_id.id + 1) if last_id else 1
            self.codigo = f"{prefix}-{next_id:06d}"

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.tipo_servico == "OFERTADO":
            return reverse("servicos:servico_ofertado_detail", args=[self.slug])
        else:
            return reverse("servicos:servico_recebido_detail", args=[self.slug])

    def get_update_url(self):
        if self.tipo_servico == "OFERTADO":
            return reverse("servicos:servico_ofertado_update", args=[self.slug])
        else:
            return reverse("servicos:servico_recebido_update", args=[self.slug])

    def get_delete_url(self):
        if self.tipo_servico == "OFERTADO":
            return reverse("servicos:servico_ofertado_delete", args=[self.slug])
        else:
            return reverse("servicos:servico_recebido_delete", args=[self.slug])

    # NOVO MÉTODO DE AJUDA
    def get_list_url(self):
        if self.tipo_servico == "OFERTADO":
            return reverse("servicos:servico_ofertado_list")
        else:
            return reverse("servicos:servico_recebido_list")

    def calcular_preco(self, quantidade=1):
        if self.regra_cobranca:
            return self.regra_cobranca.calcular_valor(quantidade)
        return self.preco_base

    # -----------------------------
    # Compatibilidade Legada (Procedimento)
    # -----------------------------
    @property
    def nome(self):  # permite templates antigos usarem objeto.nome
        return self.nome_servico

    @property
    def duracao_estimada(self):
        return getattr(getattr(self, "perfil_clinico", None), "duracao_estimada", None)

    @property
    def valor(self):  # alias para preco_base
        return self.preco_base

    @property
    def valor_base(self):  # alguns lugares usavam valor_base
        return self.preco_base

    @property
    def intervalo_minimo_sessoes(self):
        """Compat: acessa do perfil_clinico quando existir."""
        return getattr(getattr(self, "perfil_clinico", None), "intervalo_minimo_sessoes", None)

    @property
    def categoria_nome(self):  # conveniência para templates/relatórios
        try:
            return self.categoria.nome
        except Exception:
            return None


class ServicoClinico(models.Model):
    servico = models.OneToOneField(
        Servico,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="perfil_clinico",
        verbose_name=_("Serviço Base"),
    )
    duracao_estimada = models.DurationField(verbose_name=_("Duração Estimada"))
    requisitos_pre_procedimento = models.TextField(blank=True, null=True)
    contraindicacoes = models.TextField(blank=True, null=True)
    cuidados_pos_procedimento = models.TextField(blank=True, null=True)
    requer_anamnese = models.BooleanField(default=True)
    requer_termo_consentimento = models.BooleanField(default=True)
    permite_fotos_evolucao = models.BooleanField(default=True)
    intervalo_minimo_sessoes = models.PositiveIntegerField(
        default=7, verbose_name=_("Intervalo Mínimo entre Sessões (dias)")
    )

    class Meta:
        verbose_name = _("Perfil Clínico do Serviço")
        verbose_name_plural = _("Perfis Clínicos de Serviços")

    def __str__(self):
        return f"Perfil Clínico de: {self.servico.nome_servico}"


class ServicoFornecedor(models.Model):
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE)

    preco_base_fornecedor = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Preço Base do Fornecedor")
    )
    regra_cobranca_fornecedor = models.ForeignKey(
        RegraCobranca,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Regra de Cobrança do Fornecedor"),
        related_name="servicos_fornecedor",
    )
    codigo_fornecedor = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Código do Serviço no Fornecedor")
    )

    class Meta:
        verbose_name = _("Fornecedor do Serviço")
        verbose_name_plural = _("Fornecedores do Serviço")
        unique_together = ("servico", "fornecedor")
        ordering = ["fornecedor__pessoajuridica__razao_social", "fornecedor__pessoafisica__nome_completo"]

    def __str__(self):
        return f"{str(self.fornecedor)} - {self.servico.nome_servico}"

    def calcular_preco_fornecedor(self, quantidade=1):
        if self.regra_cobranca_fornecedor:
            return self.regra_cobranca_fornecedor.calcular_valor(quantidade)
        return self.preco_base_fornecedor


class ServicoImagem(models.Model):
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="imagens_adicionais")
    imagem = models.ImageField(upload_to=servico_imagem_path, verbose_name=_("Imagem"))
    titulo = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Título (Opcional)"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição (Opcional)"))
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name=_("Ordem de Exibição"))
    data_upload = models.DateTimeField(auto_now_add=True, verbose_name=_("Data de Upload"))

    class Meta:
        verbose_name = _("Imagem Adicional do Serviço")
        verbose_name_plural = _("Imagens Adicionais do Serviço")
        ordering = ["servico", "ordem", "data_upload"]

    def __str__(self):
        return self.titulo or f"Imagem {self.ordem} - {self.servico.nome_servico}"


class ServicoDocumento(models.Model):
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="documentos_anexos")
    titulo = models.CharField(max_length=100, verbose_name=_("Título do Documento"))
    arquivo = models.FileField(upload_to=servico_documento_path, verbose_name=_("Arquivo"))
    TIPO_DOCUMENTO_CHOICES = [
        ("contrato", _("Contrato Modelo")),
        ("termo", _("Termo de Serviço")),
        ("manual", _("Manual de Uso/Instruções")),
        ("certificado", _("Certificado de Garantia")),
        ("portfolio", _("Portfólio/Case de Sucesso")),
        ("outro", _("Outro")),
    ]
    tipo = models.CharField(
        max_length=50, choices=TIPO_DOCUMENTO_CHOICES, default="outro", verbose_name=_("Tipo de Documento")
    )
    data_upload = models.DateTimeField(auto_now_add=True, verbose_name=_("Data de Upload"))

    class Meta:
        verbose_name = _("Documento do Serviço")
        verbose_name_plural = _("Documentos do Serviço")
        ordering = ["servico", "titulo"]

    def __str__(self):
        return f"{self.titulo} ({self.get_tipo_display()}) - {self.servico.nome_servico}"

    @property
    def filename(self):
        return os.path.basename(self.arquivo.name) if self.arquivo else ""


class Avaliacao(models.Model):
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="avaliacoes")
    nome_cliente = models.CharField(max_length=100, verbose_name=_("Nome do Cliente"))
    email_cliente = models.EmailField(blank=True, null=True, verbose_name=_("Email do Cliente (Opcional)"))
    NOTA_CHOICES = [(i, str(i)) for i in range(1, 6)]
    nota = models.PositiveSmallIntegerField(choices=NOTA_CHOICES, verbose_name=_("Nota (1 a 5)"))
    comentario = models.TextField(verbose_name=_("Comentário"))
    data_avaliacao = models.DateTimeField(auto_now_add=True, verbose_name=_("Data da Avaliação"))
    aprovado = models.BooleanField(default=False, verbose_name=_("Aprovado para Exibição"))

    class Meta:
        verbose_name = _("Avaliação de Serviço")
        verbose_name_plural = _("Avaliações de Serviços")
        ordering = ["-data_avaliacao"]

    def __str__(self):
        return f"Avaliação de {self.nome_cliente} para {self.servico.nome_servico} - Nota: {self.nota}/5"
