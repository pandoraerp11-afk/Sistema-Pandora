# sst/forms.py
from django import forms

from .models import DocumentoSST  # CORRIGIDO para importar DocumentoSST (singular)


class DocumentoSSTForm(forms.ModelForm):  # CORRIGIDO para DocumentoSSTForm (singular)
    class Meta:
        model = DocumentoSST  # CORRIGIDO para DocumentoSST (singular)
        fields = "__all__"
        # Adicione widgets ou personalizações de campos se necessário
        # widgets = {
        #     'data_criacao': forms.DateInput(attrs={'type': 'date'}),
        # }
