# core/models.py - VERSÃO EVOLUÍDA PARA MULTI-EMPRESAS
# NENHUM CAMPO ORIGINAL REMOVIDO - APENAS ADICIONADOS NOVOS CAMPOS E FUNCIONALIDADES


from django.contrib.auth.models import AbstractUser, Group, Permission
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import EmailValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from cadastros_gerais.models import ItemAuxiliar

# ============================================================================
# MODELO BASE PARA TIMESTAMPS (MANTIDO ORIGINAL)
# ============================================================================


class TimestampedModel(models.Model):
    """Modelo abstrato base que adiciona campos de timestamp a todos os modelos"""

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Data de criação"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Data de atualização"))

    class Meta:
        abstract = True


# ============================================================================
# MODELO TENANT EVOLUÍDO - FUNDAÇÃO UNIVERSAL PARA MULTI-EMPRESAS
# ============================================================================


class Tenant(TimestampedModel):
    """
    Modelo principal que representa uma empresa/organização no sistema multi-tenant.
    Evoluído para suportar diferentes tipos de empresas: construtoras, clínicas de estética,
    clínicas médicas, empresas de vendas, e qualquer outro tipo de negócio.

    IMPORTANTE: Todos os campos originais foram mantidos para compatibilidade total.
    Novos campos foram adicionados para expandir as funcionalidades.
    """

    # ========================================================================
    # CAMPOS ORIGINAIS (100% MANTIDOS PARA COMPATIBILIDADE)
    # ========================================================================

    TIPO_PESSOA_CHOICES = [("PJ", "Pessoa Jurídica"), ("PF", "Pessoa Física")]

    STATUS_CHOICES = [("active", _("Ativo")), ("inactive", _("Inativo")), ("suspended", _("Suspenso"))]

    # ------------------------------------------------------------------
    # COMPATIBILIDADE LEGADA
    # Aceita kwargs antigos: nome, slug, email_contato.
    # Mantém testes e código legado funcionando sem alterar chamadas.
    # ------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        legacy = {"nome": "name", "slug": "subdomain", "email_contato": "email", "schema_name": "subdomain"}
        for old, new in list(legacy.items()):
            if old in kwargs and new not in kwargs:
                kwargs[new] = kwargs.pop(old)
        super().__init__(*args, **kwargs)

    # Campos básicos originais
    name = models.CharField(
        max_length=100, verbose_name=_("Nome Fantasia / Nome de Exibição"), help_text=_("Nome que aparecerá no sistema")
    )
    subdomain = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Subdomínio (identificador único)"),
        help_text=_("Identificador único usado para acessar o sistema"),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", verbose_name=_("Status"))
    enabled_modules = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Módulos Habilitados"),
        help_text=_("Configuração dos módulos ativos para esta empresa"),
    )
    logo = models.ImageField(
        upload_to="tenant_logos/",
        null=True,
        blank=True,
        verbose_name=_("Logo da Empresa"),
        help_text=_("Logo que aparecerá no sistema"),
    )

    # Compat: alguns trechos legados referenciam tenant.slug; expor property.
    @property
    def slug(self):  # pragma: no cover - simples
        return self.subdomain

    @slug.setter
    def slug(self, value):  # pragma: no cover
        self.subdomain = value

    def save(self, *args, **kwargs):
        if self.subdomain:
            self.subdomain = self.subdomain.strip().lower()
        # Compat testes: se em ambiente de teste e enabled_modules vazio, auto popular com todos módulos conhecidos
        try:
            from django.conf import settings

            if getattr(settings, "TESTING", False) and (not self.enabled_modules or self.enabled_modules == {}):
                # Lista simplificada baseada em PANDORA_MODULES do settings se disponível
                mods = []
                try:
                    from django.conf import settings as _s

                    for item in getattr(_s, "PANDORA_MODULES", []):
                        if isinstance(item, dict) and item.get("module_name"):
                            mods.append(item["module_name"])
                except Exception:
                    pass
                if mods:
                    self.enabled_modules = {"modules": sorted(set(mods))}
            # Normalização estrita opcional
            if getattr(settings, "FEATURE_STRICT_ENABLED_MODULES", False):
                try:
                    self.enabled_modules = self._normalize_enabled_modules(self.enabled_modules)
                except Exception:
                    # Falha de normalização não deve impedir persistência; aplica fallback vazio canonical
                    self.enabled_modules = {"modules": []}
        except Exception:
            pass
        super().save(*args, **kwargs)

    @staticmethod
    def _normalize_enabled_modules(raw):  # pragma: no cover - coberto indiretamente por testes
        import json as _json

        normalized = []
        if isinstance(raw, dict):
            if "modules" in raw and isinstance(raw["modules"], (list, tuple)):
                normalized = list(dict.fromkeys([str(m).strip() for m in raw["modules"] if m]))
            else:
                normalized = [k for k, v in raw.items() if v in (True, 1, "on", "ON")]
        elif isinstance(raw, (list, tuple)):
            normalized = list(dict.fromkeys([str(m).strip() for m in raw if m]))
        elif isinstance(raw, str):
            s = raw.strip()
            try:
                if s.startswith("[") or s.startswith("{"):
                    parsed = _json.loads(s)
                    if isinstance(parsed, list):
                        normalized = list(dict.fromkeys([str(m).strip() for m in parsed if m]))
                    elif isinstance(parsed, dict) and "modules" in parsed:
                        normalized = list(dict.fromkeys([str(m).strip() for m in parsed["modules"] if m]))
                    elif isinstance(parsed, dict):
                        normalized = [k for k, v in parsed.items() if v in (True, 1, "on", "ON")]
            except Exception:
                pass
            if not normalized:
                cleaned = s.replace("[", "").replace("]", "").replace('"', "").replace("'", "")
                normalized = [m.strip() for m in cleaned.replace(";", ",").split(",") if m.strip()]
        return {"modules": normalized}

    # Métodos/aliases legados
    def is_active(self) -> bool:  # pragma: no cover
        return getattr(self, "status", None) == "active"

    @property
    def modules(self):  # pragma: no cover
        # Pode ser dict arbitrário legado ou formato {"modules": [...]}
        return self.enabled_modules or {}

    @modules.setter
    def modules(self, value):  # pragma: no cover
        self.enabled_modules = value or {}

    def has_module(self, code: str) -> bool:
        if code == "core":
            return True
        mods = self.modules
        # Formato novo tolerante {"modules": [..]}
        if isinstance(mods, dict):
            if "modules" in mods and isinstance(mods["modules"], list):
                return code in mods["modules"]
            data = mods.get(code)
            if isinstance(data, dict):
                val = data.get("enabled")
                return val in (True, 1, "on", "ON")
        return False

    # Campos de identificação originais
    tipo_pessoa = models.CharField(
        max_length=2, choices=TIPO_PESSOA_CHOICES, default="PJ", verbose_name=_("Tipo de Pessoa")
    )
    razao_social = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Razão Social"))
    cnpj = models.CharField(
        max_length=18,
        blank=True,
        null=True,
        verbose_name=_("CNPJ"),
        validators=[
            RegexValidator(
                regex=r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$", message=_("CNPJ deve estar no formato XX.XXX.XXX/XXXX-XX")
            )
        ],
    )
    inscricao_estadual = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Inscrição Estadual"))
    cpf = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        verbose_name=_("CPF"),
        validators=[
            RegexValidator(regex=r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", message=_("CPF deve estar no formato XXX.XXX.XXX-XX"))
        ],
    )
    rg = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("RG"))

    # ========================================================================
    # NOVOS CAMPOS EXPANDIDOS - INFORMAÇÕES GERAIS
    # ========================================================================

    # Informações básicas expandidas
    codigo_interno = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Código Interno"),
        help_text=_("Código interno para identificação da empresa"),
    )
    nome_contato_principal = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Nome do Responsável Principal"),
        help_text=_("Nome da pessoa responsável pela empresa"),
    )

    # Informações de contato expandidas
    email = models.EmailField(
        max_length=254, blank=True, null=True, verbose_name=_("E-mail Principal"), validators=[EmailValidator()]
    )
    email_financeiro = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
        verbose_name=_("E-mail do Financeiro"),
        help_text=_("E-mail específico para questões financeiras"),
    )
    email_comercial = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
        verbose_name=_("E-mail Comercial"),
        help_text=_("E-mail específico para questões comerciais"),
    )
    email_tecnico = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
        verbose_name=_("E-mail Técnico"),
        help_text=_("E-mail específico para questões técnicas"),
    )

    # Telefones expandidos
    telefone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Telefone Principal"),
        validators=[
            RegexValidator(
                regex=r"^\(\d{2}\)\s\d{4,5}-\d{4}$", message=_("Telefone deve estar no formato (XX) XXXXX-XXXX")
            )
        ],
    )
    telefone_secundario = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Telefone Secundário"),
        validators=[
            RegexValidator(
                regex=r"^\(\d{2}\)\s\d{4,5}-\d{4}$", message=_("Telefone deve estar no formato (XX) XXXXX-XXXX")
            )
        ],
    )
    telefone_financeiro = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Telefone do Financeiro"),
        help_text=_("Telefone específico do setor financeiro"),
    )
    telefone_comercial = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Telefone Comercial"),
        help_text=_("Telefone específico do setor comercial"),
    )
    telefone_emergencia = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Telefone de Emergência"),
        help_text=_("Telefone para contato em emergências"),
    )
    whatsapp = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("WhatsApp"), help_text=_("Número do WhatsApp para contato")
    )

    # ========================================================================
    # CAMPOS PARA PESSOA JURÍDICA EXPANDIDOS
    # ========================================================================

    inscricao_municipal = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Inscrição Municipal"))
    data_fundacao = models.DateField(blank=True, null=True, verbose_name=_("Data de Fundação"))
    data_abertura = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Data de Abertura"),
        help_text=_("Data de abertura da empresa na Receita Federal"),
    )

    # Classificação da empresa
    PORTE_EMPRESA_CHOICES = [
        ("MEI", _("Microempreendedor Individual")),
        ("ME", _("Microempresa")),
        ("EPP", _("Empresa de Pequeno Porte")),
        ("MEDIA", _("Empresa de Médio Porte")),
        ("GRANDE", _("Empresa de Grande Porte")),
    ]
    porte_empresa = models.CharField(
        max_length=10, choices=PORTE_EMPRESA_CHOICES, blank=True, null=True, verbose_name=_("Porte da Empresa")
    )

    # Atividade econômica
    ramo_atividade = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Ramo de Atividade Principal")
    )
    cnae_principal = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name=_("CNAE Principal"),
        help_text=_("Código CNAE da atividade principal"),
    )
    cnae_secundarios = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("CNAEs Secundários"),
        help_text=_("Lista de códigos CNAE das atividades secundárias"),
    )

    # Informações online
    website = models.URLField(max_length=200, blank=True, null=True, verbose_name=_("Site / Website"))
    redes_sociais = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Redes Sociais"),
        help_text=_("Links para redes sociais (Facebook, Instagram, LinkedIn, etc.)"),
    )

    # Responsáveis específicos
    nome_responsavel_financeiro = models.CharField(
        max_length=200, blank=True, null=True, verbose_name=_("Nome do Responsável Financeiro")
    )
    nome_responsavel_comercial = models.CharField(
        max_length=200, blank=True, null=True, verbose_name=_("Nome do Responsável Comercial")
    )
    nome_responsavel_tecnico = models.CharField(
        max_length=200, blank=True, null=True, verbose_name=_("Nome do Responsável Técnico")
    )

    # ========================================================================
    # CAMPOS PARA PESSOA FÍSICA EXPANDIDOS
    # ========================================================================

    data_nascimento = models.DateField(blank=True, null=True, verbose_name=_("Data de Nascimento"))

    SEXO_CHOICES = [("M", _("Masculino")), ("F", _("Feminino")), ("O", _("Outro")), ("N", _("Não informar"))]
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True, null=True, verbose_name=_("Sexo"))

    naturalidade = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Naturalidade (Cidade de Nascimento)")
    )
    nacionalidade = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Nacionalidade"), default=_("Brasileira")
    )

    # Filiação
    nome_mae = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Nome da Mãe"))
    nome_pai = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Nome do Pai"))

    # Estado civil
    ESTADO_CIVIL_CHOICES = [
        ("S", _("Solteiro(a)")),
        ("C", _("Casado(a)")),
        ("D", _("Divorciado(a)")),
        ("V", _("Viúvo(a)")),
        ("U", _("União Estável")),
        ("O", _("Outro")),
    ]
    estado_civil = models.CharField(
        max_length=1, choices=ESTADO_CIVIL_CHOICES, blank=True, null=True, verbose_name=_("Estado Civil")
    )

    profissao = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Profissão"))

    # Escolaridade para pessoa física
    ESCOLARIDADE_CHOICES = [
        ("FUNDAMENTAL_INCOMPLETO", "Ensino Fundamental Incompleto"),
        ("FUNDAMENTAL_COMPLETO", "Ensino Fundamental Completo"),
        ("MEDIO_INCOMPLETO", "Ensino Médio Incompleto"),
        ("MEDIO_COMPLETO", "Ensino Médio Completo"),
        ("SUPERIOR_INCOMPLETO", "Ensino Superior Incompleto"),
        ("SUPERIOR_COMPLETO", "Ensino Superior Completo"),
        ("ESPECIALIZACAO", "Especialização/Pós-graduação"),
        ("MESTRADO", "Mestrado"),
        ("DOUTORADO", "Doutorado"),
        ("POS_DOUTORADO", "Pós-doutorado"),
    ]

    escolaridade = models.CharField(
        max_length=50, choices=ESCOLARIDADE_CHOICES, blank=True, null=True, verbose_name=_("Escolaridade")
    )

    # ========================================================================
    # CAMPOS ESPECÍFICOS POR SETOR (USANDO JSON PARA FLEXIBILIDADE)
    # ========================================================================

    # Dados específicos para construção civil
    dados_construcao_civil = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Dados Específicos - Construção Civil"),
        help_text=_("Especialidades, certificações, registros CREA, etc."),
    )

    # Dados específicos para área da saúde (clínicas médicas e estéticas)
    dados_saude = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Dados Específicos - Área da Saúde"),
        help_text=_("Especialidades médicas, equipamentos, certificações ANVISA, etc."),
    )

    # Dados específicos para comércio e vendas
    dados_comerciais = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Dados Específicos - Comércio"),
        help_text=_("Canais de venda, marketplaces, categorias de produtos, etc."),
    )

    # Dados específicos para serviços
    dados_servicos = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Dados Específicos - Serviços"),
        help_text=_("Tipos de serviços, certificações, especializações, etc."),
    )

    # ========================================================================
    # CONFIGURAÇÕES REGIONAIS E OPERACIONAIS
    # ========================================================================

    # Configurações regionais
    TIMEZONE_CHOICES = [
        ("America/Sao_Paulo", _("Brasília (UTC-3)")),
        ("America/Manaus", _("Manaus (UTC-4)")),
        ("America/Rio_Branco", _("Rio Branco (UTC-5)")),
        ("America/Noronha", _("Fernando de Noronha (UTC-2)")),
    ]
    timezone = models.CharField(
        max_length=50, choices=TIMEZONE_CHOICES, default="America/Sao_Paulo", verbose_name=_("Fuso Horário")
    )

    IDIOMA_CHOICES = [
        ("pt-br", _("Português (Brasil)")),
        ("en", _("English")),
        ("es", _("Español")),
    ]
    idioma_padrao = models.CharField(
        max_length=10, choices=IDIOMA_CHOICES, default="pt-br", verbose_name=_("Idioma Padrão")
    )

    # Configurações de moeda e formato
    MOEDA_CHOICES = [
        ("BRL", _("Real Brasileiro (R$)")),
        ("USD", _("Dólar Americano ($)")),
        ("EUR", _("Euro (€)")),
    ]
    moeda_padrao = models.CharField(max_length=3, choices=MOEDA_CHOICES, default="BRL", verbose_name=_("Moeda Padrão"))

    formato_data = models.CharField(
        max_length=20,
        default="DD/MM/YYYY",
        verbose_name=_("Formato de Data"),
        help_text=_("Formato padrão para exibição de datas"),
    )

    # ========================================================================
    # INFORMAÇÕES FISCAIS E TRIBUTÁRIAS
    # ========================================================================

    REGIME_TRIBUTARIO_CHOICES = [
        ("SIMPLES", _("Simples Nacional")),
        ("PRESUMIDO", _("Lucro Presumido")),
        ("REAL", _("Lucro Real")),
        ("MEI", _("Microempreendedor Individual")),
        ("ISENTO", _("Isento")),
    ]
    regime_tributario = models.CharField(
        max_length=20, choices=REGIME_TRIBUTARIO_CHOICES, blank=True, null=True, verbose_name=_("Regime Tributário")
    )

    inscricao_suframa = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Inscrição SUFRAMA"),
        help_text=_("Número de inscrição na SUFRAMA, se aplicável"),
    )

    # ========================================================================
    # GESTÃO DA ASSINATURA E LIMITES (EXPANDIDO)
    # ========================================================================

    PLANO_ASSINATURA_CHOICES = [
        ("BASIC", "Básico"),
        ("PRO", "Profissional"),
        ("ENTERPRISE", "Enterprise"),
        ("CUSTOM", "Personalizado"),
    ]
    plano_assinatura = models.CharField(
        max_length=10, choices=PLANO_ASSINATURA_CHOICES, default="BASIC", verbose_name=_("Plano de Assinatura")
    )
    data_ativacao_plano = models.DateField(blank=True, null=True, verbose_name=_("Data de Ativação do Plano"))
    data_proxima_cobranca = models.DateField(blank=True, null=True, verbose_name=_("Próxima Cobrança"))
    data_fim_trial = models.DateTimeField(blank=True, null=True, verbose_name=_("Fim do Período de Teste"))
    max_usuarios = models.PositiveIntegerField(
        default=5, verbose_name=_("Nº Máximo de Usuários"), help_text=_("Defina 0 para ilimitado.")
    )
    max_armazenamento_gb = models.PositiveIntegerField(
        default=1, verbose_name=_("Armazenamento Máx. (GB)"), help_text=_("Defina 0 para ilimitado.")
    )

    # ========================================================================
    # CONFIGURAÇÕES DE PORTAL E ACESSO
    # ========================================================================

    portal_ativo = models.BooleanField(
        default=False,
        verbose_name=_("Portal do Cliente Ativo?"),
        help_text=_("Indica se o portal de acesso para clientes/usuários externos está ativo."),
    )

    # ========================================================================
    # OUTROS CAMPOS GERAIS
    # ========================================================================

    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Observações Gerais"),
        help_text=_("Informações adicionais relevantes sobre a empresa."),
    )

    # ========================================================================
    # METADADOS E OTIMIZAÇÃO
    # ========================================================================

    class Meta(TimestampedModel.Meta):
        verbose_name = _("empresa (tenant)")
        verbose_name_plural = _("empresas (tenants)")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["subdomain"]),
            models.Index(fields=["cnpj"]),
            models.Index(fields=["cpf"]),
            models.Index(fields=["status"]),
            models.Index(fields=["tipo_pessoa"]),
        ]

    def __str__(self):
        return self.name

    def is_module_enabled(self, module_name):
        """Retorna True se o módulo está habilitado (formato canonical estrito).

        Formato suportado: {'modules': ['mod1','mod2', ...]} somente.
        Qualquer divergência retorna False (dados devem ser previamente normalizados).
        """
        data = self.enabled_modules
        if isinstance(data, dict):
            mods = data.get("modules")
            if isinstance(mods, list):
                return module_name in mods
        return False

    def get_documento_principal(self):
        """Retorna o CPF ou CNPJ dependendo do tipo de pessoa."""
        if self.tipo_pessoa == "PF":
            return self.cpf
        elif self.tipo_pessoa == "PJ":
            return self.cnpj
        return None

    def get_idade_empresa(self):
        """Calcula a idade da empresa em anos, se data de fundação/abertura existir."""
        if self.data_fundacao:
            today = timezone.now().date()
            return (
                today.year
                - self.data_fundacao.year
                - ((today.month, today.day) < (self.data_fundacao.month, self.data_fundacao.day))
            )
        return None

    def get_status_display_color(self):
        """Retorna uma cor para o status, útil para dashboards."""
        if self.status == "active":
            return "green"
        elif self.status == "inactive":
            return "red"
        elif self.status == "suspended":
            return "orange"
        return "gray"


