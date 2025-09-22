# fornecedores/models.py (VERSÃO FINAL "DE PONTA" E COMPLETA)

import os
import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from cadastros_gerais.models import ItemAuxiliar
from core.models import Tenant


def fornecedor_logo_path(instance, filename):
    ext = filename.split(".")[-1]
    tenant_id_str = str(instance.tenant.id) if instance.tenant else "sem_tenant"
    unique_filename = f"{instance.pk or uuid.uuid4()}.{ext}"
    return os.path.join("tenants", tenant_id_str, "fornecedores_logos", unique_filename)


class CategoriaFornecedor(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="categorias_fornecedores")
    nome = models.CharField(max_length=100, verbose_name=_("Nome da Categoria"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))

    class Meta:
        verbose_name = _("Categoria de Fornecedor")
        verbose_name_plural = _("Categorias de Fornecedores")
        unique_together = ("tenant", "nome")

    def __str__(self):
        return self.nome


class Fornecedor(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, verbose_name=_("Empresa (Tenant)"), related_name="fornecedores"
    )

    TIPO_CHOICES = (("PJ", _("Pessoa Jurídica")), ("PF", _("Pessoa Física")))
    tipo_pessoa = models.CharField(max_length=2, choices=TIPO_CHOICES, default="PJ", verbose_name=_("Tipo de Pessoa"))

    TIPO_FORNECIMENTO_CHOICES = (("PRODUTOS", _("Produtos")), ("SERVICOS", _("Serviços")), ("AMBOS", _("Ambos")))
    tipo_fornecimento = models.CharField(
        max_length=10, choices=TIPO_FORNECIMENTO_CHOICES, blank=True, null=True, verbose_name=_("Tipo de Fornecimento")
    )

    STATUS_CHOICES = (("active", _("Ativo")), ("inactive", _("Inativo")), ("suspended", _("Suspenso")))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", verbose_name=_("Status"))

    HOMOLOGACAO_CHOICES = (("aprovado", _("Aprovado")), ("pendente", _("Pendente")), ("reprovado", _("Reprovado")))
    status_homologacao = models.CharField(
        max_length=10, choices=HOMOLOGACAO_CHOICES, default="pendente", verbose_name=_("Status de Homologação")
    )

    # Portal de Fornecedor
    portal_ativo = models.BooleanField(
        default=False, verbose_name=_("Portal Ativo"), help_text=_("Permite acesso ao portal do fornecedor")
    )
    data_ativacao_portal = models.DateTimeField(null=True, blank=True, verbose_name=_("Data de Ativação do Portal"))

    logo = models.ImageField(upload_to=fornecedor_logo_path, null=True, blank=True, verbose_name=_("Logo / Imagem"))
    categoria = models.ForeignKey(
        CategoriaFornecedor, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Categoria")
    )
    avaliacao = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        verbose_name=_("Avaliação (1-5)"),
    )
    condicoes_pagamento = models.TextField(blank=True, null=True, verbose_name=_("Condições Padrão de Pagamento"))
    # Novos campos de configuração/comercial
    linhas_fornecidas = models.ManyToManyField(
        ItemAuxiliar, blank=True, related_name="fornecedores", verbose_name=_("Linhas/Categorias Fornecidas")
    )
    regioes_atendidas = models.TextField(blank=True, null=True, verbose_name=_("Regiões Atendidas (UFs/Cidades)"))
    prazo_pagamento_dias = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name=_("Prazo de Pagamento Padrão (dias)")
    )
    pedido_minimo = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True, verbose_name=_("Pedido Mínimo (valor)")
    )
    prazo_medio_entrega_dias = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name=_("Prazo Médio de Entrega (dias)")
    )

    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name=_("Data de Cadastro"))
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações Gerais"))

    class Meta:
        verbose_name = _("Fornecedor")
        verbose_name_plural = _("Fornecedores")
        ordering = ["-id"]

    def __str__(self):
        if hasattr(self, "pessoajuridica") and self.pessoajuridica.nome_fantasia:
            return self.pessoajuridica.nome_fantasia
        elif hasattr(self, "pessoajuridica"):
            return self.pessoajuridica.razao_social
        elif hasattr(self, "pessoafisica"):
            return self.pessoafisica.nome_completo
        return f"Fornecedor ID {self.id}"

    def get_absolute_url(self):
        return reverse("fornecedores:fornecedores_detail", kwargs={"pk": self.pk})

    @property
    def nome_fantasia(self):
        """Retorna nome fantasia ou razão social para PJ, nome completo para PF."""
        if hasattr(self, "pessoajuridica") and self.pessoajuridica.nome_fantasia:
            return self.pessoajuridica.nome_fantasia
        elif hasattr(self, "pessoajuridica"):
            return self.pessoajuridica.razao_social
        elif hasattr(self, "pessoafisica"):
            return self.pessoafisica.nome_completo
        return f"Fornecedor ID {self.id}"

    def pode_acessar_portal(self):
        """Verifica se o fornecedor pode acessar o portal."""
        return self.status == "active" and self.status_homologacao == "aprovado" and self.portal_ativo

    def ativar_portal(self, usuario=None):
        """Ativa o portal do fornecedor."""
        from django.utils import timezone

        self.portal_ativo = True
        self.data_ativacao_portal = timezone.now()
        self.save(update_fields=["portal_ativo", "data_ativacao_portal"])

    # -----------------------------
    # Compatibilidade Legada
    # -----------------------------
    def __init__(self, *args, **kwargs):
        # Se vier com args posicionais é uma instância carregada do banco (from_db); pular compat.
        if args and not kwargs:
            super().__init__(*args, **kwargs)
            return
        # Captura campos legados usados em criação via kwargs
        self._legacy_nome_fantasia = kwargs.pop("nome_fantasia", None)
        self._legacy_razao_social = kwargs.pop("razao_social", None)
        self._legacy_cnpj = kwargs.pop("cnpj", None)
        self._legacy_cpf = kwargs.pop("cpf", None)
        tipo_pessoa = kwargs.pop("tipo_pessoa", None)
        if ("tenant" not in kwargs or kwargs.get("tenant") is None) and not args:
            try:
                from core.models import Tenant as _Tenant

                default_tenant = _Tenant.objects.first()
                if not default_tenant:
                    default_tenant = _Tenant.objects.create(name="Default", subdomain="default")
                kwargs["tenant"] = default_tenant
            except Exception:
                pass
        if tipo_pessoa and "tipo_pessoa" not in kwargs:
            kwargs["tipo_pessoa"] = tipo_pessoa
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        # Após salvar, criar registro PF/PJ auxiliar se informado via kwargs legados
        if creating:
            try:
                if (
                    self.tipo_pessoa == "PJ"
                    and not hasattr(self, "pessoajuridica")
                    and (self._legacy_razao_social or self._legacy_nome_fantasia or self._legacy_cnpj)
                ):
                    FornecedorPJ.objects.create(
                        fornecedor=self,
                        razao_social=self._legacy_razao_social or self._legacy_nome_fantasia or f"Fornecedor {self.pk}",
                        nome_fantasia=self._legacy_nome_fantasia
                        or self._legacy_razao_social
                        or f"Fornecedor {self.pk}",
                        cnpj=self._legacy_cnpj or "00.000.000/0000-00",
                    )
                if (
                    self.tipo_pessoa == "PF"
                    and not hasattr(self, "pessoafisica")
                    and (self._legacy_nome_fantasia or self._legacy_razao_social or self._legacy_cpf)
                ):
                    FornecedorPF.objects.create(
                        fornecedor=self,
                        nome_completo=self._legacy_nome_fantasia
                        or self._legacy_razao_social
                        or f"Fornecedor {self.pk}",
                        cpf=self._legacy_cpf or "000.000.000-00",
                    )
            finally:
                self._legacy_nome_fantasia = None
                self._legacy_razao_social = None
                self._legacy_cnpj = None
                self._legacy_cpf = None


