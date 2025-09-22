# agenda/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.forms import BasePandoraForm
from core.models import CustomUser
from core.utils import get_current_tenant

from .models import Evento, EventoLembrete


class EventoForm(BasePandoraForm):
    """Formulário para criar e editar eventos"""

    participantes = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="Participantes",
    )

    # Lembretes padrão (aplicados ao responsável e participantes)
    lembrete_15 = forms.BooleanField(
        required=False,
        initial=True,
        label="Lembrar 15 minutos antes",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    lembrete_60 = forms.BooleanField(
        required=False,
        initial=True,
        label="Lembrar 60 minutos antes",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Evento
        fields = [
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
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Título do evento"}),
            "descricao": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Descrição detalhada do evento"}
            ),
            "data_inicio": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "data_fim": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "dia_inteiro": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "prioridade": forms.Select(attrs={"class": "form-control"}),
            "tipo_evento": forms.Select(attrs={"class": "form-control"}),
            "local": forms.TextInput(attrs={"class": "form-control", "placeholder": "Local do evento"}),
            "responsavel": forms.Select(attrs={"class": "form-control select2"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Configurar queryset para usuários baseado no tenant
        user_qs = CustomUser.objects.all()
        if self.request:
            tenant = get_current_tenant(self.request)
            if tenant:
                # Filtrar usuários do tenant atual
                user_qs = CustomUser.objects.filter(tenant_memberships__tenant=tenant).distinct()

        self.fields["responsavel"].queryset = user_qs
        self.fields["participantes"].queryset = user_qs

        self.fields["responsavel"].empty_label = "Selecione um responsável"

        # Campo status não obrigatório para compat (tests não enviam)
        if "status" in self.fields:
            self.fields["status"].required = False
            # Se não veio no POST, definir initial para default do model
            if not self.data or "status" not in self.data:
                try:
                    default_status = Evento._meta.get_field("status").default or "agendado"
                except Exception:
                    default_status = "agendado"
                self.initial.setdefault("status", default_status)

        # Compat: se POST usou 'tipo' em vez de 'tipo_evento', mover dado
        if self.data and "tipo" in self.data and "tipo_evento" not in self.data:
            mutable = self.data._mutable if hasattr(self.data, "_mutable") else None
            try:
                if mutable is not None:
                    self.data._mutable = True
                self.data = self.data.copy()
                self.data["tipo_evento"] = self.data.get("tipo")
            finally:
                if mutable is not None:
                    self.data._mutable = mutable

        # Tornar campos obrigatórios
        self.fields["titulo"].required = True
        self.fields["data_inicio"].required = True

        # JavaScript para dia inteiro
        self.fields["dia_inteiro"].help_text = "Marque se o evento dura o dia todo"

        # Inicializar lembretes conforme já configurados para o responsável
        try:
            ev = self.instance if getattr(self, "instance", None) and getattr(self.instance, "pk", None) else None
            if ev and ev.responsavel_id:
                self.fields["lembrete_15"].initial = EventoLembrete.objects.filter(
                    evento=ev, usuario_id=ev.responsavel_id, minutos_antes=15, ativo=True
                ).exists()
                self.fields["lembrete_60"].initial = EventoLembrete.objects.filter(
                    evento=ev, usuario_id=ev.responsavel_id, minutos_antes=60, ativo=True
                ).exists()
        except Exception:
            # Em caso de erro de consulta, manter padrões
            pass

        # Integração com Chat: pré-preencher a partir de conversa_id
        try:
            if self.request:
                conversa_id = self.request.GET.get("conversa_id")
                if conversa_id and not self.instance.pk:
                    from chat.models import Conversa

                    conversa = Conversa.objects.get(id=conversa_id)
                    if not self.initial.get("titulo"):
                        self.initial["titulo"] = f"Reunião - {conversa.get_titulo_display()}"
                    # Pré-selecionar participantes da conversa
                    p_ids = list(conversa.participantes.values_list("id", flat=True))
                    if p_ids:
                        self.initial["participantes"] = p_ids
                    # Definir responsável padrão como usuário atual se não informado
                    if self.request.user and not self.initial.get("responsavel"):
                        self.initial["responsavel"] = self.request.user.id
        except Exception:
            # Silenciar qualquer falha de pré-preenchimento
            pass

    def clean(self):
        """Validações gerais do formulário"""
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get("data_inicio")
        data_fim = cleaned_data.get("data_fim")
        dia_inteiro = cleaned_data.get("dia_inteiro")
        responsavel = cleaned_data.get("responsavel")

        # Validar datas
        if data_inicio and data_fim and data_inicio >= data_fim:
            raise ValidationError("A data de fim deve ser posterior à data de início.")

        # Se é dia inteiro, não precisa de hora de fim
        if dia_inteiro and data_fim:
            # Ajustar para o final do dia
            data_fim = data_inicio.replace(hour=23, minute=59, second=59)
            cleaned_data["data_fim"] = data_fim

        # Validar data no passado (apenas para novos eventos)
        if data_inicio and not self.instance.pk and data_inicio < timezone.now():
            raise ValidationError("Não é possível criar eventos no passado.")

        # Validação de conflito de horários para o responsável
        if responsavel and data_inicio and data_fim:
            conflitos = Evento.objects.filter(responsavel=responsavel, status="pendente").exclude(
                pk=self.instance.pk if self.instance else None
            )

            # Verificar sobreposição
            for conflito in conflitos:
                if conflito.data_fim:
                    if data_inicio < conflito.data_fim and (data_fim or data_inicio) > conflito.data_inicio:
                        raise ValidationError(
                            f'Conflito de horário com o evento "{conflito.titulo}" '
                            f"({conflito.data_inicio.strftime('%d/%m/%Y %H:%M')})"
                        )

        return cleaned_data

    def clean_titulo(self):
        """Validar título único por dia e responsável"""
        titulo = self.cleaned_data.get("titulo")
        data_inicio = self.cleaned_data.get("data_inicio")
        responsavel = self.cleaned_data.get("responsavel")

        if titulo and data_inicio and responsavel:
            eventos_mesmo_dia = Evento.objects.filter(
                titulo=titulo, responsavel=responsavel, data_inicio__date=data_inicio.date()
            ).exclude(pk=self.instance.pk if self.instance else None)

            if eventos_mesmo_dia.exists():
                raise ValidationError("Já existe um evento com este título para este responsável no mesmo dia.")

        return titulo


class EventoBuscaForm(forms.Form):
    """Formulário para busca avançada de eventos"""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Buscar por título, descrição ou local"}),
        label="Buscar",
    )

    status = forms.ChoiceField(
        choices=[("", "Todos os status")] + Evento.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Status",
    )

    prioridade = forms.ChoiceField(
        choices=[("", "Todas as prioridades")] + Evento.PRIORIDADE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Prioridade",
    )

    responsavel = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        empty_label="Todos os responsáveis",
        widget=forms.Select(attrs={"class": "form-control select2"}),
        label="Responsável",
    )

    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Data início (de)",
    )

    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Data início (até)",
    )

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields["responsavel"].queryset = CustomUser.objects.filter(
                tenant_memberships__tenant=tenant
            ).distinct()


