"""funcionarios/wizard_forms.py
Formulários do Wizard de Cadastro de Funcionários.
MVP inspirado em clientes/fornecedores, usando sessões.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.models import Department

from .models import Funcionario


class FuncionarioIdentificationForm(forms.ModelForm):
    dependentes_json = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Funcionario
        fields = [
            "nome_completo",
            "cpf",
            "rg",
            "rg_orgao_emissor",
            "rg_data_emissao",
            "data_nascimento",
            "sexo",
            "estado_civil",
            "nacionalidade",
            "naturalidade",
            "nome_mae",
            "nome_pai",
            "profissao",
            "escolaridade",
            "pis",
            "ctps",
            "titulo_eleitor",
            "reservista",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date", "class": "form-control wizard-field"}),
            "rg_data_emissao": forms.DateInput(attrs={"type": "date", "class": "form-control wizard-field"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            if not isinstance(f.widget, forms.DateInput):
                f.widget.attrs.setdefault("class", "form-control wizard-field")
        # Placeholders específicos para novos campos
        ph_map = {
            "naturalidade": "Cidade de nascimento",
            "nome_mae": "Nome completo da mãe",
            "nome_pai": "Nome completo do pai",
            "profissao": "Profissão principal",
            "pis": "Número do PIS/PASEP",
            "ctps": "Número da CTPS",
            "titulo_eleitor": "Número do Título de Eleitor",
            "reservista": "Número do Certificado de Reservista",
            "rg_orgao_emissor": "SSP/UF",
            "rg_data_emissao": "Data de emissão",
        }
        for k, v in ph_map.items():
            if k in self.fields:
                self.fields[k].widget.attrs.setdefault("placeholder", v)

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf") or ""
        digits = "".join(filter(str.isdigit, cpf))
        if len(digits) != 11:
            raise ValidationError(_("CPF deve ter 11 dígitos."))
        return cpf

    def clean_dependentes_json(self):
        import json

        raw = self.cleaned_data.get("dependentes_json") or ""
        if not raw:
            return "[]"
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError
            for idx, dep in enumerate(data):
                if not dep.get("nome"):
                    raise ValidationError(f"Dependente {idx + 1} sem nome.")
                if not dep.get("data_nascimento"):
                    raise ValidationError(f"Dependente {dep.get('nome', '?')} sem data de nascimento.")
            return raw
        except Exception:
            raise ValidationError("JSON de dependentes inválido.")


class FuncionarioAddressForm(forms.ModelForm):
    additional_addresses_json = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Funcionario
        fields = [
            "endereco_cep",
            "endereco_logradouro",
            "endereco_numero",
            "endereco_complemento",
            "endereco_bairro",
            "endereco_cidade",
            "endereco_uf",
            "endereco_pais",
            "additional_addresses_json",
        ]
        widgets = {
            "endereco_cep": forms.TextInput(attrs={"class": "form-control wizard-field cep-mask"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, f in self.fields.items():
            if not f.widget.attrs.get("class"):
                f.widget.attrs["class"] = "form-control wizard-field"


class FuncionarioContratoForm(forms.ModelForm):
    # Campo oculto para armazenar JSON da grade de horários detalhados (FuncionarioHorario)
    horarios_json = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Funcionario
        fields = [
            "data_admissao",
            "tipo_contrato",
            "cargo",
            "departamento",
            "jornada_trabalho_horas",
            "horario_entrada",
            "horario_saida",
            "intervalo_inicio",
            "intervalo_fim",
            "salario_base",
            "cnpj_prestador",
            "pj_categoria",
            "banco",
            "agencia",
            "conta",
            "tipo_conta",
            "horarios_json",
        ]
        widgets = {
            "data_admissao": forms.DateInput(attrs={"type": "date", "class": "form-control wizard-field"}),
            "horario_entrada": forms.TimeInput(attrs={"type": "time", "class": "form-control wizard-field"}),
            "horario_saida": forms.TimeInput(attrs={"type": "time", "class": "form-control wizard-field"}),
            "intervalo_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control wizard-field"}),
            "intervalo_fim": forms.TimeInput(attrs={"type": "time", "class": "form-control wizard-field"}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        for _name, f in self.fields.items():
            if not isinstance(f.widget, forms.DateInput):
                f.widget.attrs.setdefault("class", "form-control wizard-field")
        if tenant:
            self.fields["departamento"].queryset = Department.objects.filter(tenant=tenant)

    def clean(self):
        data = super().clean()
        tipo = data.get("tipo_contrato")
        cnpj = (data.get("cnpj_prestador") or "").strip()
        pj_cat = data.get("pj_categoria")
        if tipo == "PJ":
            # Exigir CNPJ, exceto quando categoria AUTONOMO (RPA) onde pode não haver CNPJ
            if pj_cat != "AUTONOMO":
                if not cnpj:
                    self.add_error("cnpj_prestador", "Informe o CNPJ do prestador.")
                else:
                    import re

                    nums = re.sub(r"\D", "", cnpj)
                    if len(nums) != 14:
                        self.add_error("cnpj_prestador", "CNPJ deve ter 14 dígitos.")
                    # Opcional: validar DV simples
            if pj_cat is None:
                self.add_error("pj_categoria", "Selecione a categoria PJ.")
        else:
            # Limpar campos PJ se não for PJ
            data["cnpj_prestador"] = None
            data["pj_categoria"] = None
        return data


class FuncionarioSalarioBancarioForm(forms.ModelForm):
    class Meta:
        model = Funcionario
        fields = [
            "salario_base",
            "banco",
            "agencia",
            "conta",
            "tipo_conta",
            "pis",
            "ctps",
            "titulo_eleitor",
            "reservista",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-control wizard-field")


class FuncionarioContatoEmergenciaForm(forms.ModelForm):
    class Meta:
        model = Funcionario
        fields = [
            "telefone_pessoal",
            "telefone_secundario",
            "email_pessoal",
            "telefone_emergencia",
            "contato_emergencia",
            "observacoes",
        ]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, f in self.fields.items():
            css = "form-control wizard-field"
            if isinstance(f.widget, forms.Textarea):
                f.widget.attrs.setdefault("class", css)
            else:
                f.widget.attrs.setdefault("class", css)
        # Campo oculto para contatos adicionais dinâmicos (JSON)
        self.fields["additional_contacts_json"] = forms.CharField(required=False, widget=forms.HiddenInput())


class FuncionarioConfirmForm(forms.Form):
    confirmar = forms.BooleanField(
        required=True,
        label=_("Confirmo a criação / atualização deste funcionário"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input wizard-checkbox"}),
    )
