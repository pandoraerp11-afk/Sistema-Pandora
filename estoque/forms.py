from django import forms

from .models_movimento import Movimento


class MovimentoForm(forms.ModelForm):
    class Meta:
        model = Movimento
        fields = "__all__"
