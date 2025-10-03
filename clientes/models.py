"""Modelos do app clientes.

Inclui modelo principal ``Cliente`` e entidades relacionadas (PessoaFisica, PessoaJuridica,
Contato, EnderecoAdicional, AcessoCliente). O modelo ``DocumentoCliente`` permanece apenas
como artefato de transição (dados migrados para o app ``documentos``).

NOTA SOBRE ``null=True`` em campos CharField/TextField (avisos DJ001):
Estes campos vieram de schema legado; remover ``null=True`` exigirá migração e possivelmente
normalização de dados (substituir NULL por string vazia). Será feito em etapa posterior.
"""

from __future__ import annotations

# ruff: noqa: DJ001, I001  (Campos string com null=True mantidos por legado; import sort conflitando)

import uuid
from pathlib import Path
from typing import Any, cast

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from core.models import CustomUser, Tenant

CNPJ_MIN_LENGTH_THRESHOLD = 14  # Limite mínimo para heurística de identificação de CNPJ


def cliente_imagem_path(instance: models.Model, filename: str) -> str:
    """Gerar caminho único para imagem de perfil segregado por tenant.

    A tipagem aceita ``models.Model`` para satisfazer Django/Pyright; internamente
    convertemos para ``Cliente`` via cast.
    """
    cli = cast("Cliente", instance)
    ext = filename.split(".")[-1]
    tenant_id_str = str(cli.tenant.id) if getattr(cli, "tenant", None) else "sem_tenant"
    unique_filename = f"{cli.pk or uuid.uuid4()}.{ext}"
    return str(Path("tenants") / tenant_id_str / "clientes_profile_pics" / unique_filename)


