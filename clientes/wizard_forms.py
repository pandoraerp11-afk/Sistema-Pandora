# clientes/wizard_forms.py - Formulários específicos para o wizard de clientes
"""
Formulários adaptados do sistema de wizard do core para clientes
Reutiliza a estrutura existente com campos específicos de clientes
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.wizard_forms import (
    TenantPessoaFisicaWizardForm,
    TenantPessoaJuridicaWizardForm,
)

from .models import Cliente, PessoaFisica, PessoaJuridica


class ClientePFIdentificationForm(TenantPessoaFisicaWizardForm):
    """
    Step 1 (PF) reutilizando o form do CORE, mas sem checar unicidade no modelo Tenant.
    """

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf")
        if cpf:
            cpf_digits = "".join(ch for ch in str(cpf) if ch.isdigit())
            if len(cpf_digits) != 11:
                raise ValidationError(_("CPF deve ter 11 dígitos"))
        return cpf


class ClientePJIdentificationForm(TenantPessoaJuridicaWizardForm):
    """
    Step 1 (PJ) reutilizando o form do CORE, mas sem checar unicidade no modelo Tenant.
    """

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get("cnpj")
        if cnpj:
            cnpj_digits = "".join(ch for ch in str(cnpj) if ch.isdigit())
            if len(cnpj_digits) != 14:
                raise ValidationError(_("CNPJ deve ter 14 dígitos"))
        return cnpj


class ClientePessoaJuridicaWizardForm(forms.ModelForm):
    """
    STEP 1B: Formulário específico para Pessoa Jurídica (baseado no TenantPessoaJuridicaWizardForm)
    """

    class Meta:
        model = PessoaJuridica
        fields = [
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
        widgets = {
            "razao_social": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Empresa Ltda"}
            ),
            "nome_fantasia": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Nome Fantasia"}
            ),
            "cnpj": forms.TextInput(
                attrs={"class": "form-control wizard-field cnpj-mask", "placeholder": "00.000.000/0000-00"}
            ),
            "inscricao_estadual": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "000.000.000.000"}
            ),
            "inscricao_municipal": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "00000000"}
            ),
            "data_fundacao": forms.DateInput(attrs={"class": "form-control wizard-field", "type": "date"}),
            "ramo_atividade": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Ex: Comércio de produtos"}
            ),
            "porte_empresa": forms.Select(attrs={"class": "form-control wizard-field"}),
            "website": forms.URLInput(
                attrs={"class": "form-control wizard-field", "placeholder": "https://www.empresa.com.br"}
            ),
            "email_financeiro": forms.EmailInput(
                attrs={"class": "form-control wizard-field", "placeholder": "financeiro@empresa.com.br"}
            ),
            "telefone_financeiro": forms.TextInput(
                attrs={"class": "form-control wizard-field phone-mask", "placeholder": "(11) 99999-9999"}
            ),
        }

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get("cnpj")
        if cnpj:
            # Remover formatação para validação
            cnpj_clean = "".join(filter(str.isdigit, cnpj))
            if len(cnpj_clean) != 14:
                raise ValidationError("CNPJ deve ter 14 dígitos")
        return cnpj


class ClientePessoaFisicaWizardForm(forms.ModelForm):
    """
    STEP 1C: Formulário específico para Pessoa Física (baseado no TenantPessoaFisicaWizardForm)
    """

    class Meta:
        model = PessoaFisica
        fields = [
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
        widgets = {
            "nome_completo": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Nome completo do cliente"}
            ),
            "cpf": forms.TextInput(
                attrs={"class": "form-control wizard-field cpf-mask", "placeholder": "000.000.000-00"}
            ),
            "rg": forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "00.000.000-0"}),
            "data_nascimento": forms.DateInput(attrs={"class": "form-control wizard-field", "type": "date"}),
            "sexo": forms.Select(attrs={"class": "form-control wizard-field"}),
            "naturalidade": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Cidade de nascimento"}
            ),
            "nome_mae": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Nome completo da mãe"}
            ),
            "nome_pai": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Nome completo do pai"}
            ),
            "estado_civil": forms.Select(attrs={"class": "form-control wizard-field"}),
            "profissao": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Profissão/Ocupação"}
            ),
            "nacionalidade": forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Brasileira"}),
        }

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf")
        if cpf:
            # Remover formatação para validação
            cpf_clean = "".join(filter(str.isdigit, cpf))
            if len(cpf_clean) != 11:
                raise ValidationError("CPF deve ter 11 dígitos")
        return cpf


class ClienteAddressWizardForm(forms.Form):
    """
    LEGADO (não utilizado). Nos steps usaremos TenantAddressWizardForm do CORE.
    Mantido por compatibilidade, sem impacto no novo fluxo.
    """

    pass


class ClienteContactsWizardForm(forms.ModelForm):
    """
    LEGADO (não utilizado). Nos steps usaremos TenantContactsWizardForm do CORE.
    """

    class Meta:
        model = Cliente
        fields = []


class ClienteDocumentsWizardForm(forms.Form):
    """
    STEP 4: Documentos (baseado no TenantDocumentsWizardForm)
    """

    # Campos para upload de documentos opcionais
    documento_cpf_rg = forms.FileField(
        required=False,
        label=_("CPF/RG"),
        widget=forms.FileInput(attrs={"class": "form-control wizard-field", "accept": ".pdf,.jpg,.jpeg,.png"}),
    )

    comprovante_residencia = forms.FileField(
        required=False,
        label=_("Comprovante de Residência"),
        widget=forms.FileInput(attrs={"class": "form-control wizard-field", "accept": ".pdf,.jpg,.jpeg,.png"}),
    )

    contrato_social = forms.FileField(
        required=False,
        label=_("Contrato Social"),
        widget=forms.FileInput(attrs={"class": "form-control wizard-field", "accept": ".pdf,.jpg,.jpeg,.png"}),
    )

    cartao_cnpj = forms.FileField(
        required=False,
        label=_("Cartão CNPJ"),
        widget=forms.FileInput(attrs={"class": "form-control wizard-field", "accept": ".pdf,.jpg,.jpeg,.png"}),
    )


class ClienteReviewWizardForm(forms.Form):
    """
    STEP 5: Confirmação (baseado no TenantReviewWizardForm)
    """

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
            }
        ),
    )
