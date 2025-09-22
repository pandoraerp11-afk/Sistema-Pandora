from django import forms
from django.utils.translation import gettext_lazy as _

from clientes.models import Cliente
from core.utils import get_current_tenant
from core.wizard_forms import MultipleFileField

from .models import Obra


class ObraIdentificationWizardForm(forms.ModelForm):
    """Step 1: Dados iniciais da Obra"""

    class Meta:
        model = Obra
        fields = ["nome", "tipo_obra", "cno", "cliente", "data_inicio", "data_previsao_termino", "valor_contrato"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": _("Nome da obra")}),
            "tipo_obra": forms.Select(attrs={"class": "form-select wizard-field"}),
            "cno": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": _("Cadastro Nacional de Obras (opcional)")}
            ),
            "cliente": forms.Select(attrs={"class": "form-select wizard-field select2"}),
            "data_inicio": forms.DateInput(attrs={"class": "form-control wizard-field", "type": "date"}),
            "data_previsao_termino": forms.DateInput(attrs={"class": "form-control wizard-field", "type": "date"}),
            "valor_contrato": forms.NumberInput(attrs={"class": "form-control wizard-field", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # Filtrar clientes por tenant quando possível
        qs = Cliente.objects.all()
        if self.request:
            tenant = get_current_tenant(self.request)
            if tenant and hasattr(Cliente, "tenant"):
                qs = qs.filter(tenant=tenant)
        self.fields["cliente"].queryset = qs
        self.fields["cliente"].empty_label = _("Selecione um cliente (opcional)")


class ObraContactsWizardForm(forms.Form):
    """Step 3: Contatos principais da obra (armazenados nas observações por enquanto)."""

    responsavel_nome = forms.CharField(
        required=False,
        label=_("Responsável pela Obra"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": _("Nome completo")}),
    )
    responsavel_cargo = forms.CharField(
        required=False,
        label=_("Cargo"),
        widget=forms.TextInput(
            attrs={"class": "form-control wizard-field", "placeholder": _("Ex.: Engenheiro, Encarregado")}
        ),
    )
    responsavel_email = forms.EmailField(
        required=False,
        label=_("E-mail"),
        widget=forms.EmailInput(attrs={"class": "form-control wizard-field", "placeholder": "responsavel@empresa.com"}),
    )
    responsavel_telefone = forms.CharField(
        required=False,
        label=_("Telefone"),
        widget=forms.TextInput(
            attrs={"class": "form-control wizard-field phone-mask", "placeholder": "(11) 99999-9999"}
        ),
    )


class ObraDocumentsWizardForm(forms.Form):
    """Step 4: Upload de documentos (múltiplos arquivos)."""

    documentos = MultipleFileField(
        required=False,
        label=_("Documentos da Obra"),
        help_text=_("Você pode selecionar múltiplos arquivos. Máximo 10 arquivos de até 10MB."),
        max_files=10,
        file_types=["pdf", "doc", "docx", "jpg", "jpeg", "png", "xlsx", "xls"],
    )


class ObraConfigurationWizardForm(forms.ModelForm):
    """Step 5: Configurações finais"""

    class Meta:
        model = Obra
        fields = ["status", "progresso", "valor_total", "data_termino", "observacoes"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select wizard-field"}),
            "progresso": forms.NumberInput(attrs={"class": "form-control wizard-field", "min": "0", "max": "100"}),
            "valor_total": forms.NumberInput(attrs={"class": "form-control wizard-field", "step": "0.01"}),
            "data_termino": forms.DateInput(attrs={"class": "form-control wizard-field", "type": "date"}),
            "observacoes": forms.Textarea(
                attrs={"class": "form-control wizard-field", "rows": 3, "placeholder": _("Observações adicionais")}
            ),
        }
