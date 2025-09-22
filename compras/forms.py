# compras/forms.py
from django import forms

from cadastros_gerais.forms import BasePandoraForm

from .models import Compra


class CompraForm(BasePandoraForm):
    class Meta:
        model = Compra
        fields = "__all__"
        widgets = {
            "data_pedido": forms.DateInput(attrs={"type": "date"}),
            "data_entrega_prevista": forms.DateInput(attrs={"type": "date"}),
            "data_entrega_real": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 4}),
            "condicoes_pagamento": forms.Textarea(attrs={"rows": 3}),
        }
