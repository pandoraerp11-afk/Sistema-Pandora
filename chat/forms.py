from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Field, Layout, Row, Submit
from django import forms
from django.contrib.auth import get_user_model

from .models import ConfiguracaoChat, Conversa, Mensagem, PreferenciaUsuarioChat

User = get_user_model()


class ConversaForm(forms.ModelForm):
    """Form para criar/editar conversas"""

    participantes_selecionados = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(), widget=forms.CheckboxSelectMultiple, required=True, label="Participantes"
    )

    class Meta:
        model = Conversa
        fields = ["titulo", "tipo", "participantes_selecionados"]
        widgets = {
            "titulo": forms.TextInput(attrs={"placeholder": "Digite o título da conversa..."}),
            "tipo": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Configurar queryset de participantes baseado no tenant do usuário
        if user and hasattr(user, "tenant"):
            self.fields["participantes_selecionados"].queryset = User.objects.filter(
                tenant_memberships__tenant=user.tenant, is_active=True
            ).exclude(id=user.id)

        # Configurar crispy forms
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("titulo", css_class="form-group col-md-8 mb-0"),
                Column("tipo", css_class="form-group col-md-4 mb-0"),
                css_class="form-row",
            ),
            Field("participantes_selecionados", css_class="form-check-input"),
            FormActions(
                Submit("submit", "Criar Conversa", css_class="btn btn-primary"),
                HTML('<a href="{% url "chat:conversa_list" %}" class="btn btn-secondary ml-2">Cancelar</a>'),
            ),
        )

    def save(self, commit=True):
        conversa = super().save(commit=commit)

        if commit:
            # Adicionar participantes selecionados
            participantes = self.cleaned_data["participantes_selecionados"]
            for participante in participantes:
                conversa.adicionar_participante(participante, adicionado_por=conversa.criador)

        return conversa


class MensagemForm(forms.ModelForm):
    """Form para enviar mensagens"""

    class Meta:
        model = Mensagem
        fields = ["conteudo", "arquivo", "resposta_para"]
        widgets = {
            "conteudo": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Digite sua mensagem...", "class": "form-control"}
            ),
            "arquivo": forms.FileInput(
                attrs={"class": "form-control-file", "accept": ".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif"}
            ),
            "resposta_para": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        conversa = kwargs.pop("conversa", None)
        super().__init__(*args, **kwargs)

        # Configurar queryset de mensagens para resposta
        if conversa:
            self.fields["resposta_para"].queryset = conversa.mensagens.filter(
                status__in=["enviada", "entregue", "lida", "editada"]
            )

        # Configurar crispy forms
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_enctype = "multipart/form-data"
        self.helper.layout = Layout(
            Field("conteudo", css_class="form-control"),
            Field("arquivo", css_class="form-control-file"),
            Field("resposta_para"),
            FormActions(
                Submit("submit", "Enviar", css_class="btn btn-primary"),
            ),
        )

    def clean_conteudo(self):
        conteudo = self.cleaned_data.get("conteudo", "").strip()
        if not conteudo and not self.cleaned_data.get("arquivo"):
            raise forms.ValidationError("É necessário fornecer um conteúdo ou anexar um arquivo.")
        return conteudo

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        if arquivo:
            # Verificar tamanho do arquivo (10MB por padrão)
            max_size = 10 * 1024 * 1024  # 10MB
            if arquivo.size > max_size:
                raise forms.ValidationError("O arquivo é muito grande. Tamanho máximo: 10MB.")

            # Verificar extensão do arquivo
            extensoes_permitidas = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg", ".png", ".gif", ".txt"]
            nome_arquivo = arquivo.name.lower()
            if not any(nome_arquivo.endswith(ext) for ext in extensoes_permitidas):
                raise forms.ValidationError("Tipo de arquivo não permitido.")

        return arquivo


