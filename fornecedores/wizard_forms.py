from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _

from cadastros_gerais.models import ItemAuxiliar
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
    # Contato principal
    nome = forms.CharField(max_length=100, required=False, label=_("Nome do Contato"))
    email = forms.EmailField(required=False, label=_("E-mail"))
    telefone = forms.CharField(max_length=20, required=False, label=_("Telefone"))
    cargo = forms.CharField(max_length=100, required=False, label=_("Cargo"))
    # Contatos adicionais (JSON opcional)
    additional_contacts_json = forms.CharField(required=False, widget=forms.HiddenInput())


class FornecedorContactsExtendCoreForm(TenantContactsWizardForm):
    """
    Extende o form de contatos do CORE para o módulo Fornecedores,
    adicionando um campo hidden para lista dinâmica de vendedores.
    """

    additional_vendors_json = forms.CharField(required=False, widget=forms.HiddenInput())
    additional_employees_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text=_("Contatos de funcionários para prestação de serviços (com cargo)."),
    )


class FornecedorBankingWizardForm(forms.Form):
    banco = forms.CharField(max_length=100, required=False, label=_("Banco"))
    agencia = forms.CharField(max_length=20, required=False, label=_("Agência"))
    conta = forms.CharField(max_length=20, required=False, label=_("Conta"))
    tipo_chave_pix = forms.CharField(max_length=50, required=False, label=_("Tipo de Chave PIX"))
    chave_pix = forms.CharField(max_length=255, required=False, label=_("Chave PIX"))
    # Contas adicionais (JSON opcional)
    additional_bank_json = forms.CharField(required=False, widget=forms.HiddenInput())


class FornecedorReviewWizardForm(forms.Form):
    confirmacao = forms.BooleanField(required=True, label=_("Confirmo que revisei os dados."))
    confirmar = forms.BooleanField(label=_("Confirmo os dados"), required=True)
    observacoes = forms.CharField(label=_("Observações"), widget=forms.Textarea(attrs={"rows": 3}), required=False)
    aceite_politica = forms.BooleanField(label=_("Aceito a política de privacidade"), required=True)


class FornecedorConfigWizardForm(forms.Form):
    tipo_fornecimento = forms.ChoiceField(
        choices=Fornecedor.TIPO_FORNECIMENTO_CHOICES,
        required=False,
        label=_("Tipo de Fornecimento"),
        help_text=_("Selecione se o fornecedor presta serviços, vende produtos ou ambos."),
        widget=forms.Select,
    )
    linhas_fornecidas = forms.ModelMultipleChoiceField(
        queryset=ItemAuxiliar.objects.none(),
        required=False,
        label=_("Linhas/Categorias Fornecidas"),
        help_text=_("Selecione as linhas/categorias que este fornecedor atende."),
        widget=forms.SelectMultiple(attrs={"size": 6}),
    )
    regioes_atendidas = forms.CharField(
        required=False,
        label=_("Regiões Atendidas (UFs/Cidades)"),
        help_text=_("Informe UFs e/ou cidades. Ex.: SP; RJ; Belo Horizonte/MG."),
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    prazo_pagamento_dias = forms.IntegerField(required=False, min_value=0, label=_("Prazo de Pagamento Padrão (dias)"))
    pedido_minimo = forms.DecimalField(
        required=False, min_value=0, max_digits=12, decimal_places=2, label=_("Pedido Mínimo (valor)")
    )
    prazo_medio_entrega_dias = forms.IntegerField(required=False, min_value=0, label=_("Prazo Médio de Entrega (dias)"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            # Filtrar itens aplicáveis a fornecedor
            qs = ItemAuxiliar.objects.filter(ativo=True)
            qs = qs.filter(models.Q(alvo="fornecedor") | models.Q(targets__code="fornecedor")).distinct()
            self.fields["linhas_fornecidas"].queryset = qs.order_by("categoria__ordem", "ordem", "nome")
        except Exception:
            pass


class FornecedorDocumentsWizardForm(forms.Form):
    pass


# -------------------------------
# Identificação (PF/PJ) com validação flexível
# Reutiliza os campos/UX do CORE, mas remove unicidade em Tenant
# -------------------------------


class FornecedorPFIdentificationForm(TenantPessoaFisicaWizardForm):
    def clean_cpf(self):
        # Apenas valida formato básico; não bloqueia por duplicidade no Tenant
        cpf = self.cleaned_data.get("cpf")
        if cpf:
            import re

            cpf_digits = re.sub(r"\D", "", str(cpf))
            if len(cpf_digits) != 11:
                raise forms.ValidationError(_("CPF inválido."))
        return cpf


class FornecedorPJIdentificationForm(TenantPessoaJuridicaWizardForm):
    def clean_cnpj(self):
        # Apenas valida formato básico; não bloqueia por duplicidade no Tenant
        cnpj = self.cleaned_data.get("cnpj")
        if cnpj:
            import re

            cnpj_digits = re.sub(r"\D", "", str(cnpj))
            if len(cnpj_digits) != 14:
                raise forms.ValidationError(_("CNPJ inválido."))
        return cnpj