class FornecedorPJ(models.Model):
    fornecedor = models.OneToOneField(
        Fornecedor, on_delete=models.CASCADE, primary_key=True, related_name="pessoajuridica"
    )
    razao_social = models.CharField(max_length=255, verbose_name=_("Razão Social"))
    nome_fantasia = models.CharField(max_length=255, verbose_name=_("Nome Fantasia"))
    cnpj = models.CharField(max_length=18, verbose_name=_("CNPJ"))
    inscricao_estadual = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Inscrição Estadual"))

    # --- CAMPOS ADICIONADOS PARA CORRIGIR O FieldError ---
    inscricao_municipal = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Inscrição Municipal"))
    data_fundacao = models.DateField(blank=True, null=True, verbose_name=_("Data de Fundação"))
    data_abertura = models.DateField(blank=True, null=True, verbose_name=_("Data de Abertura"))
    porte_empresa = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Porte da Empresa"))
    ramo_atividade = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Ramo de Atividade"))
    cnae_principal = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("CNAE Principal"))
    cnae_secundarios = models.TextField(blank=True, null=True, verbose_name=_("CNAEs Secundários"))
    website = models.URLField(blank=True, null=True, verbose_name=_("Website"))
    redes_sociais = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Redes Sociais"))
    nome_responsavel_financeiro = models.CharField(
        max_length=150, blank=True, null=True, verbose_name=_("Responsável Financeiro")
    )
    nome_responsavel_comercial = models.CharField(
        max_length=150, blank=True, null=True, verbose_name=_("Responsável Comercial")
    )
    nome_responsavel_tecnico = models.CharField(
        max_length=150, blank=True, null=True, verbose_name=_("Responsável Técnico")
    )


