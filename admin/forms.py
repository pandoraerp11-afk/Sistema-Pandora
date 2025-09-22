"""Formulários do app Admin.

Inclui formulários de Tenant, Alertas e Configurações com tipagem e lint
compatíveis (ruff/mypy), sem alterar regras de negócio.
"""

from __future__ import annotations

import json
from typing import ClassVar, cast

from django import forms
from django.contrib.auth import get_user_model

from core.models import Tenant

from .models import SystemAlert, SystemConfiguration, TenantConfiguration

User = get_user_model()


class TenantForm(forms.ModelForm):
    """Formulário para criar e atualizar Tenants, alinhado com os campos de core.models.Tenant."""

    class Meta:
        """Opções de configuração do Django para o formulário Tenant."""

        model = Tenant
        # Campos corrigidos para refletir o modelo Tenant
        fields: ClassVar[list[str]] = [
            "name",
            "subdomain",
            "status",
            "razao_social",
            "tipo_pessoa",
            "logo",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "subdomain": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "identificador_unico_da_empresa"},
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "razao_social": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_pessoa": forms.Select(attrs={"class": "form-select"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
        labels: ClassVar[dict[str, str]] = {
            "name": "Nome Fantasia",
            "subdomain": "Subdomínio (Identificador Único)",
            "status": "Status",
            "razao_social": "Razão Social",
            "tipo_pessoa": "Tipo de Pessoa",
            "logo": "Logo da Empresa",
        }


class SystemAlertForm(forms.ModelForm):
    """Formulário ultra-moderno para criar e editar alertas do sistema."""

    class Meta:
        """Opções de configuração do Django para o formulário de alertas."""

        model = SystemAlert
        fields: ClassVar[list[str]] = [
            "title",
            "description",
            "severity",
            "alert_type",
            "tenant",
            "assigned_to",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Título do alerta...", "maxlength": 200},
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "placeholder": "Descrição detalhada do alerta...", "rows": 4},
            ),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "alert_type": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Tipo do alerta (ex: system, security, performance)",
                    "maxlength": 50,
                },
            ),
            "tenant": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
        }
        labels: ClassVar[dict[str, str]] = {
            "title": "Título do Alerta",
            "description": "Descrição",
            "severity": "Severidade",
            "alert_type": "Tipo de Alerta",
            "tenant": "Empresa (opcional)",
            "assigned_to": "Atribuído para",
        }

    def __init__(self, *args, **kwargs: object) -> None:  # noqa: ANN002
        """Inicializa o formulário configurando querysets com tipagem explícita."""
        super().__init__(*args, **kwargs)
        # Configurar queryset para usuários administradores
        assigned_to_field = cast(forms.ModelChoiceField, self.fields["assigned_to"])
        assigned_to_field.queryset = User.objects.filter(is_staff=True).order_by("first_name", "last_name")
        assigned_to_field.empty_label = "Selecione um usuário..."

        # Configurar queryset para tenants
        tenant_field = cast(forms.ModelChoiceField, self.fields["tenant"])
        tenant_field.queryset = Tenant.objects.filter(status="active").order_by("name")
        tenant_field.empty_label = "Alerta global (todas as empresas)"


class SystemConfigurationForm(forms.ModelForm):
    """Formulário ultra-moderno para configurações globais do sistema."""

    class Meta:
        """Opções de configuração do Django para o formulário de configurações do sistema."""

        model = SystemConfiguration
        fields: ClassVar[list[str]] = ["key", "value", "description", "category", "is_editable"]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "key": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "CHAVE_CONFIGURACAO",
                    "style": "font-family: monospace;",
                },
            ),
            "value": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Valor da configuração (JSON válido)",
                    "rows": 3,
                    "style": "font-family: monospace;",
                },
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "placeholder": "Descrição detalhada da configuração...", "rows": 2},
            ),
            "category": forms.Select(
                choices=[
                    ("geral", "Geral"),
                    ("email", "E-mail"),
                    ("seguranca", "Segurança"),
                    ("sistema", "Sistema"),
                    ("api", "API"),
                    ("backup", "Backup"),
                    ("interface", "Interface"),
                ],
                attrs={"class": "form-select"},
            ),
            "is_editable": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels: ClassVar[dict[str, str]] = {
            "key": "Chave da Configuração",
            "value": "Valor",
            "description": "Descrição",
            "category": "Categoria",
            "is_editable": "Editável pelos usuários",
        }

    def clean_value(self) -> str:
        """Valida se o valor é um JSON válido."""
        value: str = self.cleaned_data["value"]
        try:
            json.loads(value)
        except json.JSONDecodeError as err:
            message = "O valor deve ser um JSON válido."
            raise forms.ValidationError(message) from err
        else:
            return value


class TenantConfigurationForm(forms.ModelForm):
    """Formulário ultra-moderno para configurações específicas da empresa."""

    class Meta:
        """Opções de configuração do Django para o formulário de configurações de tenant."""

        model = TenantConfiguration
        fields: ClassVar[list[str]] = [
            "max_users",
            "max_storage_mb",
            "max_api_requests_per_hour",
            "require_2fa",
            "backup_enabled",
            "custom_branding",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "max_users": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 10000, "placeholder": "100"},
            ),
            "max_storage_mb": forms.NumberInput(
                attrs={"class": "form-control", "min": 100, "max": 100000, "placeholder": "1024"},
            ),
            "max_api_requests_per_hour": forms.NumberInput(
                attrs={"class": "form-control", "min": 100, "max": 1000000, "placeholder": "1000"},
            ),
            "require_2fa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "backup_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "custom_branding": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": '{"logo_url": "", "primary_color": "#007bff", "company_name": ""}',
                    "rows": 3,
                    "style": "font-family: monospace;",
                },
            ),
        }
        labels: ClassVar[dict[str, str]] = {
            "max_users": "Máximo de Usuários",
            "max_storage_mb": "Máximo de Armazenamento (MB)",
            "max_api_requests_per_hour": "Máx. Requisições API/hora",
            "require_2fa": "Exigir Autenticação 2FA",
            "backup_enabled": "Backup Automático Habilitado",
            "custom_branding": "Customização Visual (JSON)",
        }

    def clean_custom_branding(self) -> str:
        """Valida se o custom_branding é um JSON válido."""
        value: str = self.cleaned_data["custom_branding"]
        if value:
            try:
                json.loads(value)
            except json.JSONDecodeError as err:
                message = "A customização deve ser um JSON válido."
                raise forms.ValidationError(message) from err
            else:
                return value
        return value