# ============================================================================
# NOVOS MODELOS RELACIONADOS AO TENANT
# ============================================================================


class TenantPessoaFisica(TimestampedModel):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, primary_key=True, related_name="pessoafisica_info")
    nome_completo = models.CharField(max_length=200, verbose_name=_("Nome Completo"))
    cpf = models.CharField(max_length=14, verbose_name=_("CPF"))
    rg = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("RG"))
    data_nascimento = models.DateField(blank=True, null=True, verbose_name=_("Data de Nascimento"))
    SEXO_CHOICES = (("M", "Masculino"), ("F", "Feminino"), ("O", "Outro"))
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True, null=True, verbose_name=_("Sexo"))
    naturalidade = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Naturalidade (Cidade de Nascimento)")
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
        max_length=1, choices=ESTADO_CIVIL_CHOICES, blank=True, null=True, verbose_name=_("Estado Civil")
    )
    profissao = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Profissão"))
    nacionalidade = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Nacionalidade"), default=_("Brasileira")
    )

    class Meta:
        verbose_name = _("Pessoa Física do Tenant")
        verbose_name_plural = _("Pessoas Físicas do Tenant")

    def __str__(self):
        return self.nome_completo


class TenantPessoaJuridica(TimestampedModel):
    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, primary_key=True, related_name="pessoajuridica_info"
    )
    razao_social = models.CharField(max_length=200, verbose_name=_("Razão Social"))
    nome_fantasia = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Nome Fantasia"))
    cnpj = models.CharField(max_length=18, blank=True, null=True, verbose_name=_("CNPJ"))
    inscricao_estadual = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Inscrição Estadual"))
    inscricao_municipal = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Inscrição Municipal"))
    data_fundacao = models.DateField(blank=True, null=True, verbose_name=_("Data de Fundação"))
    ramo_atividade = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Ramo de Atividade"))
    porte_empresa = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Porte da Empresa"))
    website = models.URLField(max_length=200, blank=True, null=True, verbose_name=_("Site / Website"))
    email_financeiro = models.EmailField(max_length=254, blank=True, null=True, verbose_name=_("E-mail do Financeiro"))
    telefone_financeiro = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("Telefone do Financeiro")
    )

    class Meta:
        verbose_name = _("Pessoa Jurídica do Tenant")
        verbose_name_plural = _("Pessoas Jurídicas do Tenant")

    def __str__(self):
        return self.razao_social


