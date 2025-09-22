# apropriacao/forms.py
from django import forms

from .models import Apropriacao


class ApropriacaoForm(forms.ModelForm):
    class Meta:
        model = Apropriacao
        fields = "__all__"
        widgets = {
            "descricao": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Digite a descrição da apropriação..."}
            ),
            "obra": forms.Select(attrs={"class": "form-control select2", "data-placeholder": "Selecione uma obra..."}),
            "data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "responsavel": forms.Select(
                attrs={"class": "form-control select2", "data-placeholder": "Selecione um responsável..."}
            ),
            "observacoes": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Digite observações adicionais..."}
            ),
        }
        labels = {
            "descricao": "Descrição",
            "obra": "Obra",
            "data": "Data",
            "responsavel": "Responsável",
            "observacoes": "Observações",
        }
        help_texts = {
            "descricao": "Descrição clara e objetiva da apropriação",
            "obra": "Obra relacionada a esta apropriação",
            "data": "Data da apropriação",
            "responsavel": "Funcionário responsável pela apropriação (opcional)",
            "observacoes": "Informações adicionais sobre a apropriação (opcional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Aplicar classes CSS e configurações
        for _field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs["required"] = True
                field.label = f"{field.label} *"

            # Adicionar placeholder para campos de texto
            if isinstance(field.widget, forms.TextInput):
                field.widget.attrs["placeholder"] = f"Digite {field.label.lower()}..."

            # Configurar Select2 para campos de seleção
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] += " select2"
                field.empty_label = f"Selecione {field.label.lower()}..."

        # Configurações específicas por campo
        self.fields["descricao"].widget.attrs.update({"maxlength": 200, "autocomplete": "off"})

        # Tornar responsável opcional mais explícito
        self.fields["responsavel"].required = False
        self.fields["observacoes"].required = False

    def clean_descricao(self):
        descricao = self.cleaned_data.get("descricao")
        if descricao:
            descricao = descricao.strip()
            if len(descricao) < 5:
                raise forms.ValidationError("A descrição deve ter pelo menos 5 caracteres.")
        return descricao

    def clean_data(self):
        data = self.cleaned_data.get("data")
        if data:
            from datetime import date

            if data > date.today():
                # Permitir datas futuras, mas mostrar aviso
                pass
        return data
