# financeiro/forms.py
from django import forms

from core.forms import BasePandoraForm

from .models import ContaPagar, ContaReceber, Financeiro


class FinanceiroForm(BasePandoraForm):
    class Meta:
        model = Financeiro
        fields = "__all__"
        widgets = {
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "descricao": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "obra": forms.Select(attrs={"class": "form-select"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class ContaPagarForm(BasePandoraForm):
    class Meta:
        model = ContaPagar
        fields = "__all__"
        widgets = {
            "descricao": forms.TextInput(attrs={"class": "form-control"}),
            "fornecedor": forms.Select(attrs={"class": "form-select"}),
            "data_vencimento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "data_pagamento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class ContaReceberForm(BasePandoraForm):
    class Meta:
        model = ContaReceber
        fields = "__all__"
        widgets = {
            "descricao": forms.TextInput(attrs={"class": "form-control"}),
            "cliente": forms.Select(attrs={"class": "form-select"}),
            "data_vencimento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "data_recebimento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