class Cliente(models.Model):
    """Cliente (Pessoa Física ou Jurídica) associado a um tenant.

    Centraliza dados principais, contato e endereço base; detalhes específicos
    ficam nos modelos ``PessoaFisica`` e ``PessoaJuridica``.
    """

    # --- Identificação e Vínculo ---
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        verbose_name=_("Empresa (Tenant)"),
        related_name="clientes",
    )
    codigo_interno = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Código Interno"))
    TIPO_CHOICES = (("PF", _("Pessoa Física")), ("PJ", _("Pessoa Jurídica")))
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES, verbose_name=_("Tipo de Cliente"), default="PF")
    STATUS_CHOICES = (("active", _("Ativo")), ("inactive", _("Inativo")), ("suspended", _("Suspenso")))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", verbose_name=_("Status"))
    # --- Branding e Portal ---
    imagem_perfil = models.ImageField(
        upload_to=cliente_imagem_path,
        null=True,
        blank=True,
        verbose_name=_("Foto do Perfil / Logo"),
    )
    portal_ativo = models.BooleanField(
        default=False,
        verbose_name=_("Portal do Cliente Ativo?"),
        help_text=_("Habilita o acesso do cliente e seus usuários ao portal do sistema."),
    )
    # --- Contato Principal ---
    email = models.EmailField(verbose_name=_("E-mail Principal"), max_length=254, blank=True, null=True)
    telefone = models.CharField(max_length=20, verbose_name=_("Telefone Principal"), blank=True, null=True)
    telefone_secundario = models.CharField(max_length=20, verbose_name=_("Telefone Secundário"), blank=True, null=True)
    # --- Endereço Principal (Estruturado) ---
    cep = models.CharField(max_length=10, verbose_name=_("CEP"), blank=True, null=True)
    logradouro = models.CharField(max_length=255, verbose_name=_("Logradouro"), blank=True, null=True)
    numero = models.CharField(max_length=20, verbose_name=_("Número"), blank=True, null=True)
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Complemento"))
    bairro = models.CharField(max_length=100, verbose_name=_("Bairro"), null=True, blank=True)
    cidade = models.CharField(max_length=100, verbose_name=_("Cidade"), blank=True, null=True)
    estado = models.CharField(max_length=2, verbose_name=_("Estado (UF)"), blank=True, null=True)
    pais = models.CharField(max_length=50, verbose_name=_("País"), blank=True, null=True, default="Brasil")
    # --- Campos de Gestão ---
    data_cadastro = models.DateField(auto_now_add=True, verbose_name=_("Data de Cadastro"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo (Legado)"), editable=False)
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        """Metadados de ordenação e unicidade do Cliente."""

        verbose_name = _("Cliente")
        verbose_name_plural = _("Clientes")
        unique_together = (("tenant", "email"), ("tenant", "codigo_interno"))
        ordering = ("-id",)

    # OBS: Métodos Django model usam assinatura dinâmica (*args, **kwargs) por design.
    def __init__(self, *args: object, **kwargs: object) -> None:
        """Inicializa cliente aceitando parâmetros legados (migração gradual)."""
        kw = cast("dict[str, Any]", kwargs)
        # Suporta criação via kwargs legados: nome_razao_social / tipo_pessoa / cpf / cnpj
        self._legacy_nome_razao_social = kw.pop("nome_razao_social", None)
        tipo_pessoa = kw.pop("tipo_pessoa", None)
        # Guardar documentos caso fornecidos junto à criação (não são campos diretos em Cliente)
        self._legacy_cpf = kw.get("cpf") or kw.pop("cpf", None)
        self._legacy_cnpj = kw.get("cnpj") or kw.pop("cnpj", None)
        # Aceitar 'nome' e 'documento' legados
        legacy_nome_simple = kw.pop("nome", None)
        if not self._legacy_nome_razao_social and legacy_nome_simple:
            self._legacy_nome_razao_social = legacy_nome_simple
        legacy_documento = kw.pop("documento", None)
        if legacy_documento:
            # Heurística simples: 14+ chars com '/' ou '-' => CNPJ, senão CPF
            if (
                isinstance(legacy_documento, str)
                and len(legacy_documento) >= CNPJ_MIN_LENGTH_THRESHOLD
                and any(ch in legacy_documento for ch in ["/", "-"])
            ):
                self._legacy_cnpj = self._legacy_cnpj or legacy_documento
                if not tipo_pessoa and "tipo" not in kw:
                    tipo_pessoa = "PJ"
            elif isinstance(legacy_documento, str):
                self._legacy_cpf = self._legacy_cpf or legacy_documento
                if not tipo_pessoa and "tipo" not in kw:
                    tipo_pessoa = "PF"
        if tipo_pessoa and "tipo" not in kw:
            kw["tipo"] = tipo_pessoa
        # Mapear status legados
        legacy_status = kw.get("status")
        status_map = {"ATIVO": "active", "INATIVO": "inactive", "SUSPENSO": "suspended"}
        if isinstance(legacy_status, str) and legacy_status in status_map:
            kw["status"] = status_map[legacy_status]
        super().__init__(*cast("tuple[Any, ...]", args), **kw)

    def __str__(self) -> str:  # noqa: D105 - descrição simples suficiente
        return self.nome_display

    def save(self, *args: object, **kwargs: object) -> None:
        """Salvar cliente ajustando flag legado e criando PF/PJ se necessário."""
        self.ativo = self.status == "active"
        super().save(*cast("tuple[Any, ...]", args), **cast("dict[str, Any]", kwargs))
        # Criação automática de registros PF/PJ quando fornecido nome_razao_social legado
        # Somente executa na primeira gravação (id recém criado) e se ainda não existir relação
        legacy_nome = getattr(self, "_legacy_nome_razao_social", None)
        if legacy_nome:
            try:
                if self.tipo == "PF" and not hasattr(self, "pessoafisica"):
                    cpf_val = getattr(self, "_legacy_cpf", None) or "000.000.000-00"
                    PessoaFisica.objects.create(cliente=self, nome_completo=legacy_nome, cpf=cpf_val)
                elif self.tipo == "PJ" and not hasattr(self, "pessoajuridica"):
                    cnpj_val = getattr(self, "_legacy_cnpj", None) or "00.000.000/0000-00"
                    PessoaJuridica.objects.create(
                        cliente=self,
                        razao_social=legacy_nome,
                        nome_fantasia=legacy_nome,
                        cnpj=cnpj_val,
                    )
            finally:
                # Evita recriação em saves subsequentes
                self._legacy_nome_razao_social = None

    def get_absolute_url(self) -> str:
        """URL canônica do detalhe do cliente no site."""
        return reverse("clientes:clientes_detail", args=[str(self.id)])

    @property
    def nome_display(self) -> str:
        """Nome amigável exibido (PF: nome completo, PJ: nome fantasia/razão)."""
        if self.tipo == "PF" and hasattr(self, "pessoafisica"):
            return self.pessoafisica.nome_completo
        if self.tipo == "PJ" and hasattr(self, "pessoajuridica"):
            return self.pessoajuridica.nome_fantasia or self.pessoajuridica.razao_social
        return f"{_('Cliente')} #{self.id}"

    @property
    def documento_principal(self) -> str:
        """Retorna CPF ou CNPJ baseado no tipo do cliente."""
        if self.tipo == "PF" and hasattr(self, "pessoafisica"):
            return self.pessoafisica.cpf
        if self.tipo == "PJ" and hasattr(self, "pessoajuridica"):
            return self.pessoajuridica.cnpj
        return ""

    # -------------------------
    # Compatibilidade Legada
    # -------------------------

    @property
    def nome_razao_social(self) -> str:
        """Alias legado que retorna o mesmo valor de ``nome_display``."""
        return self.nome_display

    @property
    def tipo_pessoa(self) -> str:
        """Alias legado para ``tipo``."""
        return self.tipo

    @property
    def nome_fantasia(self) -> str:
        """Retorna nome fantasia quando PJ; string vazia caso contrário."""
        return self.pessoajuridica.nome_fantasia if self.tipo == "PJ" and hasattr(self, "pessoajuridica") else ""


# Modelos relacionados (Contatos, Endereços, etc.)


class PessoaFisica(models.Model):
    """Dados específicos de pessoa física relacionados a um ``Cliente`` PF."""

    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, primary_key=True, related_name="pessoafisica")
    nome_completo = models.CharField(max_length=200, verbose_name=_("Nome Completo"))
    cpf = models.CharField(max_length=14, verbose_name=_("CPF"))
    rg = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("RG"))
    data_nascimento = models.DateField(blank=True, null=True, verbose_name=_("Data de Nascimento"))
    SEXO_CHOICES = (("M", "Masculino"), ("F", "Feminino"), ("O", "Outro"))
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True, null=True, verbose_name=_("Sexo"))
    naturalidade = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Naturalidade (Cidade de Nascimento)"),
    )
    nome_mae = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Nome da Mãe"))
    nome_pai = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Nome do Pai"))
    ESTADO_CIVIL_CHOICES = (
        ("S", _("Solteiro(a)")),
        ("C", _("Casado(a)")),
        ("D", _("Divorciado(a)")),
        ("V", _("Viúvo(a)")),
        ("U", _("União Estável")),
        ("O", _("Outro")),
    )
    estado_civil = models.CharField(
        max_length=1,
        choices=ESTADO_CIVIL_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Estado Civil"),
    )
    profissao = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Profissão"))
    nacionalidade = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Nacionalidade"),
        default=_("Brasileira"),
    )

    class Meta:
        """Metadados de Pessoa Física."""

        verbose_name = _("Pessoa Física")
        verbose_name_plural = _("Pessoas Físicas")

    def __str__(self) -> str:  # noqa: D105
        return self.nome_completo or "Pessoa Física sem nome"


