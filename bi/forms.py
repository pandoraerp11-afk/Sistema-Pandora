# bi/forms.py
from django import forms
from django.contrib.auth import get_user_model

from .models import Indicador

User = get_user_model()


class IndicadorForm(forms.ModelForm):
    class Meta:
        model = Indicador
        fields = [
            "nome",
            "descricao",
            "valor",
            "meta",
            "data",
            "tipo",
            "periodo",
            "status",
            "unidade_medida",
            "responsavel",
            "observacoes",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome do indicador"}),
            "descricao": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Descrição do indicador"}
            ),
            "valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0,00"}),
            "meta": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "placeholder": "0,00 (opcional)"}
            ),
            "data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "periodo": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "unidade_medida": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex: %, R$, unidades, etc."}
            ),
            "responsavel": forms.Select(attrs={"class": "form-select"}),
            "observacoes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Observações adicionais (opcional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Melhorar a exibição dos usuários
        self.fields["responsavel"].queryset = User.objects.filter(is_active=True).order_by(
            "first_name", "last_name", "username"
        )

        # Personalizar labels
        self.fields["nome"].label = "Nome do Indicador"
        self.fields["descricao"].label = "Descrição"
        self.fields["valor"].label = "Valor Atual"
        self.fields["meta"].label = "Meta (Objetivo)"
        self.fields["data"].label = "Data"
        self.fields["tipo"].label = "Tipo de Indicador"
        self.fields["periodo"].label = "Período"
        self.fields["status"].label = "Status"
        self.fields["unidade_medida"].label = "Unidade de Medida"
        self.fields["responsavel"].label = "Responsável"
        self.fields["observacoes"].label = "Observações"

        # Campos obrigatórios
        self.fields["nome"].required = True
        self.fields["valor"].required = True
        self.fields["data"].required = True
        self.fields["tipo"].required = True
        self.fields["periodo"].required = True
        self.fields["status"].required = True

        # Help texts
        self.fields["meta"].help_text = "Defina uma meta para comparar o desempenho (opcional)"
        self.fields["unidade_medida"].help_text = "Ex: %, R$, unidades, kg, etc."
        self.fields["observacoes"].help_text = "Informações adicionais sobre o indicador"


class FiltroIndicadorForm(forms.Form):
    """Formulário para filtros na listagem de indicadores"""

    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Buscar por nome ou descrição..."}),
    )

    tipo = forms.ChoiceField(
        choices=[("", "Todos os Tipos")] + Indicador.TIPO_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    periodo = forms.ChoiceField(
        choices=[("", "Todos os Períodos")] + Indicador.PERIODO_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    status = forms.ChoiceField(
        choices=[("", "Todos os Status")] + Indicador.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    responsavel = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("first_name", "last_name", "username"),
        required=False,
        empty_label="Todos os Responsáveis",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    data_inicio = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )

    data_fim = forms.DateField(required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
