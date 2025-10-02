"""Formulários residuais do app clientes.

Este módulo foi reduzido: criação/edição de clientes (e dados PF/PJ, contatos,
endereços e documentos) agora é totalmente tratada pelo fluxo de wizard em
`wizard_forms.py` + `wizard_views.py` e pelos serviços centrais.

Mantemos aqui apenas:
    - BaseFormWithStyling (utilitária, ainda usada em alguns pontos legados)
    - Formsets para contatos, endereços e acessos quando exibidos em telas fora do wizard
    - Formulários utilitários: importação em massa e busca

Qualquer lógica de validação ou inclusão de campos de criação principal deve ir
para o wizard. Evita-se duplicidade e divergência de regras.
"""

from __future__ import annotations

import re
from typing import ClassVar

from django import forms
from django.core.exceptions import ValidationError
from django.forms import CheckboxInput, DateInput, FileInput, Select, Textarea, inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .models import AcessoCliente, Cliente, Contato, EnderecoAdicional


# Sua classe base de estilização foi mantida 100% intacta.
class StylingMixin:
    """Mixin que injeta classes padrão nos widgets no momento da criação da subclasse.

    Evita override de __init__ (que gerava conflitos de tipagem/lint) e garante
    que cada campo definido na classe receba as classes utilitárias desejadas
    uma única vez.
    """

    @classmethod
    def __init_subclass__(cls, **kwargs: object) -> None:
        """Aplica classes CSS padrão aos widgets base quando a subclasse é criada."""
        super().__init_subclass__(**kwargs)
        base_fields = getattr(cls, "base_fields", {})  # forms.Form / ModelForm
        for field in base_fields.values():
            widget = field.widget
            classes = set(filter(None, widget.attrs.get("class", "").split()))
            if isinstance(widget, CheckboxInput):
                classes.add("form-check-input")
            elif isinstance(widget, FileInput) or not isinstance(widget, forms.HiddenInput):
                classes.add("form-control")
            if isinstance(widget, Select):
                classes.add("select2")
            widget.attrs["class"] = " ".join(sorted(classes)).strip()


class ContatoForm(StylingMixin, forms.ModelForm):
    """Form para edição isolada de contatos adicionais fora do wizard."""

    class Meta:
        """Metadados do ModelForm de contato."""

        model = Contato
        fields: ClassVar[list[str]] = ["tipo", "valor", "nome_contato_responsavel", "cargo", "principal", "observacao"]
        widgets: ClassVar[dict[str, object]] = {"principal": CheckboxInput(), "observacao": Textarea(attrs={"rows": 2})}


class EnderecoAdicionalForm(StylingMixin, forms.ModelForm):
    """Form para edição de endereços adicionais em telas legadas."""

    class Meta:
        """Metadados do ModelForm de endereço adicional."""

        model = EnderecoAdicional
        fields: ClassVar[list[str]] = [
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
        widgets: ClassVar[dict[str, object]] = {
            "principal": CheckboxInput(),
            "cep": forms.TextInput(attrs={"class": "cep-mask"}),
            "ponto_referencia": Textarea(attrs={"rows": 2}),
        }

    def clean_cep(self) -> str | None:
        """Remove caracteres não numéricos do CEP mantendo apenas dígitos."""
        cep = self.cleaned_data.get("cep")
        return re.sub(r"[^0-9]", "", cep) if cep else cep


# NOVO FORMULÁRIO E FORMSET PARA O PORTAL DO CLIENTE
class AcessoClienteForm(StylingMixin, forms.ModelForm):
    """Form para gerenciar acessos de usuários ao portal do cliente."""

    class Meta:
        """Metadados do form de acesso ao portal."""

        model = AcessoCliente
        fields: ClassVar[list[str]] = ["usuario", "is_admin_portal"]
        widgets: ClassVar[dict[str, object]] = {"usuario": Select(), "is_admin_portal": CheckboxInput()}


ContatoFormSet = inlineformset_factory(Cliente, Contato, form=ContatoForm, extra=0, can_delete=True, fk_name="cliente")
EnderecoAdicionalFormSet = inlineformset_factory(
    Cliente,
    EnderecoAdicional,
    form=EnderecoAdicionalForm,
    extra=0,
    can_delete=True,
    fk_name="cliente",
)
AcessoClienteFormSet = inlineformset_factory(
    Cliente,
    AcessoCliente,
    form=AcessoClienteForm,
    extra=1,
    can_delete=True,
    fk_name="cliente",
)


class ClienteImportForm(StylingMixin, forms.Form):
    """Form para upload e validação de arquivo de importação de clientes."""

    FORMATO_CHOICES = (("csv", "CSV"), ("xlsx", "Excel (XLSX)"))
    arquivo = forms.FileField(
        label=_("Arquivo para Importação"),
        widget=FileInput(
            attrs={
                "class": "form-control",
                "accept": ".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        ),
    )
    formato = forms.ChoiceField(
        choices=FORMATO_CHOICES,
        label=_("Formato do Arquivo"),
        initial="csv",
        widget=Select(attrs={"class": "form-control select2"}),
    )

    def clean_arquivo(self) -> object:
        """Valida extensão coerente com o formato selecionado pelo usuário."""
        arquivo = self.cleaned_data.get("arquivo")
        formato_selecionado = self.cleaned_data.get("formato")
        if not arquivo:
            raise ValidationError(_("Nenhum arquivo selecionado."))
        ext = arquivo.name.split(".")[-1].lower()
        if formato_selecionado == "csv" and ext != "csv":
            raise ValidationError(_("O arquivo selecionado não é um CSV válido."))
        if formato_selecionado == "xlsx" and ext != "xlsx":
            raise ValidationError(_("O arquivo selecionado não é um XLSX válido."))
        return arquivo


class ClienteSearchForm(StylingMixin, forms.Form):
    """Form auxiliar para filtros de busca de clientes em listagens."""

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
        label=_("Estado (UF)"),
        required=False,
        widget=forms.TextInput(attrs={"maxlength": 2, "placeholder": "UF"}),
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
