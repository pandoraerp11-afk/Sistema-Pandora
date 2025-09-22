from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import Anamnese, Atendimento, FotoEvolucao, PerfilClinico

# Modelo Paciente removido: formulários relacionados eliminados.


class AtendimentoForm(forms.ModelForm):
    class Meta:
        model = Atendimento
        fields = "__all__"
        exclude = ("tenant",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Permitir múltiplos formatos e tornar não obrigatório (validado em clean)
        if "data_atendimento" in self.fields:
            self.fields["data_atendimento"].required = False
            self.fields["data_atendimento"].input_formats = [
                "%Y-%m-%d %H:%M:%S",  # usado nos testes
                "%Y-%m-%dT%H:%M",  # input type=datetime-local
                "%d/%m/%Y %H:%M",
            ]
        # O campo de slot foi removido do modelo
        self.fields.pop("slot", None)

    def clean(self):
        cleaned = super().clean()
        data_atendimento = cleaned.get("data_atendimento")

        # Exigir data/hora manual
        if not data_atendimento:
            raise ValidationError("A Data/Hora do atendimento é obrigatória.")

        # Validar coerência financeira
        valor = cleaned.get("valor_cobrado")
        desconto = cleaned.get("desconto_aplicado") or Decimal("0")
        if valor is not None and desconto is not None:
            try:
                if Decimal(desconto) > Decimal(valor):
                    raise ValidationError("Desconto não pode ser maior que o valor cobrado.")
            except Exception:
                pass
        return cleaned


class FotoEvolucaoForm(forms.ModelForm):
    class Meta:
        model = FotoEvolucao
        fields = "__all__"
        exclude = ("tenant", "imagem_thumbnail")


class AnamneseForm(forms.ModelForm):
    class Meta:
        model = Anamnese
        fields = "__all__"
        exclude = ("tenant", "data_preenchimento", "aprovada_por", "data_aprovacao")


"""Form de Disponibilidade removido deste módulo (centralização na Agenda)."""


class PerfilClinicoForm(forms.ModelForm):
    class Meta:
        model = PerfilClinico
        fields = "__all__"
        exclude = ("tenant", "pessoa_fisica")
