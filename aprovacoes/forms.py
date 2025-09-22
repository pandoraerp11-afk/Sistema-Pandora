# aprovacoes/forms.py
from django import forms
from django.contrib.auth import get_user_model

from .models import Aprovacao

User = get_user_model()


class AprovacaoForm(forms.ModelForm):
    class Meta:
        model = Aprovacao
        fields = ["titulo", "descricao", "tipo_aprovacao", "prioridade", "valor", "solicitante", "observacoes"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Digite o título da aprovação"}),
            "descricao": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Descreva detalhadamente a solicitação"}
            ),
            "tipo_aprovacao": forms.Select(attrs={"class": "form-select"}),
            "prioridade": forms.Select(attrs={"class": "form-select"}),
            "valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0,00"}),
            "solicitante": forms.Select(attrs={"class": "form-select"}),
            "observacoes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Observações adicionais (opcional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Melhorar a exibição dos usuários
        self.fields["solicitante"].queryset = User.objects.filter(is_active=True).order_by(
            "first_name", "last_name", "username"
        )

        # Personalizar labels
        self.fields["titulo"].label = "Título da Aprovação"
        self.fields["descricao"].label = "Descrição Detalhada"
        self.fields["tipo_aprovacao"].label = "Tipo de Aprovação"
        self.fields["prioridade"].label = "Prioridade"
        self.fields["valor"].label = "Valor (R$)"
        self.fields["solicitante"].label = "Solicitante"
        self.fields["observacoes"].label = "Observações"

        # Campos obrigatórios
        self.fields["titulo"].required = True
        self.fields["descricao"].required = True
        self.fields["tipo_aprovacao"].required = True
        self.fields["prioridade"].required = True
        self.fields["solicitante"].required = True

        # Help texts
        self.fields["valor"].help_text = "Digite o valor em reais (opcional)"
        self.fields["observacoes"].help_text = "Informações adicionais que podem ajudar na aprovação"


class FiltroAprovacaoForm(forms.Form):
    """Formulário para filtros na listagem de aprovações"""

    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Buscar por título, descrição ou solicitante..."}
        ),
    )

    status = forms.ChoiceField(
        choices=[("", "Todos os Status")] + Aprovacao.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    tipo = forms.ChoiceField(
        choices=[("", "Todos os Tipos")] + Aprovacao.TIPO_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    prioridade = forms.ChoiceField(
        choices=[("", "Todas as Prioridades")] + Aprovacao.PRIORIDADE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    solicitante = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("first_name", "last_name", "username"),
        required=False,
        empty_label="Todos os Solicitantes",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
