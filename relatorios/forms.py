# relatorios/forms.py
from django import forms

from .models import Relatorio  # CORRIGIDO para importar Relatorio (singular)


class RelatorioForm(forms.ModelForm):  # CORRIGIDO para RelatorioForm (singular)
    class Meta:
        model = Relatorio  # CORRIGIDO para Relatorio (singular)
        fields = "__all__"
        # Adicione widgets ou personalizações de campos se necessário
        # widgets = {
        #     'data_criacao': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        # }
