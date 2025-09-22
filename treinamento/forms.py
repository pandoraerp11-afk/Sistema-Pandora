# treinamento/forms.py
from django import forms

from .models import Treinamento  # CORRIGIDO para importar de .models (era .treinamento.models)


class TreinamentoForm(forms.ModelForm):  # Nome da classe já estava correto
    class Meta:
        model = Treinamento  # Referência ao modelo já estava correta
        fields = "__all__"
        # Adicione widgets ou personalizações de campos se necessário
        # widgets = {
        #     'data_inicio': forms.DateInput(attrs={'type': 'date'}),
        #     'data_fim': forms.DateInput(attrs={'type': 'date'}),
        # }
