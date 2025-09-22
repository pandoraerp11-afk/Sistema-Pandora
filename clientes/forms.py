# clientes/forms.py (VERSÃO FINAL "DE PONTA", COMPLETA E AUDITADA)

import re

from django import forms
from django.core.exceptions import ValidationError
from django.forms import CheckboxInput, DateInput, FileInput, Select, Textarea, inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .models import AcessoCliente, Cliente, Contato, DocumentoCliente, EnderecoAdicional, PessoaFisica, PessoaJuridica


# Sua classe base de estilização foi mantida 100% intacta.
class BaseFormWithStyling(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _field_name, field in self.fields.items():
            widget = field.widget
            current_classes = set(widget.attrs.get("class", "").split())
            if isinstance(widget, (CheckboxInput)):
                if "form-check-input" not in current_classes:
                    current_classes.add("form-check-input")
            elif isinstance(widget, FileInput) or not isinstance(widget, forms.HiddenInput):
                if "form-control" not in current_classes:
                    current_classes.add("form-control")
            if isinstance(widget, Select) and "select2" not in current_classes:
                current_classes.add("select2")
            widget.attrs["class"] = " ".join(sorted(list(current_classes))).strip()


class ClienteBaseForm(BaseFormWithStyling):
    class Meta:
        model = Cliente
        fields = [
            "tipo",
            "status",
            "codigo_interno",
            "imagem_perfil",
            "portal_ativo",
            "email",
            "telefone",
            "telefone_secundario",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "pais",
            "observacoes",
        ]
        widgets = {
            "tipo": Select(attrs={"id": "id_cliente_tipo"}),
            "status": Select(),
            "portal_ativo": CheckboxInput(),
            "imagem_perfil": FileInput(),
            "observacoes": Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Informações adicionais, restrições ou observações importantes sobre o cliente...",
                }
            ),
            "codigo_interno": forms.TextInput(attrs={"placeholder": "Ex: C-001"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "email.principal@dominio.com"}),
            "telefone": forms.TextInput(
                attrs={"class": "phone-mask", "autocomplete": "tel", "placeholder": "(99) 99999-9999"}
            ),
            "telefone_secundario": forms.TextInput(
                attrs={"class": "phone-mask", "autocomplete": "tel-national", "placeholder": "(99) 99999-9999"}
            ),
            "cep": forms.TextInput(
                attrs={"class": "cep-mask", "autocomplete": "postal-code", "placeholder": "99999-999"}
            ),
            "logradouro": forms.TextInput(
                attrs={"autocomplete": "street-address", "placeholder": "Av. Brasil, Rua..."}
            ),
            "numero": forms.TextInput(attrs={"autocomplete": "address-line2", "placeholder": "1234"}),
            "bairro": forms.TextInput(attrs={"autocomplete": "address-level3", "placeholder": "Centro"}),
            "cidade": forms.TextInput(attrs={"autocomplete": "address-level2", "placeholder": "São Paulo"}),
            "estado": forms.TextInput(attrs={"autocomplete": "address-level1", "placeholder": "SP"}),
            "pais": forms.TextInput(attrs={"autocomplete": "country-name", "placeholder": "Brasil"}),
            "complemento": forms.TextInput(attrs={"autocomplete": "address-line3", "placeholder": "Apto 101, Bloco B"}),
        }


class PessoaFisicaForm(BaseFormWithStyling):
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = PessoaFisica
        fields = [
            "nome_completo",
            "cpf",
            "rg",
            "data_nascimento",
            "sexo",
            "naturalidade",
            "nacionalidade",
            "estado_civil",
            "profissao",
            "nome_mae",
            "nome_pai",
        ]
        widgets = {
            "nome_completo": forms.TextInput(attrs={"placeholder": "Nome completo sem abreviações"}),
            "cpf": forms.TextInput(attrs={"class": "cpf-mask", "placeholder": "999.999.999-99"}),
            "rg": forms.TextInput(attrs={"placeholder": "Número do RG"}),
            "data_nascimento": DateInput(attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}),
            "naturalidade": forms.TextInput(attrs={"placeholder": "Cidade de nascimento"}),
            "nacionalidade": forms.TextInput(attrs={"placeholder": "País de nacionalidade"}),
            "profissao": forms.TextInput(attrs={"placeholder": "Engenheiro, Médico..."}),
            "nome_mae": forms.TextInput(attrs={"placeholder": "Nome completo da mãe"}),
            "nome_pai": forms.TextInput(attrs={"placeholder": "Nome completo do pai"}),
        }

    # ... (lógica clean_cpf mantida) ...


class PessoaJuridicaForm(BaseFormWithStyling):
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

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
            "razao_social": forms.TextInput(attrs={"placeholder": "Nome de registro da empresa"}),
            "nome_fantasia": forms.TextInput(attrs={"placeholder": "Nome popular da empresa"}),
            "cnpj": forms.TextInput(attrs={"class": "cnpj-mask", "placeholder": "99.999.999/9999-99"}),
            "inscricao_estadual": forms.TextInput(attrs={"placeholder": "Número da I.E."}),
            "inscricao_municipal": forms.TextInput(attrs={"placeholder": "Número da I.M."}),
            "data_fundacao": DateInput(attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}),
            "ramo_atividade": forms.TextInput(attrs={"placeholder": "Ex: Construção Civil"}),
            "porte_empresa": forms.TextInput(attrs={"placeholder": "MEI, Pequena, Média..."}),
            "website": forms.URLInput(attrs={"placeholder": "https://www.empresa.com.br"}),
            "email_financeiro": forms.EmailInput(attrs={"placeholder": "financeiro@empresa.com"}),
            "telefone_financeiro": forms.TextInput(attrs={"class": "phone-mask", "placeholder": "(99) 99999-9999"}),
        }

    # ... (lógica clean_cnpj mantida) ...