class FornecedorPF(models.Model):
    fornecedor = models.OneToOneField(
        Fornecedor, on_delete=models.CASCADE, primary_key=True, related_name="pessoafisica"
    )
    nome_completo = models.CharField(max_length=255, verbose_name=_("Nome Completo"))
    cpf = models.CharField(max_length=14, verbose_name=_("CPF"))

    # --- CAMPOS ADICIONADOS PARA CORRIGIR O FieldError ---
    rg = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("RG"))
    data_nascimento = models.DateField(blank=True, null=True, verbose_name=_("Data de Nascimento"))
    sexo = models.CharField(max_length=10, blank=True, null=True, verbose_name=_("Sexo"))
    naturalidade = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Naturalidade"))
    nacionalidade = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Nacionalidade"))
    nome_mae = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Nome da Mãe"))
    nome_pai = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Nome do Pai"))
    estado_civil = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Estado Civil"))
    profissao = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Profissão"))


class ContatoFornecedor(models.Model):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name="contatos")
    nome = models.CharField(max_length=100, verbose_name=_("Nome do Contato"))
    email = models.EmailField(blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    cargo = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Cargo"))


class EnderecoFornecedor(models.Model):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name="enderecos")
    logradouro = models.CharField(max_length=255)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=100, blank=True, null=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2, verbose_name=_("UF"))
    cep = models.CharField(max_length=9, verbose_name=_("CEP"))


class DadosBancariosFornecedor(models.Model):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name="dados_bancarios")
    banco = models.CharField(max_length=100, verbose_name=_("Banco"))
    agencia = models.CharField(max_length=20, verbose_name=_("Agência"))
    conta = models.CharField(max_length=20, verbose_name=_("Conta Corrente/Poupança"))
    tipo_chave_pix = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Tipo de Chave PIX"))
    chave_pix = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Chave PIX"))