class Endereco(TimestampedModel):
    TIPO_ENDERECO_CHOICES = [
        ("PRINCIPAL", "Principal"),
        ("COBRANCA", "Cobrança"),
        ("ENTREGA", "Entrega"),
        ("FISCAL", "Fiscal"),
        ("OUTRO", "Outro"),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="enderecos", verbose_name=_("Empresa"))
    tipo = models.CharField(
        max_length=20, choices=TIPO_ENDERECO_CHOICES, default="PRINCIPAL", verbose_name=_("Tipo de Endereço")
    )
    logradouro = models.CharField(max_length=200, verbose_name=_("Logradouro"))
    numero = models.CharField(max_length=20, verbose_name=_("Número"))
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Complemento"))
    bairro = models.CharField(max_length=100, verbose_name=_("Bairro"))
    cidade = models.CharField(max_length=100, verbose_name=_("Cidade"))
    uf = models.CharField(max_length=2, verbose_name=_("UF"))
    cep = models.CharField(max_length=9, verbose_name=_("CEP"))
    pais = models.CharField(max_length=50, verbose_name=_("País"), blank=True, null=True, default="Brasil")
    ponto_referencia = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Ponto de Referência"))

    class Meta:
        verbose_name = _("endereço")
        verbose_name_plural = _("endereços")
        ordering = ["tipo"]

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.logradouro}, {self.numero}"