class PessoaJuridica(models.Model):
    """Dados específicos de pessoa jurídica relacionados a um ``Cliente`` PJ."""

    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, primary_key=True, related_name="pessoajuridica")
    razao_social = models.CharField(max_length=200, verbose_name=_("Razão Social"))
    nome_fantasia = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Nome Fantasia"))
    cnpj = models.CharField(max_length=18, verbose_name=_("CNPJ"))
    inscricao_estadual = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Inscrição Estadual"))
    inscricao_municipal = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Inscrição Municipal"))
    data_fundacao = models.DateField(blank=True, null=True, verbose_name=_("Data de Fundação"))
    ramo_atividade = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Ramo de Atividade"))
    porte_empresa = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Porte da Empresa"))
    website = models.URLField(max_length=200, blank=True, null=True, verbose_name=_("Site / Website"))
    email_financeiro = models.EmailField(max_length=254, blank=True, null=True, verbose_name=_("E-mail do Financeiro"))
    telefone_financeiro = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Telefone do Financeiro"),
    )

    class Meta:
        """Metadados de Pessoa Jurídica."""

        verbose_name = _("Pessoa Jurídica")
        verbose_name_plural = _("Pessoas Jurídicas")

    def __str__(self) -> str:  # noqa: D105
        return self.razao_social or "Pessoa Jurídica sem razão social"


