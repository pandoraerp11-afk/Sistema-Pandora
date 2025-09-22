# core/forms.py - VERSÃO FINAL, COMPLETA E SINCRONIZADA

from django import forms
from django.db import models
from django.forms import DateInput, inlineformset_factory
from django.utils.translation import gettext_lazy as _

from cadastros_gerais.models import ItemAuxiliar  # novo: para filtrar tipos de documentos aplicáveis

# Modelos importados
from .models import (  # novo: modelos de versionamento
    Contato,
    CustomUser,
    Department,
    EmpresaDocumento,
    EmpresaDocumentoVersao,
    Endereco,
    EnderecoAdicional,
    Role,
    Tenant,
    TenantDocumento,
    TenantUser,
)


class BasePandoraForm(forms.ModelForm):
    """
    Classe base de estilização mantida 100% intacta.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _field_name, field in self.fields.items():
            widget = field.widget
            current_class = widget.attrs.get("class", "")
            if not isinstance(widget, (forms.CheckboxInput, forms.FileInput, forms.RadioSelect)):
                if "form-control" not in current_class:
                    widget.attrs["class"] = f"{current_class} form-control".strip()
            if isinstance(widget, forms.Select):
                if "select2" not in current_class:
                    widget.attrs["class"] = f"{widget.attrs.get('class', '')} select2".strip()
            elif isinstance(widget, forms.CheckboxInput):
                if "form-check-input" not in current_class:
                    widget.attrs["class"] = f"{current_class} form-check-input".strip()
            elif isinstance(widget, forms.FileInput):
                widget.attrs["class"] = f"{current_class} custom-file-input".strip()
            if isinstance(widget, forms.Textarea) and "rows" not in widget.attrs:
                widget.attrs["rows"] = 3


# ============================================================================
# FORMULÁRIOS DE TENANT
# ============================================================================


class TenantBaseForm(BasePandoraForm):
    class Meta:
        model = Tenant
        fields = [
            "name",
            "subdomain",
            "status",
            "tipo_pessoa",
            "logo",
            "codigo_interno",
            "email",
            "telefone",
            "telefone_secundario",
            "observacoes",
            "plano_assinatura",
            "data_ativacao_plano",
            "data_fim_trial",
            "max_usuarios",
            "max_armazenamento_gb",
            "data_proxima_cobranca",
            "portal_ativo",
        ]
        widgets = {
            "tipo_pessoa": forms.Select(attrs={"id": "id_tenant_tipo_pessoa"}),
            "name": forms.TextInput(attrs={"placeholder": "Nome Fantasia ou Nome Completo"}),
            "subdomain": forms.TextInput(attrs={"placeholder": "identificador-unico"}),
            "codigo_interno": forms.TextInput(attrs={"placeholder": "Ex: E-001"}),
            "email": forms.EmailInput(attrs={"placeholder": "email.principal@dominio.com"}),
            "telefone": forms.TextInput(attrs={"class": "phone-mask", "placeholder": "(99) 99999-9999"}),
            "telefone_secundario": forms.TextInput(attrs={"class": "phone-mask", "placeholder": "(99) 99999-9999"}),
            "observacoes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Informações adicionais sobre a empresa..."}
            ),
            "data_ativacao_plano": DateInput(
                attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}
            ),
            "data_fim_trial": DateInput(attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}),
            "data_proxima_cobranca": DateInput(
                attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}
            ),
        }

    def clean_subdomain(self):
        subdomain = self.cleaned_data.get("subdomain")
        if subdomain:
            # Verificar se já existe (excluindo a instância atual se for edição)
            queryset = Tenant.objects.filter(subdomain=subdomain)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError("Este subdomínio já está em uso.")
        return subdomain


class TenantPessoaJuridicaForm(BasePandoraForm):
    class Meta:
        model = Tenant
        fields = [
            "razao_social",
            "cnpj",
            "inscricao_estadual",
            "inscricao_municipal",
            "data_fundacao",
            "ramo_atividade",
            "porte_empresa",
            "website",
            "regime_tributario",
            "cnae_principal",
            "email_financeiro",
            "nome_responsavel_financeiro",
            "telefone_financeiro",
        ]
        widgets = {
            "razao_social": forms.TextInput(attrs={"placeholder": "Nome de registro da empresa"}),
            "cnpj": forms.TextInput(attrs={"class": "cnpj-mask", "placeholder": "99.999.999/9999-99"}),
            "inscricao_estadual": forms.TextInput(attrs={"placeholder": "Número da I.E."}),
            "inscricao_municipal": forms.TextInput(attrs={"placeholder": "Número da I.M."}),
            "data_fundacao": DateInput(attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}),
            "ramo_atividade": forms.TextInput(attrs={"placeholder": "Ex: Construção Civil"}),
            "porte_empresa": forms.TextInput(attrs={"placeholder": "MEI, Pequena, Média..."}),
            "website": forms.URLInput(attrs={"placeholder": "https://www.empresa.com.br"}),
            "cnae_principal": forms.TextInput(attrs={"placeholder": "Ex: 4120-4/00"}),
            "email_financeiro": forms.EmailInput(attrs={"placeholder": "financeiro@empresa.com"}),
            "nome_responsavel_financeiro": forms.TextInput(attrs={"placeholder": "Nome do contato financeiro"}),
            "telefone_financeiro": forms.TextInput(attrs={"class": "phone-mask", "placeholder": "(99) 99999-9999"}),
        }


class TenantPessoaFisicaForm(BasePandoraForm):
    class Meta:
        model = Tenant
        fields = [
            "cpf",
            "rg",
            "data_nascimento",
            "sexo",
            "estado_civil",
            "nacionalidade",
            "naturalidade",
            "nome_mae",
            "nome_pai",
            "profissao",
            "escolaridade",
        ]
        widgets = {
            "cpf": forms.TextInput(attrs={"class": "cpf-mask", "placeholder": "999.999.999-99"}),
            "rg": forms.TextInput(attrs={"placeholder": "Número do RG"}),
            "data_nascimento": DateInput(attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}),
            "nacionalidade": forms.TextInput(attrs={"placeholder": "País de nacionalidade"}),
            "naturalidade": forms.TextInput(attrs={"placeholder": "Cidade de nascimento"}),
            "nome_mae": forms.TextInput(attrs={"placeholder": "Nome completo da mãe"}),
            "nome_pai": forms.TextInput(attrs={"placeholder": "Nome completo do pai"}),
            "profissao": forms.TextInput(attrs={"placeholder": "Engenheiro, Médico..."}),
            "escolaridade": forms.Select(attrs={"placeholder": "Selecione a escolaridade"}),
        }


# ============================================================================
# FORMULÁRIOS E FORMSETS DE ENDEREÇO
# ============================================================================


class EnderecoPrincipalForm(BasePandoraForm):
    class Meta:
        model = Endereco
        exclude = ["tenant", "tipo"]
        widgets = {
            "cep": forms.TextInput(attrs={"class": "cep-mask", "placeholder": "99999-999"}),
            "pais": forms.TextInput(attrs={"placeholder": "Brasil"}),
            "ponto_referencia": forms.TextInput(attrs={"placeholder": "Ponto de referência"}),
        }


# --- INÍCIO DA ADIÇÃO NECESSÁRIA PARA CORRIGIR O ERRO ---
class EnderecoAdicionalForm(BasePandoraForm):
    class Meta:
        model = EnderecoAdicional
        exclude = ["tenant"]
        widgets = {
            "cep": forms.TextInput(attrs={"class": "cep-mask", "placeholder": "99999-999"}),
            "pais": forms.TextInput(attrs={"placeholder": "Brasil"}),
            "ponto_referencia": forms.TextInput(attrs={"placeholder": "Ponto de referência"}),
        }


EnderecoAdicionalFormSet = inlineformset_factory(
    Tenant, EnderecoAdicional, form=EnderecoAdicionalForm, extra=0, can_delete=True
)
# --- FIM DA ADIÇÃO NECESSÁRIA PARA CORRIGIR O ERRO ---


# ============================================================================
# FORMSETS PARA OUTROS MODELOS RELACIONADOS
# ============================================================================


class ContatoForm(BasePandoraForm):
    class Meta:
        model = Contato
        fields = ["nome", "cargo", "email", "telefone", "observacao"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome completo do contato (opcional)"}),
            "cargo": forms.TextInput(attrs={"placeholder": "Cargo ou departamento"}),
            "email": forms.EmailInput(attrs={"placeholder": "email@empresa.com"}),
            "telefone": forms.TextInput(attrs={"class": "phone-mask", "placeholder": "(99) 99999-9999"}),
            "observacao": forms.Textarea(attrs={"placeholder": "Observações sobre o contato", "rows": 3}),
        }


class TenantDocumentoForm(BasePandoraForm):
    class Meta:
        model = TenantDocumento
        fields = ["tipo", "descricao", "arquivo", "url"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "descricao": forms.TextInput(attrs={"placeholder": "Descrição do documento"}),
        }


ContatoFormSet = inlineformset_factory(Tenant, Contato, form=ContatoForm, extra=0, can_delete=True)
TenantDocumentoFormSet = inlineformset_factory(
    Tenant, TenantDocumento, form=TenantDocumentoForm, extra=0, can_delete=True
)


# ============================================================================
# OUTROS FORMULÁRIOS DO SISTEMA
# ============================================================================

"""Formulários legacy InitialAdminForm/InitialAdminFormSet removidos.