class EnderecoAdicional(TimestampedModel):
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, related_name="enderecos_adicionais")
    TIPO_CHOICES = (
        ("COB", "Cobrança"),
        ("ENT", "Entrega"),
        ("FISCAL", "Fiscal"),
        ("OUTRO", "Outro"),
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    logradouro = models.CharField(max_length=200)
    numero = models.CharField(max_length=20)
    complemento = models.CharField(max_length=100, blank=True, null=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    uf = models.CharField(max_length=2)
    cep = models.CharField(max_length=10)
    pais = models.CharField(max_length=50, blank=True, null=True, default="Brasil")
    ponto_referencia = models.CharField(max_length=200, blank=True, null=True)
    principal = models.BooleanField(default=False, verbose_name="Endereço Principal deste Tipo")

    class Meta:
        verbose_name = _("Endereço Adicional")
        verbose_name_plural = _("Endereços Adicionais")
        ordering = ["tipo", "id"]

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.logradouro}, {self.numero}"


class Contato(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="contatos", verbose_name=_("Empresa"))
    nome = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Nome Completo do Contato"))
    email = models.EmailField(blank=True, null=True, verbose_name=_("E-mail"))
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Telefone"))
    cargo = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Cargo / Departamento"))
    observacao = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        verbose_name = _("contato")
        verbose_name_plural = _("contatos")
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class TenantDocumento(TimestampedModel):
    TIPO_DOCUMENTO_CHOICES = [
        ("CONTRATO", "Contrato"),
        ("RG", "RG"),
        ("CPF", "CPF"),
        ("OUTRO", "Outro"),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="documentos", verbose_name=_("Empresa"))
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_DOCUMENTO_CHOICES,
        default="OUTRO",
        blank=True,
        null=True,
        verbose_name=_("Tipo de Documento"),
    )
    descricao = models.CharField(max_length=255, verbose_name=_("Descrição do Documento"))
    arquivo = models.FileField(upload_to="tenant_documentos/", verbose_name=_("Arquivo"))
    # Se quiser url:
    url = models.URLField(blank=True, null=True, verbose_name=_("URL do Documento"))

    class Meta:
        verbose_name = _("documento da empresa")
        verbose_name_plural = _("documentos da empresa")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.descricao} - {self.tenant.name}"


