# agenda/forms.py
"""Formulários para o módulo de agenda."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.forms import BasePandoraForm
from core.models import CustomUser
from core.utils import get_current_tenant

from .models import Evento, EventoLembrete

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from django.http import HttpRequest
    from django.http.request import QueryDict


class EventoForm(BasePandoraForm):
    """Formulário para criar e editar eventos."""

    # Anotação de tipo para self.data
    data: QueryDict | None

    participantes: ClassVar[forms.ModelMultipleChoiceField] = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "form-check-input"},
        ),
        label="Participantes",
    )

    # Lembretes padrão (aplicados ao responsável e participantes)
    lembrete_15: ClassVar[forms.BooleanField] = forms.BooleanField(
        required=False,
        initial=True,
        label="Lembrar 15 minutos antes",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    lembrete_60: ClassVar[forms.BooleanField] = forms.BooleanField(
        required=False,
        initial=True,
        label="Lembrar 60 minutos antes",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        """Metadados para o EventoForm."""

        model = Evento
        fields: ClassVar[list[str]] = [
            "titulo",
            "descricao",
            "data_inicio",
            "data_fim",
            "dia_inteiro",
            "status",
            "prioridade",
            "tipo_evento",
            "local",
            "responsavel",
            "participantes",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "titulo": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Título do evento"},
            ),
            "descricao": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Descrição detalhada do evento",
                },
            ),
            "data_inicio": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
            ),
            "data_fim": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
            ),
            "dia_inteiro": forms.CheckboxInput(
                attrs={"class": "form-check-input"},
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
            "prioridade": forms.Select(attrs={"class": "form-control"}),
            "tipo_evento": forms.Select(attrs={"class": "form-control"}),
            "local": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Local do evento"},
            ),
            "responsavel": forms.Select(attrs={"class": "form-control select2"}),
        }

    def __init__(
        self,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Inicializa o formulário e ajusta os querysets."""
        self.request: HttpRequest | None = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        user_qs = self._get_user_queryset()
        self.fields["responsavel"].queryset = user_qs
        self.fields["participantes"].queryset = user_qs
        self.fields["responsavel"].empty_label = "Selecione um responsável"

        self._set_default_status()
        self._handle_legacy_tipo_field()

    def _get_user_queryset(self) -> QuerySet[CustomUser]:
        """Retorna o queryset de usuários filtrado pelo tenant."""
        if self.request:
            tenant = get_current_tenant(self.request)
            if tenant:
                return CustomUser.objects.filter(
                    tenant_memberships__tenant=tenant,
                ).distinct()
        return CustomUser.objects.all()

    def _set_default_status(self) -> None:
        """Define o status padrão se não for fornecido."""
        if "status" in self.fields:
            self.fields["status"].required = False
            # Acessa o campo do modelo de forma segura
            model_field = self.Meta.model._meta.get_field("status")  # noqa: SLF001
            default_status = getattr(model_field, "default", "agendado")
            self.initial.setdefault("status", default_status)

    def _handle_legacy_tipo_field(self) -> None:
        """Lida com o campo legado 'tipo' para compatibilidade."""
        # Garante que self.data não é None antes de prosseguir.
        if self.data is None:
            return

        # Agora que sabemos que self.data não é None, podemos usá-lo.
        if "tipo" in self.data and "tipo_evento" not in self.data:
            data = self.data.copy()
            data["tipo_evento"] = data["tipo"]
            self.data = data

    def clean(self) -> dict[str, Any]:
        """Valida os dados do formulário."""
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get("data_inicio")
        data_fim = cleaned_data.get("data_fim")
        dia_inteiro = cleaned_data.get("dia_inteiro")
        responsavel = cleaned_data.get("responsavel")

        # Validar datas
        if data_inicio and data_fim and data_inicio >= data_fim:
            msg = "A data de fim deve ser posterior à data de início."
            raise ValidationError(msg)

        # Se é dia inteiro, ajusta a hora de fim
        if dia_inteiro and data_inicio:
            data_fim = data_inicio.replace(hour=23, minute=59, second=59)
            cleaned_data["data_fim"] = data_fim

        # Validar data no passado (apenas para novos eventos)
        if data_inicio and not self.instance.pk and data_inicio < timezone.now():
            msg = "Não é possível criar eventos no passado."
            raise ValidationError(msg)

        # Validação de conflito de horários para o responsável
        if responsavel and data_inicio and data_fim:
            conflitos = Evento.objects.filter(
                responsavel=responsavel,
                status="pendente",
            ).exclude(pk=self.instance.pk if self.instance else None)

            # Verificar sobreposição
            for conflito in conflitos:
                if conflito.data_fim and data_inicio < conflito.data_fim and data_fim > conflito.data_inicio:
                    msg = (
                        f'Conflito de horário com o evento "{conflito.titulo}" '
                        f"({conflito.data_inicio.strftime('%d/%m/%Y %H:%M')})"
                    )
                    raise ValidationError(msg)

        return cleaned_data

    def clean_titulo(self) -> str | None:
        """Validar título único por dia e responsável."""
        titulo = self.cleaned_data.get("titulo")
        data_inicio = self.cleaned_data.get("data_inicio")
        responsavel = self.cleaned_data.get("responsavel")

        if titulo and data_inicio and responsavel:
            eventos_mesmo_dia = Evento.objects.filter(
                titulo=titulo,
                responsavel=responsavel,
                data_inicio__date=data_inicio.date(),
            ).exclude(pk=self.instance.pk if self.instance else None)

            if eventos_mesmo_dia.exists():
                msg = "Já existe um evento com este título para este responsável no mesmo dia."
                raise ValidationError(msg)

        return titulo

    def save(self, *, commit: bool = True) -> Evento:
        """Salva o evento e seus lembretes."""
        instance: Evento = super().save(commit=False)

        if commit:
            instance.save()
            self.save_m2m()  # Salva os participantes
            self._create_reminders(instance)

        return instance

    def _create_reminders(self, evento: Evento) -> None:
        """Cria lembretes para o evento."""
        lembretes_a_criar = []
        participantes = list(evento.participantes.all())
        if evento.responsavel:
            participantes.append(evento.responsavel)

        # Garante que os usuários sejam únicos
        for user in set(participantes):
            if self.cleaned_data.get("lembrete_15"):
                lembretes_a_criar.append(
                    EventoLembrete(
                        evento=evento,
                        usuario=user,
                        minutos_antes=15,
                    ),
                )
            if self.cleaned_data.get("lembrete_60"):
                lembretes_a_criar.append(
                    EventoLembrete(
                        evento=evento,
                        usuario=user,
                        minutos_antes=60,
                    ),
                )

        if lembretes_a_criar:
            EventoLembrete.objects.bulk_create(lembretes_a_criar)


class AgendamentoForm(forms.ModelForm):
    """Formulário para criar e editar agendamentos (definido no app agendamentos)."""
