from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import CampoFormulario, FormularioDinamico, StatusFormulario, StatusResposta, TipoCampo

User = get_user_model()


class FormularioDinamicoForm(forms.ModelForm):
    """Formulário para criar/editar formulários dinâmicos"""

    class Meta:
        model = FormularioDinamico
        fields = [
            "titulo",
            "slug",
            "descricao",
            "status",
            "publico",
            "permite_multiplas_respostas",
            "requer_login",
            "data_inicio",
            "data_fim",
            "notificar_nova_resposta",
            "emails_notificacao",
            "cor_tema",
            "css_personalizado",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "data_fim": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "emails_notificacao": forms.Textarea(attrs={"rows": 3}),
            "cor_tema": forms.TextInput(attrs={"type": "color"}),
            "css_personalizado": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for _field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = "form-control"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_emails_notificacao(self):
        emails = self.cleaned_data.get("emails_notificacao", "")
        if emails:
            linhas = [linha.strip() for linha in emails.split("\n") if linha.strip()]
            for email in linhas:
                try:
                    forms.EmailField().clean(email)
                except ValidationError:
                    raise ValidationError(f"E-mail inválido: {email}")
        return emails


class CampoFormularioForm(forms.ModelForm):
    """Formulário para criar/editar campos de formulário"""

    opcoes_texto = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        required=False,
        label="Opções (uma por linha)",
        help_text="Para campos de seleção, digite uma opção por linha",
    )

    class Meta:
        model = CampoFormulario
        fields = [
            "nome",
            "label",
            "tipo",
            "obrigatorio",
            "placeholder",
            "help_text",
            "valor_padrao",
            "min_length",
            "max_length",
            "min_value",
            "max_value",
            "regex_validacao",
            "css_classes",
            "largura_coluna",
            "ordem",
            "grupo",
        ]
        widgets = {
            "help_text": forms.Textarea(attrs={"rows": 2}),
            "valor_padrao": forms.Textarea(attrs={"rows": 2}),
            "regex_validacao": forms.TextInput(attrs={"placeholder": r"^[A-Za-z0-9]+$"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Preencher campo de opções se existir
        if self.instance and self.instance.pk and self.instance.opcoes:
            opcoes_list = self.instance.get_opcoes_list()
            opcoes_texto = "\n".join([opcao.get("label", opcao.get("value", "")) for opcao in opcoes_list])
            self.fields["opcoes_texto"].initial = opcoes_texto

        # Adicionar classes CSS do Bootstrap 5
        for _field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = "form-control"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_nome(self):
        nome = self.cleaned_data["nome"]
        # Validar que o nome é um identificador válido
        if not nome.replace("_", "").isalnum():
            raise ValidationError("O nome deve conter apenas letras, números e underscore.")
        return nome

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo")
        opcoes_texto = cleaned_data.get("opcoes_texto")

        # Validar opções para campos que precisam
        if tipo in [TipoCampo.SELECT, TipoCampo.RADIO, TipoCampo.CHECKBOX] and not opcoes_texto:
            raise ValidationError("Campos de seleção precisam ter opções definidas.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Processar opções
        opcoes_texto = self.cleaned_data.get("opcoes_texto", "")
        if opcoes_texto:
            instance.set_opcoes_from_text(opcoes_texto)
        else:
            instance.opcoes = []

        if commit:
            instance.save()

        return instance


class RespostaFormularioForm(forms.Form):
    """Formulário dinâmico baseado na configuração do FormularioDinamico"""

    def __init__(self, formulario, *args, **kwargs):
        self.formulario = formulario
        super().__init__(*args, **kwargs)

        # Criar campos dinamicamente
        for campo in formulario.campos.filter().order_by("ordem"):
            field = self._criar_campo_django(campo)
            self.fields[campo.nome] = field

    def _criar_campo_django(self, campo):
        """Cria um campo Django baseado na configuração do CampoFormulario"""

        # Configurações básicas
        kwargs = {
            "label": campo.label,
            "required": campo.obrigatorio,
            "help_text": campo.help_text,
            "initial": campo.valor_padrao,
        }

        # Widget attributes
        widget_attrs = {
            "class": f"form-control {campo.css_classes}".strip(),
            "placeholder": campo.placeholder,
        }

        # Criar campo baseado no tipo
        if campo.tipo == TipoCampo.TEXT:
            field = forms.CharField(**kwargs)
            if campo.min_length:
                field.min_length = campo.min_length
            if campo.max_length:
                field.max_length = campo.max_length
                widget_attrs["maxlength"] = campo.max_length

        elif campo.tipo == TipoCampo.TEXTAREA:
            widget_attrs["rows"] = 4
            field = forms.CharField(widget=forms.Textarea(attrs=widget_attrs), **kwargs)
            if campo.min_length:
                field.min_length = campo.min_length
            if campo.max_length:
                field.max_length = campo.max_length

        elif campo.tipo == TipoCampo.EMAIL:
            field = forms.EmailField(**kwargs)

        elif campo.tipo == TipoCampo.NUMBER:
            field = forms.DecimalField(**kwargs)
            widget_attrs["type"] = "number"
            if campo.min_value is not None:
                field.min_value = campo.min_value
                widget_attrs["min"] = str(campo.min_value)
            if campo.max_value is not None:
                field.max_value = campo.max_value
                widget_attrs["max"] = str(campo.max_value)

        elif campo.tipo == TipoCampo.DATE:
            field = forms.DateField(**kwargs)
            widget_attrs["type"] = "date"

        elif campo.tipo == TipoCampo.DATETIME:
            field = forms.DateTimeField(**kwargs)
            widget_attrs["type"] = "datetime-local"

        elif campo.tipo == TipoCampo.TIME:
            field = forms.TimeField(**kwargs)
            widget_attrs["type"] = "time"

        elif campo.tipo == TipoCampo.SELECT:
            opcoes = [(opcao["value"], opcao["label"]) for opcao in campo.get_opcoes_list()]
            field = forms.ChoiceField(choices=opcoes, **kwargs)

        elif campo.tipo == TipoCampo.RADIO:
            opcoes = [(opcao["value"], opcao["label"]) for opcao in campo.get_opcoes_list()]
            field = forms.ChoiceField(
                choices=opcoes, widget=forms.RadioSelect(attrs={"class": "form-check-input"}), **kwargs
            )

        elif campo.tipo == TipoCampo.CHECKBOX:
            opcoes = [(opcao["value"], opcao["label"]) for opcao in campo.get_opcoes_list()]
            field = forms.MultipleChoiceField(
                choices=opcoes, widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}), **kwargs
            )

        elif campo.tipo == TipoCampo.FILE:
            field = forms.FileField(**kwargs)

        elif campo.tipo == TipoCampo.IMAGE:
            field = forms.ImageField(**kwargs)

        elif campo.tipo == TipoCampo.URL:
            # Garantir padrão https para evitar warning Django 6 (default scheme)
            field = forms.URLField(assume_scheme="https", **kwargs)

        elif campo.tipo == TipoCampo.PHONE:
            field = forms.CharField(**kwargs)
            widget_attrs["type"] = "tel"

        elif campo.tipo == TipoCampo.CPF:
            field = forms.CharField(**kwargs)
            widget_attrs["data-mask"] = "000.000.000-00"

        elif campo.tipo == TipoCampo.CNPJ:
            field = forms.CharField(**kwargs)
            widget_attrs["data-mask"] = "00.000.000/0000-00"

        elif campo.tipo == TipoCampo.CEP:
            field = forms.CharField(**kwargs)
            widget_attrs["data-mask"] = "00000-000"

        elif campo.tipo == TipoCampo.CURRENCY:
            field = forms.DecimalField(decimal_places=2, **kwargs)
            widget_attrs["data-mask"] = "currency"

        elif campo.tipo == TipoCampo.PERCENTAGE:
            field = forms.DecimalField(decimal_places=2, **kwargs)
            widget_attrs["type"] = "number"
            widget_attrs["step"] = "0.01"
            widget_attrs["min"] = "0"
            widget_attrs["max"] = "100"

        elif campo.tipo == TipoCampo.RATING:
            opcoes = [(str(i), f"{i} estrela{'s' if i > 1 else ''}") for i in range(1, 6)]
            field = forms.ChoiceField(
                choices=opcoes, widget=forms.RadioSelect(attrs={"class": "rating-input"}), **kwargs
            )

        elif campo.tipo == TipoCampo.COLOR:
            field = forms.CharField(**kwargs)
            widget_attrs["type"] = "color"

        elif campo.tipo == TipoCampo.RANGE:
            field = forms.IntegerField(**kwargs)
            widget_attrs["type"] = "range"
            if campo.min_value is not None:
                widget_attrs["min"] = str(int(campo.min_value))
            if campo.max_value is not None:
                widget_attrs["max"] = str(int(campo.max_value))

        elif campo.tipo == TipoCampo.HIDDEN:
            field = forms.CharField(widget=forms.HiddenInput(), **kwargs)

        else:
            # Fallback para texto
            field = forms.CharField(**kwargs)

        # Aplicar widget attributes se não foi definido um widget customizado
        if not hasattr(field.widget, "attrs") or not field.widget.attrs:
            field.widget.attrs = widget_attrs
        else:
            field.widget.attrs.update(widget_attrs)

        # Aplicar validação regex se definida
        if campo.regex_validacao:
            from django.core.validators import RegexValidator

            field.validators.append(
                RegexValidator(regex=campo.regex_validacao, message=f"Valor inválido para o campo {campo.label}")
            )

        return field


class FiltroFormularioForm(forms.Form):
    """Formulário para filtrar formulários"""

    busca = forms.CharField(
        max_length=100,
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={"placeholder": "Título, descrição...", "class": "form-control"}),
    )

    status = forms.ChoiceField(
        choices=[("", "Todos os status")] + list(StatusFormulario.choices),
        required=False,
        label="Status",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    publico = forms.ChoiceField(
        choices=[("", "Todos"), ("true", "Públicos"), ("false", "Privados")],
        required=False,
        label="Visibilidade",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    criado_por = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Criado por",
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class FiltroRespostaForm(forms.Form):
    """Formulário para filtrar respostas"""

    status = forms.ChoiceField(
        choices=[("", "Todos os status")] + list(StatusResposta.choices),
        required=False,
        label="Status",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    usuario = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Usuário",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    data_inicio = forms.DateField(
        required=False, label="Data Início", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    data_fim = forms.DateField(
        required=False, label="Data Fim", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