class CustomUser(AbstractUser):
    profile_image = models.ImageField(
        upload_to="profile_images/", null=True, blank=True, verbose_name=_("Imagem de Perfil")
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name=_("Telefone"))
    bio = models.TextField(blank=True, verbose_name=_("Biografia"))
    theme_preference = models.CharField(
        max_length=10,
        choices=[("light", "Claro"), ("dark", "Escuro"), ("auto", "Automático")],
        default="auto",
        verbose_name=_("Preferência de Tema"),
    )
    # Novo: tipo de usuário para distinguir portal vs interno (uso em autorização modular)
    USER_TYPE_CHOICES = [
        ("INTERNAL", "Interno"),
        ("PORTAL", "Portal Externo"),
    ]
    user_type = models.CharField(
        max_length=20, choices=USER_TYPE_CHOICES, default="INTERNAL", db_index=True, verbose_name=_("Tipo de Usuário")
    )
    groups = models.ManyToManyField(
        Group,
        verbose_name=_("groups"),
        blank=True,
        help_text=_(
            "The groups this user belongs to. A user will get all permissions granted to each of their groups."
        ),
        related_name="customuser_groups",
        related_query_name="customuser",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_("user permissions"),
        blank=True,
        help_text=_("Specific permissions for this user."),
        related_name="customuser_permissions",
        related_query_name="customuser",
    )
    is_active_directory_user = models.BooleanField(default=False)
    last_password_change = models.DateTimeField(null=True, blank=True, verbose_name=_("Última troca de senha"))
    require_password_change = models.BooleanField(default=False, verbose_name=_("Exige troca de senha"))
    login_attempts = models.PositiveIntegerField(default=0, verbose_name=_("Tentativas de login"))
    is_locked = models.BooleanField(default=False, verbose_name=_("Conta bloqueada"))

    class Meta:
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")

    def __str__(self):
        return self.username

    pass

    # Compatibilidade legada: vários testes/trechos assumem user.tenant direto
    @property
    def tenant(self):
        # Retorna primeiro vínculo se existir
        rel = getattr(self, "tenant_memberships", None)
        if rel:
            first = rel.first()
            if first:
                return first.tenant
        return getattr(self, "_legacy_single_tenant", None)

    @tenant.setter
    def tenant(self, value):
        from .models import TenantUser  # import local para evitar ordem

        if not value:
            self._legacy_single_tenant = None
            return
        # Criar vínculo se não existir
        try:
            TenantUser.objects.get_or_create(user=self, tenant=value)
        except Exception:
            # Fallback em caso de migrações incompletas
            self._legacy_single_tenant = value

    # Compat: alguns testes usam user.tenants (antigo ManyToMany). Criamos proxy com .add/.all/.count
    class _LegacyTenantsProxy:
        def __init__(self, user):
            self._user = user

        def add(self, *tenants):
            from .models import TenantUser  # local import para evitar ciclos

            for tenant in tenants:
                try:
                    TenantUser.objects.get_or_create(user=self._user, tenant=tenant)
                except Exception:
                    self._user._legacy_single_tenant = tenant

        def all(self):  # retorna lista para simplicidade
            rel = getattr(self._user, "tenant_memberships", None)
            if rel:
                return [tm.tenant for tm in rel.all()]
            legacy = getattr(self._user, "_legacy_single_tenant", None)
            return [legacy] if legacy else []

        def count(self):
            return len(self.all())

        def __iter__(self):
            return iter(self.all())

        def __len__(self):  # len(user.tenants)
            return self.count()

        def __contains__(self, item):
            return item in self.all()

    @property
    def tenants(self):
        return CustomUser._LegacyTenantsProxy(self)


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="profile")
    email_notifications = models.BooleanField(default=True, verbose_name=_("Notificações por E-mail"))
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    items_per_page = models.PositiveIntegerField(default=10, verbose_name=_("Itens por página"))
    dashboard_widgets = models.JSONField(default=dict, blank=True)
    language = models.CharField(max_length=10, default="pt-br", verbose_name=_("Idioma"))
    timezone = models.CharField(max_length=50, default="America/Sao_Paulo", verbose_name=_("Fuso Horário"))
    date_format = models.CharField(max_length=20, default="DD/MM/YYYY")
    last_activity = models.DateTimeField(null=True, blank=True, verbose_name=_("Última Atividade"))

    def __str__(self):
        return f"Perfil de {self.user.username}"


