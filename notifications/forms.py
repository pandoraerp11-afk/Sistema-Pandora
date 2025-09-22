from django import forms
from django.contrib.auth import get_user_model

from .models import ConfiguracaoNotificacao, Notification, PreferenciaUsuarioNotificacao

User = get_user_model()


class NotificationForm(forms.ModelForm):
    """
    Formulário para criação e edição de notificações.
    """

    class Meta:
        model = Notification
        fields = ["titulo", "mensagem", "tipo", "prioridade", "data_expiracao", "url_acao", "modulo_origem"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Digite o título da notificação"}),
            "mensagem": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Digite a mensagem da notificação"}
            ),
            "tipo": forms.Select(attrs={"class": "form-control"}),
            "prioridade": forms.Select(attrs={"class": "form-control"}),
            "data_expiracao": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "url_acao": forms.URLInput(attrs={"class": "form-control", "placeholder": "URL de ação (opcional)"}),
            "modulo_origem": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Módulo de origem (opcional)"}
            ),
        }


class NotificationFilterForm(forms.Form):
    """
    Formulário para filtros de notificações.
    """

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Buscar por título ou mensagem..."}),
    )

    status = forms.ChoiceField(
        choices=[("", "Todos")] + Notification.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    tipo = forms.ChoiceField(
        choices=[("", "Todos os Tipos")] + Notification.TIPO_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    prioridade = forms.ChoiceField(
        choices=[("", "Todas as Prioridades")] + Notification.PRIORIDADE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class PreferenciaUsuarioNotificacaoForm(forms.ModelForm):
    """
    Formulário para preferências de notificação do usuário.
    """

    class Meta:
        model = PreferenciaUsuarioNotificacao
        fields = [
            "receber_notificacoes",
            "receber_info",
            "receber_warning",
            "receber_error",
            "receber_success",
            "receber_alert",
            "receber_baixa",
            "receber_media",
            "receber_alta",
            "receber_critica",
            "email_habilitado",
            "push_habilitado",
            "sms_habilitado",
        ]
        widgets = {
            "receber_notificacoes": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "receber_info": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "receber_warning": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "receber_error": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "receber_success": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "receber_alert": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "receber_baixa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "receber_media": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "receber_alta": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "receber_critica": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "email_habilitado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "push_habilitado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "sms_habilitado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ConfiguracaoNotificacaoForm(forms.ModelForm):
    """
    Formulário para configurações de notificação do tenant.
    """

    class Meta:
        model = ConfiguracaoNotificacao
        fields = [
            "dias_expiracao_padrao",
            "dias_retencao_lidas",
            "dias_retencao_arquivadas",
            "max_notificacoes_por_hora",
            "agrupar_notificacoes_similares",
            "email_habilitado",
            "push_habilitado",
            "sms_habilitado",
        ]
        widgets = {
            "dias_expiracao_padrao": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "dias_retencao_lidas": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "dias_retencao_arquivadas": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "max_notificacoes_por_hora": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "agrupar_notificacoes_similares": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "email_habilitado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "push_habilitado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "sms_habilitado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class NotificationBatchActionForm(forms.Form):
    """
    Formulário para ações em lote nas notificações.
    """

    ACTION_CHOICES = [
        ("mark_as_read", "Marcar como Lida"),
        ("mark_as_unread", "Marcar como Não Lida"),
        ("archive", "Arquivar"),
        ("delete", "Excluir"),
    ]

    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.Select(attrs={"class": "form-control"}))

    notification_ids = forms.CharField(widget=forms.HiddenInput())

    def clean_notification_ids(self):
        """
        Valida e converte os IDs das notificações.
        """
        ids_str = self.cleaned_data["notification_ids"]
        try:
            ids = [int(id_str.strip()) for id_str in ids_str.split(",") if id_str.strip()]
            return ids
        except ValueError:
            raise forms.ValidationError("IDs de notificação inválidos.")
