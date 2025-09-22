# mao_obra/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _

from funcionarios.models import Funcionario
from obras.models import Obra

from .models import MaoObra


class MaoObraForm(forms.ModelForm):
    class Meta:
        model = MaoObra
        fields = ["funcionario", "obra", "data", "atividade", "horas_trabalhadas", "valor_hora", "observacoes"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "atividade": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Descreva a atividade realizada..."}
            ),
            "horas_trabalhadas": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.5", "min": "0.5", "max": "24"}
            ),
            "valor_hora": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "observacoes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Observações adicionais sobre o trabalho realizado...",
                }
            ),
            "funcionario": forms.Select(attrs={"class": "form-select"}),
            "obra": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "funcionario": _("Funcionário"),
            "obra": _("Obra"),
            "data": _("Data"),
            "atividade": _("Atividade"),
            "horas_trabalhadas": _("Horas Trabalhadas"),
            "valor_hora": _("Valor por Hora"),
            "observacoes": _("Observações"),
        }
        help_texts = {
            "horas_trabalhadas": _("Informe as horas trabalhadas (ex: 8.5 para 8 horas e 30 minutos)"),
            "valor_hora": _("Valor pago por hora trabalhada"),
            "observacoes": _("Informações complementares sobre as atividades realizadas"),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            # Filtrar funcionários e obras por tenant
            self.fields["funcionario"].queryset = Funcionario.objects.filter(tenant=tenant, ativo=True).order_by(
                "nome_completo"
            )

            self.fields["obra"].queryset = Obra.objects.filter(tenant=tenant, ativo=True).order_by("nome")

        # Adicionar classes CSS personalizadas
        for field_name, field in self.fields.items():
            if field_name in ["funcionario", "obra"]:
                field.widget.attrs.update({"class": field.widget.attrs.get("class", "") + " select2"})

    def clean_horas_trabalhadas(self):
        horas = self.cleaned_data.get("horas_trabalhadas")
        if horas and horas <= 0:
            raise forms.ValidationError(_("As horas trabalhadas devem ser maior que zero."))
        if horas and horas > 24:
            raise forms.ValidationError(_("As horas trabalhadas não podem exceder 24 horas por dia."))
        return horas

    def clean_valor_hora(self):
        valor = self.cleaned_data.get("valor_hora")
        if valor and valor <= 0:
            raise forms.ValidationError(_("O valor por hora deve ser maior que zero."))
        return valor

    def clean(self):
        cleaned_data = super().clean()
        funcionario = cleaned_data.get("funcionario")
        obra = cleaned_data.get("obra")
        data = cleaned_data.get("data")

        # Validar se não existe registro duplicado no mesmo dia
        if funcionario and obra and data:
            existing = MaoObra.objects.filter(funcionario=funcionario, obra=obra, data=data)

            # Se estamos editando, excluir o próprio registro da validação
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise forms.ValidationError(
                    _("Já existe um registro de mão de obra para este funcionário nesta obra na data selecionada.")
                )

        return cleaned_data