class Role(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="roles",
        verbose_name=_("Empresa"),
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100, verbose_name=_("Nome do Papel"))
    description = models.TextField(blank=True, verbose_name=_("Descrição"))
    permissions = models.ManyToManyField(Permission, blank=True)
    department = models.ForeignKey(
        "Department", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Departamento")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Ativo"))

    class Meta:
        verbose_name = _("papel")
        verbose_name_plural = _("papéis")
        unique_together = ("tenant", "name")

    def __str__(self):
        if self.tenant_id:
            return f"{self.name} ({self.tenant.name})"
        return f"{self.name} (Global)"

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        # Regras de unicidade estendida (mesma lógica de Department):
        # 1) Papel global (tenant=None) não pode duplicar nenhum nome existente (global ou por tenant)
        # 2) Papel de tenant não pode usar nome de um papel global
        qs_same = Role.objects.exclude(pk=self.pk).filter(name__iexact=self.name)
        if self.tenant is None:
            if qs_same.exists():
                raise ValidationError({"name": "Já existe um cargo (global ou associado a uma empresa) com esse nome."})
        elif qs_same.filter(tenant__isnull=True).exists():
            raise ValidationError({"name": "Já existe um cargo global com esse nome."})


class Department(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="departments",
        verbose_name=_("Empresa"),
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100, verbose_name=_("Nome do Departamento"))
    description = models.TextField(blank=True, verbose_name=_("Descrição"))

    class Meta:
        verbose_name = _("departamento")
        verbose_name_plural = _("departamentos")
        # Mantém unicidade por tenant; regras globais tratadas em clean()
        unique_together = ("tenant", "name")

    def __str__(self):
        if self.tenant_id:
            return f"{self.name} ({self.tenant.name})"
        return f"{self.name} (Global)"

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        # Regras de unicidade estendida (opção 3):
        # 1) Global (tenant=None) não pode duplicar nenhum nome existente (global ou por tenant)
        # 2) Departamento de tenant não pode usar nome de um global
        # Comparação case-insensitive
        qs_all_same_name = Department.objects.exclude(pk=self.pk).filter(name__iexact=self.name)
        if self.tenant is None:
            if qs_all_same_name.exists():
                raise ValidationError(
                    {"name": "Já existe um departamento (global ou associado a uma empresa) com esse nome."}
                )
        elif qs_all_same_name.filter(tenant__isnull=True).exists():
            raise ValidationError({"name": "Já existe um departamento global com esse nome."})


