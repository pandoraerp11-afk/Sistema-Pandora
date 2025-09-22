from datetime import timedelta

from django import forms
from django.utils import timezone

from servicos.models import Servico

from .models import Agendamento, Disponibilidade, Slot


class AgendamentoForm(forms.ModelForm):
    slot = forms.ModelChoiceField(
        queryset=Slot.objects.none(),
        required=False,
        label="Slot",
        help_text="Opcional: selecionando um slot, datas são preenchidas.",
    )
    servico = forms.ModelChoiceField(queryset=Servico.objects.none(), required=False, label="Serviço")

    class Meta:
        model = Agendamento
        fields = [
            "cliente",
            "profissional",
            "slot",
            "servico",
            "data_inicio",
            "data_fim",
            "origem",  # 'tipo_servico' removed
        ]
        widgets = {
            "data_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "data_fim": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if tenant:
            # Limitar slots futuros do tenant ainda ativos
            self.fields["slot"].queryset = Slot.objects.filter(
                tenant=tenant, ativo=True, horario__gte=timezone.now()
            ).order_by("horario")
            self.fields["cliente"].queryset = self.fields["cliente"].queryset.filter(tenant=tenant)
            # Filtrar profissionais que têm vínculo com o tenant
            self.fields["profissional"].queryset = self.fields["profissional"].queryset.filter(
                tenant_memberships__tenant=tenant
            )
            self.fields["servico"].queryset = Servico.objects.filter(
                tenant=tenant, ativo=True, is_clinical=True
            ).order_by("nome_servico")

    def clean(self):
        cleaned = super().clean()
        slot = cleaned.get("slot")
        data_inicio = cleaned.get("data_inicio")
        data_fim = cleaned.get("data_fim")
        if slot:
            # Ajustar data_inicio ao slot se divergente
            if not data_inicio:
                cleaned["data_inicio"] = slot.horario
            else:
                cleaned["data_inicio"] = slot.horario  # forçar alinhamento
            if not data_fim:
                cleaned["data_fim"] = slot.horario + timedelta(minutes=30)
        elif data_inicio and data_fim and data_fim <= data_inicio:
            self.add_error("data_fim", "Data fim deve ser maior que início")
        return cleaned


class DisponibilidadeForm(forms.ModelForm):
    class Meta:
        model = Disponibilidade
        fields = [
            "profissional",
            "data",
            "hora_inicio",
            "hora_fim",
            "duracao_slot_minutos",
            "capacidade_por_slot",
            "recorrente",
            "regra_recorrencia",
            "ativo",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields["profissional"].queryset = self.fields["profissional"].queryset.filter(
                tenant_memberships__tenant=tenant
            )

    def clean(self):
        cleaned = super().clean()
        hi = cleaned.get("hora_inicio")
        hf = cleaned.get("hora_fim")
        if hi and hf and hf <= hi:
            self.add_error("hora_fim", "Hora fim deve ser maior que início")
        return cleaned


class ReagendarForm(forms.Form):
    novo_slot = forms.ModelChoiceField(queryset=Slot.objects.none(), required=False, label="Novo Slot")
    nova_data_inicio = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    nova_data_fim = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    motivo = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields["novo_slot"].queryset = Slot.objects.filter(
                tenant=tenant, ativo=True, horario__gte=timezone.now()
            ).order_by("horario")

    def clean(self):
        cleaned = super().clean()
        slot = cleaned.get("novo_slot")
        di = cleaned.get("nova_data_inicio")
        df = cleaned.get("nova_data_fim")
        if slot:
            # datas virão do slot, ignorar se fornecidas
            cleaned["nova_data_inicio"] = slot.horario
            # estimar 30 min caso não fornecido (pode ser aprimorado usando duração disponibilidade)
            cleaned["nova_data_fim"] = slot.horario + timedelta(minutes=30)
        else:
            if not di or not df:
                raise forms.ValidationError("Forneça novo slot OU nova data início/fim")
            if df <= di:
                raise forms.ValidationError("Data fim deve ser maior que início")
        return cleaned
