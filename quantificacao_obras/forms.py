from django import forms

from .models import AnexoQuantificacao, ItemQuantificacao, ProjetoQuantificacao


class ProjetoQuantificacaoForm(forms.ModelForm):
    class Meta:
        model = ProjetoQuantificacao
        fields = ["nome", "descricao", "data_inicio", "data_previsao_conclusao", "status"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "data_inicio": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "data_previsao_conclusao": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }


class ItemQuantificacaoForm(forms.ModelForm):
    class Meta:
        model = ItemQuantificacao
        fields = ["nome", "unidade_medida", "quantidade", "custo_unitario", "observacoes", "tipo_item"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "unidade_medida": forms.TextInput(attrs={"class": "form-control"}),
            "quantidade": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "custo_unitario": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "tipo_item": forms.Select(attrs={"class": "form-control"}),
        }


class AnexoQuantificacaoForm(forms.ModelForm):
    class Meta:
        model = AnexoQuantificacao
        fields = ["arquivo", "observacoes"]
        widgets = {
            "arquivo": forms.FileInput(attrs={"class": "form-control-file"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
