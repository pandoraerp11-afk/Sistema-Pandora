from django import forms

from .models import CategoriaDocumento, Documento, DocumentoVersao, DominioDocumento, RegraDocumento, TipoDocumento


class CategoriaDocumentoForm(forms.ModelForm):
    class Meta:
        model = CategoriaDocumento
        fields = ["nome", "descricao", "ativo"]  # campo ordem gerenciado automaticamente via DnD
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class TipoDocumentoForm(forms.ModelForm):
    class Meta:
        model = TipoDocumento
        fields = ["nome", "descricao", "categoria", "periodicidade", "ativo", "versionavel"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "periodicidade": forms.Select(attrs={"class": "form-select"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "versionavel": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["tipo", "periodicidade_aplicada", "obrigatorio", "observacao"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "periodicidade_aplicada": forms.Select(attrs={"class": "form-select"}),
            "obrigatorio": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "observacao": forms.TextInput(attrs={"class": "form-control"}),
        }


class RegraDocumentoForm(forms.ModelForm):
    class Meta:
        model = RegraDocumento
        fields = [
            "tipo",
            "nivel_aplicacao",
            "dominio",
            "tenant",
            "escopo",
            "filtro_tipo_fornecimento",
            "periodicidade_override",
            "exigencia",
            "validade_dias",
            "data_base",
            "observacoes",
            "ativo",
            "status",
        ]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "nivel_aplicacao": forms.Select(attrs={"class": "form-select"}),
            "dominio": forms.Select(attrs={"class": "form-select"}),
            "tenant": forms.Select(attrs={"class": "form-select"}),
            "escopo": forms.Select(attrs={"class": "form-select"}),
            "filtro_tipo_fornecimento": forms.Select(attrs={"class": "form-select"}),
            "periodicidade_override": forms.Select(attrs={"class": "form-select"}),
            "exigencia": forms.Select(attrs={"class": "form-select"}),
            "validade_dias": forms.NumberInput(attrs={"class": "form-control"}),
            "data_base": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.TextInput(attrs={"class": "form-control"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # Limita dominios ativos
        self.fields["dominio"].queryset = DominioDocumento.objects.filter(ativo=True).order_by("nome")
        # Usuário não admin não pode escolher status diferente nem criar global
        if user and not user.is_superuser:
            self.fields["status"].disabled = True
            self.fields["status"].initial = "pendente"
            # Oculta tenant no form para usuários normais
            self.fields["tenant"].widget = forms.HiddenInput()


class DocumentoVersaoForm(forms.ModelForm):
    class Meta:
        model = DocumentoVersao
        fields = ["arquivo", "competencia", "observacao", "validade_data"]
        widgets = {
            "arquivo": forms.FileInput(attrs={"class": "form-control"}),
            "competencia": forms.TextInput(attrs={"class": "form-control", "placeholder": "MM/AAAA"}),
            "observacao": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "validade_data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }


class DominioDocumentoForm(forms.ModelForm):
    class Meta:
        model = DominioDocumento
        fields = ["nome", "slug", "app_label", "descricao", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "app_label": forms.TextInput(attrs={"class": "form-control"}),
            "descricao": forms.TextInput(attrs={"class": "form-control"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