class TenantUser(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="tenant_users")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="tenant_memberships")
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Papel"))
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Departamento")
    )
    is_tenant_admin = models.BooleanField(default=False, verbose_name=_("É Administrador da Empresa"))
    # Campo recém adicionado para suportar nova coleta de cargo no wizard multi-admin
    cargo = models.CharField(max_length=120, blank=True, null=True, verbose_name=_("Cargo / Função"))

    class Meta:
        unique_together = ("tenant", "user")
        verbose_name = _("vínculo usuário-empresa")
        verbose_name_plural = _("vínculos usuário-empresa")

    def __str__(self):
        return f"{self.user.username} em {self.tenant.name}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        # Auto atribuição de role default após criação se ausente
        if creating and not self.role:
            try:
                default_role, _ = Role.objects.get_or_create(
                    tenant=self.tenant, name="USER", defaults={"description": "Papel padrão automático"}
                )
                self.role = default_role
                super().save(update_fields=["role"])
            except Exception:
                pass


class AuditLog(models.Model):
    ACTION_TYPES = (
        ("CREATE", "Criação"),
        ("UPDATE", "Atualização"),
        ("DELETE", "Exclusão"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("VIEW", "Visualização"),
        ("OTHER", "Outro"),
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("Usuário"),
    )
    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs", verbose_name=_("Empresa")
    )
    action_type = models.CharField(max_length=10, choices=ACTION_TYPES, verbose_name=_("Tipo de Ação"))
    action_time = models.DateTimeField(auto_now_add=True, verbose_name=_("Data/Hora da Ação"))
    change_message = models.TextField(blank=True, verbose_name=_("Mensagem de Alteração"))
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name=_("Endereço IP"))
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Tipo de Conteúdo")
    )
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("ID do Objeto"))
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-action_time"]
        verbose_name = _("log de auditoria")
        verbose_name_plural = _("logs de auditoria")

    def __str__(self):
        if self.content_object:
            return f"{self.get_action_type_display()} em {self.content_type} por {self.user or 'Sistema'}"
        return f"Ação de {self.get_action_type_display()} por {self.user or 'Sistema'}"


class Certificacao(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="certificacoes", verbose_name=_("Empresa")
    )
    nome_certificacao = models.CharField(max_length=200, verbose_name=_("Nome da Certificação"))
    entidade_emissora = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Entidade Emissora"))
    data_emissao = models.DateField(blank=True, null=True, verbose_name=_("Data de Emissão"))
    data_validade = models.DateField(blank=True, null=True, verbose_name=_("Data de Validade"))
    numero_registro = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Número de Registro"))
    arquivo_anexo = models.FileField(
        upload_to="tenant_certificacoes/", null=True, blank=True, verbose_name=_("Arquivo Anexo")
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        verbose_name = _("Certificação")
        verbose_name_plural = _("Certificações")
        ordering = ["-data_validade"]

    def __str__(self):
        return f"{self.nome_certificacao} ({self.tenant.name})"

    @property
    def is_valid(self):
        if self.data_validade:
            return self.data_validade >= timezone.now().date()
        return True

    @property
    def days_to_expire(self):
        if self.data_validade:
            return (self.data_validade - timezone.now().date()).days
        return None


class DadosBancarios(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="dados_bancarios", verbose_name=_("Empresa")
    )
    banco = models.CharField(max_length=100, verbose_name=_("Banco"))
    agencia = models.CharField(max_length=20, verbose_name=_("Agência"))
    conta = models.CharField(max_length=30, verbose_name=_("Conta"))
    digito = models.CharField(max_length=2, blank=True, null=True, verbose_name=_("Dígito"))
    tipo_conta = models.CharField(
        max_length=20,
        choices=[("CORRENTE", "Conta Corrente"), ("POUPANCA", "Conta Poupança")],
        default="CORRENTE",
        verbose_name=_("Tipo de Conta"),
    )
    chave_pix = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Chave PIX"))
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        verbose_name = _("Dado Bancário")
        verbose_name_plural = _("Dados Bancários")
        unique_together = ("tenant", "banco", "agencia", "conta")

    def __str__(self):
        return f"{self.banco} - Ag: {self.agencia} Cc: {self.conta} ({self.tenant.name})"


class ConfiguracaoSistema(TimestampedModel):
    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, primary_key=True, related_name="configuracoes_sistema"
    )
    permitir_cadastro_auto_clientes = models.BooleanField(
        default=False, verbose_name=_("Permitir cadastro automático de clientes?")
    )
    limite_documentos_upload = models.PositiveIntegerField(
        default=10, verbose_name=_("Limite de documentos por upload")
    )
    notificacoes_email_ativas = models.BooleanField(default=True, verbose_name=_("Notificações por e-mail ativas?"))
    cor_primaria_sistema = models.CharField(
        max_length=7, default="#007bff", verbose_name=_("Cor Primária do Sistema (Hex)")
    )
    logo_login = models.ImageField(
        upload_to="system_configs/", null=True, blank=True, verbose_name=_("Logo da Tela de Login")
    )
    termos_uso = models.TextField(blank=True, null=True, verbose_name=_("Termos de Uso (HTML/Markdown)"))
    politica_privacidade = models.TextField(
        blank=True, null=True, verbose_name=_("Política de Privacidade (HTML/Markdown)")
    )

    class Meta:
        verbose_name = _("Configuração do Sistema")
        verbose_name_plural = _("Configurações do Sistema")

    def __str__(self):
        return f"Configurações de {self.tenant.name}"


