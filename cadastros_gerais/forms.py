# cadastros_gerais/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _

# Importa a base de formulários do app 'core'
from core.forms import BasePandoraForm

from .models import AlvoAplicacao, CategoriaAuxiliar, ItemAuxiliar, UnidadeMedida


class UnidadeMedidaForm(BasePandoraForm):
    class Meta:
        model = UnidadeMedida
        fields = ["nome", "simbolo", "descricao"]
        labels = {
            "nome": _("Nome da Unidade"),
            "simbolo": _("Símbolo (ex: m², un, vb)"),
            "descricao": _("Descrição (Opcional)"),
        }


class UnidadeMedidaImportForm(forms.Form):
    """
    Formulário para o upload do arquivo de importação de unidades de medida.
    """

    arquivo = forms.FileField(
        label=_("Arquivo CSV"), widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv"})
    )


class TipoDocumentoForm(forms.ModelForm):
    class Meta:
        model = ItemAuxiliar
        fields = [
            "categoria",
            "nome",
            "descricao",
            "alvo",
            "targets",
            "ativo",
            "versionavel",
            "periodicidade",
            "ordem",
            "config",
        ]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "alvo": forms.Select(attrs={"class": "form-select"}),
            "targets": forms.SelectMultiple(attrs={"class": "form-select"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "versionavel": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "periodicidade": forms.Select(attrs={"class": "form-select"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control"}),
            "config": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra apenas categorias de documento
        self.fields["categoria"].queryset = CategoriaAuxiliar.objects.filter(slug__icontains="documento")
        self.fields["targets"].queryset = AlvoAplicacao.objects.all()