class ConfiguracaoChatForm(forms.ModelForm):
    """Form para configurações do chat"""

    class Meta:
        model = ConfiguracaoChat
        fields = [
            "tamanho_maximo_arquivo_mb",
            "tipos_arquivo_permitidos",
            "dias_retencao_mensagens",
            "moderacao_habilitada",
            "palavras_bloqueadas",
            "notificacoes_push_habilitadas",
            "notificacoes_email_habilitadas",
        ]
        widgets = {
            "tamanho_maximo_arquivo_mb": forms.NumberInput(attrs={"min": 1, "max": 100}),
            "tipos_arquivo_permitidos": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Digite as extensões separadas por vírgula (ex: .pdf,.doc,.jpg)"}
            ),
            "dias_retencao_mensagens": forms.NumberInput(attrs={"min": 30, "max": 3650}),
            "palavras_bloqueadas": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Digite as palavras separadas por vírgula"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Configurar crispy forms
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML("<h5>Configurações de Arquivo</h5>"),
            Row(
                Column("tamanho_maximo_arquivo_mb", css_class="form-group col-md-6 mb-0"),
                Column("tipos_arquivo_permitidos", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            HTML("<hr><h5>Configurações de Retenção</h5>"),
            Field("dias_retencao_mensagens"),
            HTML("<hr><h5>Configurações de Moderação</h5>"),
            Field("moderacao_habilitada"),
            Field("palavras_bloqueadas"),
            HTML("<hr><h5>Configurações de Notificação</h5>"),
            Row(
                Column("notificacoes_push_habilitadas", css_class="form-group col-md-6 mb-0"),
                Column("notificacoes_email_habilitadas", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            FormActions(
                Submit("submit", "Salvar Configurações", css_class="btn btn-primary"),
            ),
        )

    def clean_tipos_arquivo_permitidos(self):
        tipos = self.cleaned_data.get("tipos_arquivo_permitidos", [])
        if isinstance(tipos, str):
            # Converter string em lista
            tipos = [t.strip() for t in tipos.split(",") if t.strip()]
        return tipos

    def clean_palavras_bloqueadas(self):
        palavras = self.cleaned_data.get("palavras_bloqueadas", [])
        if isinstance(palavras, str):
            # Converter string em lista
            palavras = [p.strip().lower() for p in palavras.split(",") if p.strip()]
        return palavras


class PreferenciaUsuarioChatForm(forms.ModelForm):
    """Form para preferências do usuário"""

    class Meta:
        model = PreferenciaUsuarioChat
        fields = [
            "notificacoes_habilitadas",
            "som_notificacao_habilitado",
            "status_online_visivel",
            "ultima_visualizacao_visivel",
            "tema_escuro",
            "tamanho_fonte",
        ]
        widgets = {
            "tamanho_fonte": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Configurar crispy forms
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML("<h5>Configurações de Notificação</h5>"),
            Row(
                Column("notificacoes_habilitadas", css_class="form-group col-md-6 mb-0"),
                Column("som_notificacao_habilitado", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            HTML("<hr><h5>Configurações de Privacidade</h5>"),
            Row(
                Column("status_online_visivel", css_class="form-group col-md-6 mb-0"),
                Column("ultima_visualizacao_visivel", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            HTML("<hr><h5>Configurações de Interface</h5>"),
            Row(
                Column("tema_escuro", css_class="form-group col-md-6 mb-0"),
                Column("tamanho_fonte", css_class="form-group col-md-6 mb-0"),
                css_class="form-row",
            ),
            FormActions(
                Submit("submit", "Salvar Preferências", css_class="btn btn-primary"),
            ),
        )


class BuscarUsuariosForm(forms.Form):
    """Form para buscar usuários para adicionar à conversa"""

    busca = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Digite o nome ou email do usuário...", "class": "form-control"}),
        label="Buscar Usuários",
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Configurar crispy forms
        self.helper = FormHelper()
        self.helper.form_method = "get"
        self.helper.layout = Layout(
            Row(
                Column("busca", css_class="form-group col-md-10 mb-0"),
                Column(
                    Submit("submit", "Buscar", css_class="btn btn-primary"),
                    css_class="form-group col-md-2 mb-0 d-flex align-items-end",
                ),
                css_class="form-row",
            )
        )