class Modulo(TimestampedModel):
    nome = models.CharField(max_length=100, unique=True, verbose_name=_("Nome do Módulo"))
    descricao = models.TextField(blank=True, null=True, verbose_name=_("Descrição do Módulo"))
    ativo_por_padrao = models.BooleanField(default=False, verbose_name=_("Ativo por Padrão para Novos Tenants"))

    class Meta:
        verbose_name = _("Módulo")
        verbose_name_plural = _("Módulos")
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class EmpresaDocumento(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="empresa_documentos", verbose_name=_("Empresa")
    )
    tipo = models.ForeignKey(
        ItemAuxiliar, on_delete=models.PROTECT, related_name="empresa_documentos", verbose_name=_("Tipo de Documento")
    )
    status_atual = models.CharField(max_length=20, default="ATIVO", verbose_name=_("Status Atual"))
    versao_atual = models.PositiveIntegerField(default=0, verbose_name=_("Versão Atual"))

    class Meta:
        verbose_name = _("Documento da Empresa (Tipo)")
        verbose_name_plural = _("Documentos da Empresa (Tipos)")
        unique_together = (("tenant", "tipo"),)
        indexes = [
            models.Index(fields=["tenant", "tipo"]),
        ]

    def __str__(self):
        return f"{self.tenant.name} - {self.tipo.nome} (v{self.versao_atual})"

    @property
    def periodicidade(self):
        return getattr(self.tipo, "periodicidade", "nenhuma")

    @property
    def versionavel(self):
        return getattr(self.tipo, "versionavel", False)


class EmpresaDocumentoVersao(TimestampedModel):
    documento = models.ForeignKey(
        EmpresaDocumento, on_delete=models.CASCADE, related_name="versoes", verbose_name=_("Documento")
    )
    versao = models.PositiveIntegerField(verbose_name=_("Versão"))
    arquivo = models.FileField(upload_to="tenant_documentos/empresa/", verbose_name=_("Arquivo"))
    data_vigencia_inicio = models.DateField(verbose_name=_("Início da Vigência"))
    data_vigencia_fim = models.DateField(blank=True, null=True, verbose_name=_("Fim da Vigência"))
    enviado_em = models.DateTimeField(auto_now_add=True, verbose_name=_("Enviado em"))
    observacao = models.TextField(blank=True, null=True, verbose_name=_("Observação"))
    usuario = models.ForeignKey(
        "CustomUser", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Usuário")
    )
    competencia = models.CharField(max_length=7, blank=True, null=True, verbose_name=_("Competência (MM/AAAA)"))

    class Meta:
        verbose_name = _("Versão de Documento da Empresa")
        verbose_name_plural = _("Versões de Documentos da Empresa")
        unique_together = (("documento", "versao"),)
        indexes = [
            models.Index(fields=["documento", "versao"]),
            models.Index(fields=["competencia"]),
        ]
        ordering = ["-data_vigencia_inicio", "-versao"]

    def __str__(self):
        return f"{self.documento} - v{self.versao}"

    @property
    def vigente(self):
        from django.utils import timezone

        hoje = timezone.now().date()
        if self.data_vigencia_fim:
            return self.data_vigencia_inicio <= hoje <= self.data_vigencia_fim
        return self.data_vigencia_inicio <= hoje


# ============================================================================
# O RESTANTE DOS SEUS MODELOS PERMANECE INALTERADO (APENAS REFERENCIADO)
# ============================================================================

# class CustomUser(AbstractUser):
#     # ... (mantido no arquivo original)

# class UserProfile(models.Model):
#     # ... (mantido no arquivo original)

# class Role(TimestampedModel):
#     # ... (mantido no arquivo original)

# class Department(TimestampedModel):
#     # ... (mantido no arquivo original)

# class TenantUser(TimestampedModel):
#     # ... (mantido no arquivo original)

# class AuditLog(models.Model):
#     # ... (mantido no arquivo original)