class EventoCalendarioForm(forms.ModelForm):
    """Formulário simplificado para criação rápida no calendário"""

    class Meta:
        model = Evento
        fields = ["titulo", "data_inicio", "data_fim", "dia_inteiro", "prioridade", "local"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Título do evento"}),
            "data_inicio": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "data_fim": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "dia_inteiro": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "prioridade": forms.Select(attrs={"class": "form-control"}),
            "local": forms.TextInput(attrs={"class": "form-control", "placeholder": "Local (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        self.fields["titulo"].required = True
        self.fields["data_inicio"].required = True


class EventoStatusForm(forms.Form):
    """Formulário para atualização rápida de status"""

    status = forms.ChoiceField(choices=Evento.STATUS_CHOICES, widget=forms.Select(attrs={"class": "form-control"}))

    observacao = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 2, "placeholder": "Observação sobre a mudança de status (opcional)"}
        ),
    )


class EventoFiltroRelatorioForm(forms.Form):
    """Formulário para filtros de relatório"""

    data_inicio = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}), label="Data início"
    )

    data_fim = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}), label="Data fim"
    )

    status = forms.MultipleChoiceField(
        choices=Evento.STATUS_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="Status",
    )

    prioridade = forms.MultipleChoiceField(
        choices=Evento.PRIORIDADE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="Prioridade",
    )

    responsavel = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="Responsáveis",
    )

    formato = forms.ChoiceField(
        choices=[
            ("html", "Visualizar na tela"),
            ("pdf", "Exportar PDF"),
            ("excel", "Exportar Excel"),
        ],
        initial="html",
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Formato",
    )

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields["responsavel"].queryset = CustomUser.objects.filter(
                tenant_memberships__tenant=tenant
            ).distinct()


class EventoRecorrenciaForm(forms.Form):
    """Formulário para eventos recorrentes"""

    TIPO_RECORRENCIA_CHOICES = [
        ("diario", "Diário"),
        ("semanal", "Semanal"),
        ("mensal", "Mensal"),
        ("anual", "Anual"),
    ]

    tipo_recorrencia = forms.ChoiceField(
        choices=TIPO_RECORRENCIA_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Tipo de recorrência",
    )

    intervalo = forms.IntegerField(
        min_value=1,
        max_value=365,
        initial=1,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Ex: 2 (a cada 2 dias/semanas/meses/anos)"}
        ),
        label="Intervalo",
        help_text="A cada quantos períodos repetir",
    )

    data_fim_recorrencia = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Data fim da recorrência",
    )

    numero_ocorrencias = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ex: 10 (criar 10 eventos)"}),
        label="Número de ocorrências",
    )

    def clean(self):
        cleaned_data = super().clean()
        data_fim_recorrencia = cleaned_data.get("data_fim_recorrencia")
        numero_ocorrencias = cleaned_data.get("numero_ocorrencias")

        if not data_fim_recorrencia and not numero_ocorrencias:
            raise ValidationError("Informe a data fim da recorrência OU o número de ocorrências.")

        if data_fim_recorrencia and numero_ocorrencias:
            raise ValidationError("Informe apenas a data fim da recorrência OU o número de ocorrências, não ambos.")

        return cleaned_data
