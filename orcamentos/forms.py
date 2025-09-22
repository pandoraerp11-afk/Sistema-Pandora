# orcamentos/forms.py
from django import forms

from .models import Orcamento  # CORRIGIDO para importar Orcamento (singular)


class OrcamentoForm(forms.ModelForm):  # CORRIGIDO para OrcamentoForm (singular)
    class Meta:
        model = Orcamento  # CORRIGIDO para Orcamento (singular)
        fields = "__all__"
        # Adicione widgets ou personalizações de campos se necessário
        # widgets = {
        #     'data_emissao': forms.DateInput(attrs={'type': 'date'}),
        # }