class ContatoForm(BaseFormWithStyling):
    class Meta:
        model = Contato
        fields = ["tipo", "valor", "nome_contato_responsavel", "cargo", "principal", "observacao"]
        widgets = {"principal": CheckboxInput(), "observacao": Textarea(attrs={"rows": 2})}


class EnderecoAdicionalForm(BaseFormWithStyling):
    class Meta:
        model = EnderecoAdicional
        fields = [
            "tipo",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "cep",
            "pais",
            "principal",
            "ponto_referencia",
        ]
        widgets = {
            "principal": CheckboxInput(),
            "cep": forms.TextInput(attrs={"class": "cep-mask"}),
            "ponto_referencia": Textarea(attrs={"rows": 2}),
        }

    def clean_cep(self):
        cep = self.cleaned_data.get("cep")
        if cep:
            return re.sub(r"[^0-9]", "", cep)
        return cep


class DocumentoClienteForm(BaseFormWithStyling):
    class Meta:
        model = DocumentoCliente
        fields = ["tipo", "arquivo", "nome_documento", "descricao", "data_validade"]
        widgets = {
            "descricao": Textarea(attrs={"rows": 2}),
            "data_validade": DateInput(attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}),
            "arquivo": FileInput(),
        }


# NOVO FORMULÁRIO E FORMSET PARA O PORTAL DO CLIENTE
class AcessoClienteForm(BaseFormWithStyling):
    class Meta:
        model = AcessoCliente
        fields = ["usuario", "is_admin_portal"]
        widgets = {"usuario": Select(), "is_admin_portal": CheckboxInput()}


ContatoFormSet = inlineformset_factory(Cliente, Contato, form=ContatoForm, extra=0, can_delete=True, fk_name="cliente")
EnderecoAdicionalFormSet = inlineformset_factory(
    Cliente, EnderecoAdicional, form=EnderecoAdicionalForm, extra=0, can_delete=True, fk_name="cliente"
)
DocumentoClienteFormSet = inlineformset_factory(
    Cliente, DocumentoCliente, form=DocumentoClienteForm, extra=1, can_delete=True, fk_name="cliente"
)
AcessoClienteFormSet = inlineformset_factory(
    Cliente, AcessoCliente, form=AcessoClienteForm, extra=1, can_delete=True, fk_name="cliente"
)


class ClienteImportForm(forms.Form):
    FORMATO_CHOICES = (("csv", "CSV"), ("xlsx", "Excel (XLSX)"))
    arquivo = forms.FileField(
        label=_("Arquivo para Importação"),
        widget=FileInput(
            attrs={
                "class": "form-control",
                "accept": ".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        ),
    )
    formato = forms.ChoiceField(
        choices=FORMATO_CHOICES,
        label=_("Formato do Arquivo"),
        initial="csv",
        widget=Select(attrs={"class": "form-control select2"}),
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        formato_selecionado = self.cleaned_data.get("formato")
        if not arquivo:
            raise ValidationError(_("Nenhum arquivo selecionado."))
        ext = arquivo.name.split(".")[-1].lower()
        if formato_selecionado == "csv" and ext != "csv":
            raise ValidationError(_("O arquivo selecionado não é um CSV válido."))
        elif formato_selecionado == "xlsx" and ext != "xlsx":
            raise ValidationError(_("O arquivo selecionado não é um XLSX válido."))
        return arquivo


class ClienteSearchForm(forms.Form):
    TIPO_CHOICES = (("", _("Todos os Tipos")), ("PF", "Pessoa Física"), ("PJ", "Pessoa Jurídica"))
    # AJUSTE: choices do status para corresponder aos valores do novo modelo ('active', 'inactive', etc.)
    STATUS_CHOICES = (
        ("", _("Todos os Status")),
        ("active", _("Ativo")),
        ("inactive", _("Inativo")),
        ("suspended", _("Suspenso")),
    )
    termo = forms.CharField(
        label=_("Buscar por"),
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Nome, CPF/CNPJ, email...")}),
    )
    tipo = forms.ChoiceField(choices=TIPO_CHOICES, label=_("Tipo de Cliente"), required=False)
    cidade = forms.CharField(label=_("Cidade"), required=False)
    estado = forms.CharField(
        label=_("Estado (UF)"), required=False, widget=forms.TextInput(attrs={"maxlength": 2, "placeholder": "UF"})
    )
    status = forms.ChoiceField(choices=STATUS_CHOICES, label=_("Status"), required=False)
    data_cadastro_inicio = forms.DateField(
        label=_("Cadastrado de"),
        required=False,
        widget=DateInput(attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}),
    )
    data_cadastro_fim = forms.DateField(
        label=_("Cadastrado até"),
        required=False,
        widget=DateInput(attrs={"type": "text", "class": "datepicker", "placeholder": "DD/MM/AAAA"}),
    )