class Contato(models.Model):
    """Contato adicional (telefone, email, whatsapp, etc.) vinculado ao cliente."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="contatos_adicionais")
    TIPO_CHOICES = (
        ("TEL", _("Telefone Fixo")),
        ("CEL", _("Celular")),
        ("EMAIL", _("E-mail")),
        ("WHATS", _("WhatsApp")),
        ("SITE", _("Website")),
        ("OUTRO", _("Outro")),
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name=_("Tipo de Contato"))
    valor = models.CharField(max_length=254, verbose_name=_("Contato (Telefone, Email, etc.)"))
    nome_contato_responsavel = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Nome do Contato (Responsável)"),
    )
    cargo = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Cargo"))
    principal = models.BooleanField(default=False, verbose_name=_("Contato Principal deste Tipo"))
    observacao = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Observação"))

    class Meta:
        """Metadados de Contato adicional do cliente."""

        verbose_name = _("Contato Adicional")
        verbose_name_plural = _("Contatos Adicionais")

    def __str__(self) -> str:  # noqa: D105
        return (
            f"{self.get_tipo_display()}: {self.valor} "
            f"({self.cliente.nome_display if self.cliente else 'Cliente não associado'})"
        )


class AcessoCliente(models.Model):
    """Vínculo de usuários internos com acesso ao portal do cliente."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="acessos")
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="acessos_cliente")
    is_admin_portal = models.BooleanField(default=False, verbose_name=_("É Administrador do Portal?"))
    data_concessao = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Metadados de Acesso de usuários ao portal do cliente."""

        verbose_name = _("Acesso de Cliente ao Portal")
        verbose_name_plural = _("Acessos de Clientes ao Portal")
        unique_together = ("cliente", "usuario")

    def __str__(self) -> str:  # noqa: D105
        return f"{self.usuario.username} -> {self.cliente.nome_display}"


class EnderecoAdicional(models.Model):
    """Endereço adicional do cliente com classificação (Comercial, Entrega, etc.)."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="enderecos_adicionais")
    TIPO_CHOICES = (
        ("COM", _("Comercial")),
        ("RES", _("Residencial")),
        ("ENT", _("Entrega")),
        ("COB", _("Cobrança")),
        ("FILIAL", _("Filial")),
        ("OUTRO", _("Outro")),
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name=_("Tipo de Endereço"))
    logradouro = models.CharField(max_length=200, verbose_name=_("Logradouro"))
    numero = models.CharField(max_length=20, verbose_name=_("Número"))
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Complemento"))
    bairro = models.CharField(max_length=100, verbose_name=_("Bairro"))
    cidade = models.CharField(max_length=100, verbose_name=_("Cidade"))
    estado = models.CharField(max_length=2, verbose_name=_("Estado (UF)"))
    cep = models.CharField(max_length=10, verbose_name=_("CEP"))
    pais = models.CharField(max_length=50, verbose_name=_("País"), blank=True, null=True, default="Brasil")
    ponto_referencia = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Ponto de Referência"))
    principal = models.BooleanField(default=False, verbose_name=_("Endereço Principal deste Tipo"))

    class Meta:
        """Metadados de Endereço adicional."""

        verbose_name = _("Endereço Adicional")
        verbose_name_plural = _("Endereços Adicionais")

    def __str__(self) -> str:  # noqa: D105
        return f"{self.logradouro}, {self.numero} - {self.cidade}"


def cliente_documento_path(instance: models.Model, filename: str) -> str:
    """Gerar caminho único para documento legado (modelo descontinuado)."""
    inst = cast("DocumentoCliente", instance)
    ext = filename.split(".")[-1]
    tenant_id_str = str(inst.cliente.tenant.id) if inst.cliente.tenant else "sem_tenant"
    cliente_id_str = str(inst.cliente.pk)
    unique_filename = f"{uuid.uuid4()}.{ext}"
    return str(
        Path("tenants") / tenant_id_str / "clientes" / cliente_id_str / "documentos" / unique_filename,
    )


class DocumentoCliente(models.Model):
    """Modelo legado (descontinuado) mantido apenas para leitura temporária.

    Os dados foram migrados para o app ``documentos``. Evite criar dependências
    novas; será removido após validação de migração completa.
    """

    # Mantido sem campos para evitar uso novo; não migrar/alterar.

    def __str__(self) -> str:  # noqa: D105
        return f"DocumentoCliente(LEGACY id={self.pk})"