Motivo: fluxo de criação de administradores iniciais agora acontece 100% via
wizard multi-admin (step específico com JSON dinâmico). A manutenção destes
formsets encobriria código morto e aumentaria custos de manutenção.
"""


class CustomUserForm(BasePandoraForm):
    password2 = forms.CharField(label=_("Confirmação de senha"), widget=forms.PasswordInput, required=False)

    class Meta:
        model = CustomUser
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password2",
            "phone",
            "bio",
            "theme_preference",
            "is_active",
            "is_staff",
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class RoleForm(BasePandoraForm):
    class Meta:
        model = Role
        fields = ["tenant", "name", "description", "is_active", "department", "permissions"]
        widgets = {"permissions": forms.CheckboxSelectMultiple(attrs={"class": "permissions-matrix"})}

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import Permission

        self.fields["permissions"].queryset = Permission.objects.all().select_related("content_type")
        from .models import Department, Tenant

        user = getattr(self.request, "user", None)
        is_super = bool(user and getattr(user, "is_superuser", False))
        # Campo tenant
        if "tenant" in self.fields:
            if is_super:
                self.fields["tenant"].queryset = Tenant.objects.all().order_by("name")
                self.fields["tenant"].required = False
                self.fields["tenant"].label = "Empresa (Tenant)"
                self.fields["tenant"].help_text = "Deixe em branco para tornar este cargo Global."
            else:
                # Usuário comum: ocultar e fixar tenant recebido por kwargs
                self.fields["tenant"].widget = forms.HiddenInput()
                if self.tenant:
                    self.fields["tenant"].initial = self.tenant

        # Departamentos
        if "department" in self.fields:
            base_qs = Department.objects.all()
            active_tenant = None
            if is_super:
                # Primeiro tenta POST, depois initial/instance, depois kwargs tenant
                active_tenant = self.data.get("tenant") or (self.instance.tenant_id if self.instance.pk else None)
            else:
                active_tenant = self.tenant.id if getattr(self.tenant, "id", None) else None
            if active_tenant:
                self.fields["department"].queryset = base_qs.filter(
                    models.Q(tenant__isnull=True) | models.Q(tenant_id=active_tenant)
                ).order_by("tenant__name", "name")
            # Superuser sem tenant escolhido: mostrar todos para facilitar (globais + específicos) ordenados
            elif is_super:
                self.fields["department"].queryset = base_qs.order_by("tenant__name", "name")
            else:
                # fallback: somente globais
                self.fields["department"].queryset = base_qs.filter(tenant__isnull=True).order_by("name")
            self.fields["department"].required = False


class DepartmentForm(BasePandoraForm):
    class Meta:
        model = Department
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # Se superuser: permitir escolher tenant explicitamente (profissional / transparente)
        from .models import Tenant

        if self.request and getattr(self.request.user, "is_superuser", False):
            self.fields["tenant"] = forms.ModelChoiceField(
                queryset=Tenant.objects.all().order_by("name"),
                required=False,
                label="Empresa (Tenant)",
                help_text="Deixe em branco para tornar este departamento Global (visível em todas as empresas).",
            )
        # Em contexto não superuser o tenant será forçado na view; não expor campo.


class TenantUserForm(BasePandoraForm):
    email_or_username = forms.CharField(
        label="E-mail ou Nome de Usuário",
        help_text="Digite o e-mail ou nome de usuário do usuário que deseja vincular",
        widget=forms.TextInput(attrs={"placeholder": "usuario@exemplo.com ou nome_usuario"}),
        required=False,
    )

    class Meta:
        model = TenantUser
        fields = ["role", "department", "is_tenant_admin"]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["role"].queryset = Role.objects.filter(tenant=self.tenant)
            self.fields["department"].queryset = Department.objects.filter(tenant=self.tenant)
        if self.instance and self.instance.pk:
            if "email_or_username" in self.fields:
                del self.fields["email_or_username"]
        else:
            self.fields["email_or_username"].required = True

    def clean_email_or_username(self):
        email_or_username = self.cleaned_data.get("email_or_username")
        if not email_or_username and not (self.instance and self.instance.pk):
            raise forms.ValidationError("Este campo é obrigatório.")
        if not email_or_username:
            return email_or_username
        try:
            user = CustomUser.objects.get(models.Q(email=email_or_username) | models.Q(username=email_or_username))
        except CustomUser.DoesNotExist:
            raise forms.ValidationError("Usuário não encontrado com este e-mail ou nome de usuário.")
        if TenantUser.objects.filter(tenant=self.tenant, user=user).exists():
            raise forms.ValidationError("Este usuário já está vinculado a esta empresa.")
        return user

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tenant = self.tenant
        if not instance.pk and "email_or_username" in self.cleaned_data:
            instance.user = self.cleaned_data["email_or_username"]
        if commit:
            instance.save()
        return instance


class ModuleConfigurationForm(forms.Form):
    # Configuração visual dos módulos (ícones e cores)
    MODULE_ICONS_AND_COLORS = {
        # Módulos Básicos de Gestão
        "clientes": {"icon": "fas fa-users", "color": "text-primary", "category": "Gestão Básica"},
        "fornecedores": {"icon": "fas fa-truck", "color": "text-info", "category": "Gestão Básica"},
        "produtos": {"icon": "fas fa-box", "color": "text-success", "category": "Gestão Básica"},
        "servicos": {"icon": "fas fa-tools", "color": "text-warning", "category": "Gestão Básica"},
        "funcionarios": {"icon": "fas fa-id-badge", "color": "text-secondary", "category": "Gestão Básica"},
        "cadastros_gerais": {"icon": "fas fa-database", "color": "text-dark", "category": "Gestão Básica"},
        # Módulos de Obras e Projetos
        "obras": {"icon": "fas fa-hard-hat", "color": "text-primary", "category": "Obras e Projetos"},
        "orcamentos": {"icon": "fas fa-calculator", "color": "text-info", "category": "Obras e Projetos"},
        "quantificacao_obras": {
            "icon": "fas fa-ruler-combined",
            "color": "text-success",
            "category": "Obras e Projetos",
        },
        "apropriacao": {"icon": "fas fa-chart-pie", "color": "text-warning", "category": "Obras e Projetos"},
        "mao_obra": {"icon": "fas fa-users-cog", "color": "text-secondary", "category": "Obras e Projetos"},
        # Módulos Financeiros e Operacionais
        "compras": {"icon": "fas fa-shopping-cart", "color": "text-success", "category": "Financeiro e Operacional"},
        "financeiro": {"icon": "fas fa-dollar-sign", "color": "text-warning", "category": "Financeiro e Operacional"},
        "estoque": {"icon": "fas fa-warehouse", "color": "text-secondary", "category": "Financeiro e Operacional"},
        "aprovacoes": {"icon": "fas fa-check-circle", "color": "text-success", "category": "Financeiro e Operacional"},
        # Módulos de Saúde e Clínicas
        "prontuarios": {"icon": "fas fa-file-medical", "color": "text-danger", "category": "Saúde e Clínicas"},
        "sst": {"icon": "fas fa-shield-alt", "color": "text-danger", "category": "Saúde e Clínicas"},
        # Módulos de Comunicação e Organização
        "agenda": {"icon": "fas fa-calendar", "color": "text-success", "category": "Comunicação e Organização"},
        "chat": {"icon": "fas fa-comments", "color": "text-warning", "category": "Comunicação e Organização"},
        "notifications": {"icon": "fas fa-bell", "color": "text-info", "category": "Comunicação e Organização"},
        # Módulos de Formulários e Documentação
        "formularios": {"icon": "fas fa-file-alt", "color": "text-secondary", "category": "Formulários e Documentação"},
        "formularios_dinamicos": {
            "icon": "fas fa-magic",
            "color": "text-purple",
            "category": "Formulários e Documentação",
        },
        # Módulos de Capacitação e Gestão
        "treinamento": {"icon": "fas fa-graduation-cap", "color": "text-info", "category": "Capacitação e Gestão"},
        "user_management": {"icon": "fas fa-users-cog", "color": "text-dark", "category": "Capacitação e Gestão"},
        # Módulos de Análise e Inteligência
        "relatorios": {"icon": "fas fa-chart-bar", "color": "text-primary", "category": "Análise e Inteligência"},
        "bi": {"icon": "fas fa-chart-line", "color": "text-info", "category": "Análise e Inteligência"},
        "ai_auditor": {"icon": "fas fa-robot", "color": "text-success", "category": "Análise e Inteligência"},
        # Módulos Administrativos
        "admin": {"icon": "fas fa-tachometer-alt", "color": "text-dark", "category": "Administrativo"},
    }

    # Categorias organizadas para melhor apresentação
    MODULE_CATEGORIES = {
        "Gestão Básica": {
            "icon": "fas fa-building",
            "color": "text-primary",
            "description": "Módulos essenciais para o dia a dia da empresa",
        },
        "Obras e Projetos": {
            "icon": "fas fa-hard-hat",
            "color": "text-warning",
            "description": "Módulos especializados em construção e projetos",
        },
        "Financeiro e Operacional": {
            "icon": "fas fa-dollar-sign",
            "color": "text-success",
            "description": "Controle financeiro e operações da empresa",
        },
        "Saúde e Clínicas": {
            "icon": "fas fa-heartbeat",
            "color": "text-danger",
            "description": "Módulos para clínicas e profissionais da saúde",
        },
        "Comunicação e Organização": {
            "icon": "fas fa-comments",
            "color": "text-info",
            "description": "Ferramentas de comunicação e organização interna",
        },
        "Formulários e Documentação": {
            "icon": "fas fa-file-alt",
            "color": "text-secondary",
            "description": "Criação e gestão de formulários e documentos",
        },
        "Capacitação e Gestão": {
            "icon": "fas fa-graduation-cap",
            "color": "text-primary",
            "description": "Treinamentos e gestão de pessoas",
        },
        "Análise e Inteligência": {
            "icon": "fas fa-chart-line",
            "color": "text-info",
            "description": "Relatórios, BI e inteligência artificial",
        },
        "Administrativo": {
            "icon": "fas fa-tachometer-alt",
            "color": "text-dark",
            "description": "Ferramentas administrativas e configurações",
        },
    }

    # Definição completa dos módulos disponíveis
    AVAILABLE_MODULES = {
        # Módulos Básicos de Gestão
        "clientes": {
            "name": "Clientes",
            "description": "Gestão completa de clientes, contratos e relacionamentos",
            "category": "Gestão Básica",
            "premium": False,
        },
        "fornecedores": {
            "name": "Fornecedores",
            "description": "Cadastro e gestão de fornecedores e parcerias",
            "category": "Gestão Básica",
            "premium": False,
        },
        "produtos": {
            "name": "Produtos",
            "description": "Catálogo de produtos, preços e especificações",
            "category": "Gestão Básica",
            "premium": False,
        },
        "servicos": {
            "name": "Serviços",
            "description": "Gestão de serviços oferecidos pela empresa",
            "category": "Gestão Básica",
            "premium": False,
        },
        "funcionarios": {
            "name": "Funcionários",
            "description": "Gestão de recursos humanos e colaboradores",
            "category": "Gestão Básica",
            "premium": False,
        },
        "cadastros_gerais": {
            "name": "Cadastros Gerais",
            "description": "Cadastros auxiliares e configurações gerais",
            "category": "Gestão Básica",
            "premium": False,
        },
        # Módulos de Obras e Projetos
        "obras": {
            "name": "Obras",
            "description": "Gestão completa de obras e projetos de construção",
            "category": "Obras e Projetos",
            "premium": False,
        },
        "orcamentos": {
            "name": "Orçamentos",
            "description": "Criação e gestão de orçamentos detalhados",
            "category": "Obras e Projetos",
            "premium": False,
        },
        "quantificacao_obras": {
            "name": "Quantificação de Obras",
            "description": "Cálculos e quantificações para projetos",
            "category": "Obras e Projetos",
            "premium": True,
        },
        "apropriacao": {
            "name": "Apropriação",
            "description": "Apropriação de custos e controle de obras",
            "category": "Obras e Projetos",
            "premium": True,
        },
        "mao_obra": {
            "name": "Mão de Obra",
            "description": "Gestão de equipes e mão de obra especializada",
            "category": "Obras e Projetos",
            "premium": False,
        },
        # Módulos Financeiros e Operacionais
        "compras": {
            "name": "Compras",
            "description": "Sistema de compras, cotações e aquisições",
            "category": "Financeiro e Operacional",
            "premium": False,
        },
        "financeiro": {
            "name": "Financeiro",
            "description": "Controle financeiro completo da empresa",
            "category": "Financeiro e Operacional",
            "premium": False,
        },
        "estoque": {
            "name": "Estoque",
            "description": "Controle de estoque e movimentações",
            "category": "Financeiro e Operacional",
            "premium": False,
        },
        "aprovacoes": {
            "name": "Aprovações",
            "description": "Sistema de workflow e aprovações",
            "category": "Financeiro e Operacional",
            "premium": True,
        },
        # Módulos de Saúde e Clínicas
        "prontuarios": {
            "name": "Prontuários",
            "description": "Prontuários médicos eletrônicos",
            "category": "Saúde e Clínicas",
            "premium": True,
        },
        "sst": {
            "name": "SST",
            "description": "Segurança e Saúde do Trabalho",
            "category": "Saúde e Clínicas",
            "premium": True,
        },
        # Módulos de Comunicação e Organização
        "agenda": {
            "name": "Agenda",
            "description": "Agenda compartilhada e agendamentos",
            "category": "Comunicação e Organização",
            "premium": False,
        },
        "chat": {
            "name": "Chat",
            "description": "Chat interno em tempo real",
            "category": "Comunicação e Organização",
            "premium": True,
        },
        "notifications": {
            "name": "Notificações",
            "description": "Sistema de notificações e alertas",
            "category": "Comunicação e Organização",
            "premium": False,
        },
        # Módulos de Formulários e Documentação
        "formularios": {
            "name": "Formulários",
            "description": "Formulários customizados para a empresa",
            "category": "Formulários e Documentação",
            "premium": False,
        },
        "formularios_dinamicos": {
            "name": "Formulários Dinâmicos",
            "description": "Criador avançado de formulários dinâmicos",
            "category": "Formulários e Documentação",
            "premium": True,
        },
        # Módulos de Capacitação e Gestão
        "treinamento": {
            "name": "Treinamentos",
            "description": "Sistema de treinamentos e capacitação",
            "category": "Capacitação e Gestão",
            "premium": True,
        },
        "user_management": {
            "name": "Gestão de Usuários",
            "description": "Gestão avançada de usuários e permissões",
            "category": "Capacitação e Gestão",
            "premium": False,
        },
        # Módulos de Análise e Inteligência
        "relatorios": {
            "name": "Relatórios",
            "description": "Sistema completo de relatórios",
            "category": "Análise e Inteligência",
            "premium": False,
        },
        "bi": {
            "name": "Business Intelligence",
            "description": "Dashboards e análises inteligentes",
            "category": "Análise e Inteligência",
            "premium": True,
        },
        "ai_auditor": {
            "name": "Auditor IA",
            "description": "Auditoria automatizada com inteligência artificial",
            "category": "Análise e Inteligência",
            "premium": True,
        },
        # Módulos Administrativos
        "admin": {
            "name": "Dashboard Admin",
            "description": "Painel administrativo avançado",
            "category": "Administrativo",
            "premium": False,
        },
    }

    # Lista de tuplas para o campo de formulário
    AVAILABLE_MODULES_CHOICES = [(key, str(info.get("name", key))) for key, info in AVAILABLE_MODULES.items()]

    enabled_modules = forms.MultipleChoiceField(
        choices=sorted(AVAILABLE_MODULES_CHOICES, key=lambda x: (x[1] or "")),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "custom-checkbox-list"}),
        required=False,
        label=_("Selecione os módulos para habilitar para esta empresa"),
    )

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant and getattr(self.tenant, "enabled_modules", None):
            try:
                import json

                enabled_modules_data = self.tenant.enabled_modules
                if isinstance(enabled_modules_data, str):
                    initial_modules = json.loads(enabled_modules_data)
                elif isinstance(enabled_modules_data, dict):
                    initial_modules = enabled_modules_data.get("modules", [])
                else:
                    initial_modules = []
                self.fields["enabled_modules"].initial = initial_modules
            except (json.JSONDecodeError, TypeError):
                pass

    def save(self):
        if not self.tenant:
            raise TypeError("O tenant não foi fornecido para o formulário.")
        import json

        selected_modules = self.cleaned_data.get("enabled_modules", [])
        self.tenant.enabled_modules = json.dumps(selected_modules)
        self.tenant.save(update_fields=["enabled_modules"])


class EmpresaDocumentoVersaoCreateForm(forms.Form):
    tipo = forms.ModelChoiceField(queryset=ItemAuxiliar.objects.none(), label=_("Tipo de Documento"))
    arquivo = forms.FileField(label=_("Arquivo"))
    data_vigencia_inicio = forms.DateField(label=_("Início da Vigência"), widget=DateInput(attrs={"type": "date"}))
    data_vigencia_fim = forms.DateField(
        label=_("Fim da Vigência"), required=False, widget=DateInput(attrs={"type": "date"})
    )
    competencia = forms.CharField(label=_("Competência (MM/AAAA)"), required=False)
    observacao = forms.CharField(label=_("Observação"), required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        # Filtrar tipos aplicáveis a EMPRESA nas categorias conhecidas
        qs = ItemAuxiliar.objects.filter(ativo=True)
        qs = qs.filter(models.Q(alvo="empresa") | models.Q(targets__code="empresa")).distinct()
        qs = qs.filter(categoria__slug__in=["documentos-da-empresa", "documentos-financeiros", "outros-documentos"])
        self.fields["tipo"].queryset = qs.order_by("categoria__ordem", "ordem", "nome")

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        competencia = cleaned.get("competencia")
        # Se o tipo tiver periodicidade, sugerir/validar competência preenchida
        if tipo and getattr(tipo, "periodicidade", "nenhuma") != "nenhuma" and not competencia:
            # Não tornar obrigatório duro; apenas dica. Pode-se habilitar validação dura se necessário:
            # raise forms.ValidationError(_('Competência é obrigatória para documentos periódicos.'))
            pass
        return cleaned

    def save(self, user=None):
        if not self.tenant:
            raise ValueError("Tenant é obrigatório para salvar a versão do documento.")
        tipo = self.cleaned_data["tipo"]
        arquivo = self.cleaned_data["arquivo"]
        data_ini = self.cleaned_data["data_vigencia_inicio"]
        data_fim = self.cleaned_data.get("data_vigencia_fim")
        competencia = self.cleaned_data.get("competencia")
        observacao = self.cleaned_data.get("observacao")

        # Obter ou criar o registro do documento por (tenant, tipo)
        doc, _ = EmpresaDocumento.objects.get_or_create(tenant=self.tenant, tipo=tipo)
        proxima_versao = (doc.versao_atual or 0) + 1

        versao = EmpresaDocumentoVersao.objects.create(
            documento=doc,
            versao=proxima_versao,
            arquivo=arquivo,
            data_vigencia_inicio=data_ini,
            data_vigencia_fim=data_fim,
            competencia=competencia,
            observacao=observacao,
            usuario=user if user and getattr(user, "pk", None) else None,
        )
        # Atualizar cabeçalho
        doc.versao_atual = proxima_versao
        doc.status_atual = "ATIVO"
        doc.save(update_fields=["versao_atual", "status_atual", "updated_at"])
        return versao
