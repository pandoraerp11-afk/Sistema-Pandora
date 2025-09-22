# formularios/forms.py
from django import forms

from .models import Formulario  # CORRIGIDO para importar Formulario (singular)


class FormularioForm(forms.ModelForm):  # CORRIGIDO para FormularioForm (singular)
    class Meta:
        model = Formulario  # CORRIGIDO para Formulario (singular)
        fields = "__all__"
        # Adicione widgets ou personalizações de campos se necessário
        # widgets = {
        #     'data_criacao': forms.DateInput(attrs={'type': 'date'}),
        # }