# -------------------------------
# Documentos (Fase 1 - Versionado)
# -------------------------------


def fornecedor_documento_path(instance, filename):
    ext = filename.split(".")[-1].lower()
    fornecedor_id = instance.documento.fornecedor_id if getattr(instance, "documento", None) else None
    tipo_slug = (
        instance.documento.tipo.slug if getattr(instance, "documento", None) and instance.documento.tipo else "tipo"
    )
    competencia = (instance.competencia or "geral").replace("/", "-")
    return os.path.join(
        "tenant_documentos",
        "fornecedor",
        str(fornecedor_id or "novo"),
        tipo_slug,
        competencia,
        f"v{instance.versao}.{ext}",
    )


class FornecedorDocumento(models.Model):
    PERIODICIDADE_CHOICES = [
        ("nenhuma", _("Não se aplica")),
        ("mensal", _("Mensal")),
        ("anual", _("Anual")),
        ("eventual", _("Eventual")),
        ("personalizada", _("Personalizada")),
    ]
    EXIGENCIA_CHOICES = [
        ("obrigatorio", _("Obrigatório")),
        ("recomendado", _("Recomendado")),
        ("opcional", _("Opcional")),
    ]
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.CASCADE, related_name="documentos", verbose_name=_("Fornecedor")
    )
    tipo = models.ForeignKey(
        ItemAuxiliar,
        on_delete=models.PROTECT,
        related_name="documentos_fornecedor",
        verbose_name=_("Tipo de Documento"),
    )
    periodicidade = models.CharField(
        max_length=20, choices=PERIODICIDADE_CHOICES, default="nenhuma", verbose_name=_("Periodicidade")
    )
    exigencia = models.CharField(
        max_length=20, choices=EXIGENCIA_CHOICES, default="obrigatorio", verbose_name=_("Exigência")
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Documento de Fornecedor")
        verbose_name_plural = _("Documentos de Fornecedor")
        unique_together = (("fornecedor", "tipo"),)
        indexes = [
            models.Index(fields=["fornecedor", "tipo"]),
        ]

    def __str__(self):
        try:
            return f"{self.fornecedor} - {self.tipo.nome}"
        except Exception:
            return f"Documento Fornecedor #{self.pk}"


class FornecedorDocumentoVersao(models.Model):
    STATUS_CHOICES = (
        ("pendente", _("Pendente")),
        ("enviado", _("Enviado")),
        ("aprovado", _("Aprovado")),
        ("reprovado", _("Reprovado")),
        ("vencido", _("Vencido")),
    )

    documento = models.ForeignKey(
        FornecedorDocumento, on_delete=models.CASCADE, related_name="versoes", verbose_name=_("Documento")
    )
    versao = models.PositiveIntegerField(verbose_name=_("Versão"))
    arquivo = models.FileField(upload_to=fornecedor_documento_path, verbose_name=_("Arquivo"))
    enviado_em = models.DateTimeField(auto_now_add=True, verbose_name=_("Enviado em"))
    usuario = models.ForeignKey(
        "core.CustomUser", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Usuário")
    )
    observacao = models.TextField(blank=True, null=True, verbose_name=_("Observação"))
    competencia = models.CharField(max_length=7, blank=True, null=True, verbose_name=_("Competência (MM/AAAA)"))
    validade_data = models.DateField(blank=True, null=True, verbose_name=_("Validade"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="enviado", verbose_name=_("Status"))

    class Meta:
        verbose_name = _("Versão de Documento de Fornecedor")
        verbose_name_plural = _("Versões de Documentos de Fornecedor")
        unique_together = (("documento", "competencia", "versao"),)
        indexes = [
            models.Index(fields=["documento", "versao"]),
            models.Index(fields=["competencia"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-enviado_em", "-versao"]

    def __str__(self):
        comp = f" ({self.competencia})" if self.competencia else ""
        return f"{self.documento} - v{self.versao}{comp}"
