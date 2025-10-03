# clientes/wizard_forms.py - Formulários específicos para o wizard de clientes
"""Formulários adaptados do sistema de wizard do core para clientes.

Reutiliza a estrutura existente com campos específicos de clientes.
Inclui formulários para identificação PF/PJ, dados específicos, contatos,
endereços e revisão final do wizard. Formulários legados não mais usados
permanecem apenas por compatibilidade e poderão ser removidos após ciclo
de migração estável.
"""

from __future__ import annotations

from typing import ClassVar, Final

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.wizard_forms import (
    TenantPessoaFisicaWizardForm,
    TenantPessoaJuridicaWizardForm,
)

from .models import Cliente, PessoaFisica, PessoaJuridica

# Constantes para evitar "magic numbers" em validações
CPF_LENGTH: Final[int] = 11  # Comprimento esperado de CPF sem máscara
CNPJ_LENGTH: Final[int] = 14  # Comprimento esperado de CNPJ sem máscara


class ClientePFIdentificationForm(TenantPessoaFisicaWizardForm):
    """Step 1 (PF) reutiliza form CORE sem checar unicidade no modelo Tenant."""

    def clean_cpf(self) -> str | None:
        """Valida o CPF removendo máscara e checando comprimento."""
        cpf = self.cleaned_data.get("cpf")
        if cpf:
            cpf_digits = "".join(ch for ch in str(cpf) if ch.isdigit())
            if len(cpf_digits) != CPF_LENGTH:
                msg = _("CPF deve ter 11 dígitos")
                raise ValidationError(msg)
        return cpf


class ClientePJIdentificationForm(TenantPessoaJuridicaWizardForm):
    """Step 1 (PJ) reutiliza form CORE sem checar unicidade adicional."""

    def clean_cnpj(self) -> str | None:
        """Valida o CNPJ removendo máscara e checando comprimento."""
        cnpj = self.cleaned_data.get("cnpj")
        if cnpj:
            cnpj_digits = "".join(ch for ch in str(cnpj) if ch.isdigit())
            if len(cnpj_digits) != CNPJ_LENGTH:
                msg = _("CNPJ deve ter 14 dígitos")
                raise ValidationError(msg)
        return cnpj


class ClientePessoaJuridicaWizardForm(forms.ModelForm):
    """STEP 1B: Dados complementares PJ (baseado no form CORE)."""

    class Meta:
        """Configuração de campos e widgets para Pessoa Jurídica."""

        model = PessoaJuridica
        fields: ClassVar[list[str]] = [
            "razao_social",
            "nome_fantasia",
            "cnpj",
            "inscricao_estadual",
            "inscricao_municipal",
            "data_fundacao",
            "ramo_atividade",
            "porte_empresa",
            "website",
            "email_financeiro",
            "telefone_financeiro",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "razao_social": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Empresa Ltda"},
            ),
            "nome_fantasia": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Nome Fantasia"},
            ),
            "cnpj": forms.TextInput(
                attrs={"class": "form-control wizard-field cnpj-mask", "placeholder": "00.000.000/0000-00"},
            ),
            "inscricao_estadual": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "000.000.000.000"},
            ),
            "inscricao_municipal": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "00000000"},
            ),
            "data_fundacao": forms.DateInput(attrs={"class": "form-control wizard-field", "type": "date"}),
            "ramo_atividade": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Ex: Comércio de produtos"},
            ),
            "porte_empresa": forms.Select(attrs={"class": "form-control wizard-field"}),
            "website": forms.URLInput(
                attrs={"class": "form-control wizard-field", "placeholder": "https://www.empresa.com.br"},
            ),
            "email_financeiro": forms.EmailInput(
                attrs={"class": "form-control wizard-field", "placeholder": "financeiro@empresa.com.br"},
            ),
            "telefone_financeiro": forms.TextInput(
                attrs={"class": "form-control wizard-field phone-mask", "placeholder": "(11) 99999-9999"},
            ),
        }

    def clean_cnpj(self) -> str | None:
        """Remove máscara e valida tamanho do CNPJ."""
        cnpj = self.cleaned_data.get("cnpj")
        if cnpj:
            cnpj_clean = "".join(filter(str.isdigit, cnpj))
            if len(cnpj_clean) != CNPJ_LENGTH:
                msg = _("CNPJ deve ter 14 dígitos")
                raise ValidationError(msg)
        return cnpj


class ClientePessoaFisicaWizardForm(forms.ModelForm):
    """STEP 1C: Dados complementares PF (baseado no form CORE)."""

    class Meta:
        """Configuração de campos e widgets para Pessoa Física."""

        model = PessoaFisica
        fields: ClassVar[list[str]] = [
            "nome_completo",
            "cpf",
            "rg",
            "data_nascimento",
            "sexo",
            "naturalidade",
            "nome_mae",
            "nome_pai",
            "estado_civil",
            "profissao",
            "nacionalidade",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "nome_completo": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Nome completo do cliente"},
            ),
            "cpf": forms.TextInput(
                attrs={"class": "form-control wizard-field cpf-mask", "placeholder": "000.000.000-00"},
            ),
            "rg": forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "00.000.000-0"}),
            "data_nascimento": forms.DateInput(attrs={"class": "form-control wizard-field", "type": "date"}),
            "sexo": forms.Select(attrs={"class": "form-control wizard-field"}),
            "naturalidade": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Cidade de nascimento"},
            ),
            "nome_mae": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Nome completo da mãe"},
            ),
            "nome_pai": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Nome completo do pai"},
            ),
            "estado_civil": forms.Select(attrs={"class": "form-control wizard-field"}),
            "profissao": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Profissão/Ocupação"},
            ),
            "nacionalidade": forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Brasileira"}),
        }

    def clean_cpf(self) -> str | None:
        """Remove máscara e valida tamanho do CPF."""
        cpf = self.cleaned_data.get("cpf")
        if cpf:
            cpf_clean = "".join(filter(str.isdigit, cpf))
            if len(cpf_clean) != CPF_LENGTH:
                msg = _("CPF deve ter 11 dígitos")
                raise ValidationError(msg)
        return cpf


class ClienteAddressWizardForm(forms.Form):
    """LEGADO (não utilizado).

    Mantido apenas por compatibilidade; TenantAddressWizardForm do CORE é usado
    no fluxo ativo. Pode ser removido após período de depreciação.
    """


class ClienteContactsWizardForm(forms.ModelForm):
    """LEGADO (não utilizado). Usar TenantContactsWizardForm (CORE)."""

    class Meta:
        """Meta vazia para compatibilidade (nenhum campo exposto)."""

        model = Cliente  # Mantido para compatibilidade
        fields: ClassVar[list[str]] = []


class ClienteDocumentsWizardForm(forms.Form):
    """DESCONTINUADO.

    Gestão de documentos movida para componente reutilizável do app
    'documentos'. Mantido vazio para não quebrar imports legados.
    """


class ClienteReviewWizardForm(forms.Form):
    """STEP 5: Confirmação final dos dados antes da persistência."""

    confirmar_dados = forms.BooleanField(
        required=True,
        label=_("Confirmo que todos os dados estão corretos"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input wizard-checkbox"}),
    )

    observacoes_finais = forms.CharField(
        required=False,
        label=_("Observações Finais"),
        widget=forms.Textarea(
            attrs={
                "class": "form-control wizard-field",
                "rows": 3,
                "placeholder": "Observações adicionais sobre o cliente...",
            },
        ),
    )
