"""Formulários do wizard de Fornecedores (endereços, contatos, config/unificado)."""

import re
from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from core.wizard_forms import (
    TenantContactsWizardForm,
    TenantPessoaFisicaWizardForm,
    TenantPessoaJuridicaWizardForm,
)

from .models import (
    Fornecedor,
)

# Observação: os formulários de Identificação do Step 1 (PF/PJ) agora são reutilizados do CORE
# via TenantPessoaJuridicaWizardForm e TenantPessoaFisicaWizardForm em fornecedores/wizard_views.py.
# Mantemos apenas os steps específicos do módulo fornecedores abaixo.


class FornecedorAddressWizardForm(forms.Form):
    """Form do step de endereços (principal + adicionais serializados)."""

    # Endereço principal
    logradouro = forms.CharField(max_length=255, label=_("Logradouro"))
    numero = forms.CharField(max_length=20, label=_("Número"))
    complemento = forms.CharField(max_length=100, required=False, label=_("Complemento"))
    bairro = forms.CharField(max_length=100, label=_("Bairro"))
    cidade = forms.CharField(max_length=100, label=_("Cidade"))
    uf = forms.CharField(max_length=2, label=_("UF"))
    cep = forms.CharField(max_length=9, label=_("CEP"))
    # Endereços adicionais (JSON opcional)
    additional_addresses_json = forms.CharField(required=False, widget=forms.HiddenInput())


class FornecedorContactsWizardForm(forms.Form):
    """Form legado simplificado de contatos (não estendido no fluxo atual)."""

    # Contato principal
    nome = forms.CharField(max_length=100, required=False, label=_("Nome do Contato"))
    email = forms.EmailField(required=False, label=_("E-mail"))
    telefone = forms.CharField(max_length=20, required=False, label=_("Telefone"))
    cargo = forms.CharField(max_length=100, required=False, label=_("Cargo"))
    # Contatos adicionais (JSON opcional)
    additional_contacts_json = forms.CharField(required=False, widget=forms.HiddenInput())


class FornecedorContactsExtendCoreForm(TenantContactsWizardForm):
    """Estende contatos do CORE adicionando campos dinâmicos (vendedores e funcionários)."""

    additional_vendors_json = forms.CharField(required=False, widget=forms.HiddenInput())
    additional_employees_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text=_("Contatos de funcionários para prestação de serviços (com cargo)."),
    )


class FornecedorReviewWizardForm(forms.Form):
    """Step de revisão final (confirmações e observações)."""

    confirmacao = forms.BooleanField(required=True, label=_("Confirmo que revisei os dados."))
    confirmar = forms.BooleanField(label=_("Confirmo os dados"), required=True)
    observacoes = forms.CharField(label=_("Observações"), widget=forms.Textarea(attrs={"rows": 3}), required=False)
    aceite_politica = forms.BooleanField(label=_("Aceito a política de privacidade"), required=True)


class FornecedorConfigWizardForm(forms.Form):
    """Step unificado de configurações + dados bancários."""

    tipo_fornecimento = forms.ChoiceField(
        choices=Fornecedor.TIPO_FORNECIMENTO_CHOICES,
        required=False,
        label=_("Tipo de Fornecimento"),
        widget=forms.Select,
    )
    prazo_pagamento_dias = forms.IntegerField(required=False, min_value=0, label=_("Prazo de Pagamento Padrão (dias)"))
    pedido_minimo = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        label=_("Pedido Mínimo (valor)"),
    )
    prazo_medio_entrega_dias = forms.IntegerField(required=False, min_value=0, label=_("Prazo Médio de Entrega (dias)"))
    # Campos bancários incorporados do antigo step de banking
    banco = forms.CharField(max_length=100, required=False, label=_("Banco"))
    agencia = forms.CharField(max_length=20, required=False, label=_("Agência"))
    conta = forms.CharField(max_length=20, required=False, label=_("Conta"))
    tipo_chave_pix = forms.CharField(max_length=50, required=False, label=_("Tipo de Chave PIX"))
    chave_pix = forms.CharField(max_length=255, required=False, label=_("Chave PIX"))
    additional_bank_json = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401 - uso deliberado de Any para compat.
        """Chama inicialização padrão e configura queryset dinâmica."""
        super().__init__(*args, **kwargs)
        self._configure_dynamic_queryset()

    def _configure_dynamic_queryset(self) -> None:
        """Configura queryset dinâmica de linhas fornecidas.

        Isolado para evitar assinatura extensa do __init__ e simplificar lint.
        """

    # Campos removidos (linhas_fornecidas, regioes_atendidas) nesta fase do projeto.
    # Nenhuma configuração adicional necessária.


class FornecedorDocumentsWizardForm(forms.Form):
    """Placeholder mantido por compatibilidade (step documentos agora dinâmico)."""

    # Render é totalmente dinâmico (JS) no step de documentos.


# -------------------------------
# Identificação (PF/PJ) com validação flexível
# Reutiliza os campos/UX do CORE, mas remove unicidade em Tenant
# -------------------------------


CPF_LEN = 11
CNPJ_LEN = 14


class FornecedorPFIdentificationForm(TenantPessoaFisicaWizardForm):
    """Identificação PF sem validação de unicidade no tenant (apenas formato)."""

    def clean_cpf(self) -> str | None:
        """Validar formato básico do CPF (apenas comprimento)."""
        cpf = self.cleaned_data.get("cpf")
        if cpf:
            cpf_digits = re.sub(r"\D", "", str(cpf))
            if len(cpf_digits) != CPF_LEN:
                raise forms.ValidationError(_("CPF inválido."))
        return cpf


class FornecedorPJIdentificationForm(TenantPessoaJuridicaWizardForm):
    """Identificação PJ sem validação de unicidade (somente formato)."""

    def clean_cnpj(self) -> str | None:
        """Validar formato básico do CNPJ (apenas comprimento)."""
        cnpj = self.cleaned_data.get("cnpj")
        if cnpj:
            cnpj_digits = re.sub(r"\D", "", str(cnpj))
            if len(cnpj_digits) != CNPJ_LEN:
                raise forms.ValidationError(_("CNPJ inválido."))
        return cnpj
