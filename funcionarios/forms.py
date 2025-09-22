# funcionarios/forms.py

from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from core.forms import BasePandoraForm
from core.models import CustomUser, Department

from .models import (
    Beneficio,
    CartaoPonto,
    DecimoTerceiro,
    Dependente,
    Ferias,
    Folga,
    Funcionario,
    FuncionarioRemuneracaoRegra,
    HorarioTrabalho,
    SalarioHistorico,
)


class FuncionarioForm(BasePandoraForm):
    class Meta:
        model = Funcionario
        fields = [
            "user",
            "nome_completo",
            "cpf",
            "rg",
            "data_nascimento",
            "sexo",
            "estado_civil",
            "nacionalidade",
            "escolaridade",
            "email_pessoal",
            "telefone_pessoal",
            "telefone_emergencia",
            "contato_emergencia",
            "endereco_logradouro",
            "endereco_numero",
            "endereco_complemento",
            "endereco_bairro",
            "endereco_cidade",
            "endereco_uf",
            "endereco_cep",
            "data_admissao",
            "data_demissao",
            "motivo_demissao",
            "cargo",
            "departamento",
            "tipo_contrato",
            "jornada_trabalho_horas",
            "salario_base",
            "banco",
            "agencia",
            "conta",
            "tipo_conta",
            "pis",
            "ctps",
            "titulo_eleitor",
            "reservista",
            "observacoes",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "data_admissao": forms.DateInput(attrs={"type": "date"}),
            "data_demissao": forms.DateInput(attrs={"type": "date"}),
            "motivo_demissao": forms.Textarea(attrs={"rows": 2, "placeholder": "Preencha somente ao desligar"}),
            "observacoes": forms.Textarea(attrs={"rows": 4}),
            "cpf": forms.TextInput(attrs={"data-inputmask": "'mask': '999.999.999-99'"}),
            "endereco_cep": forms.TextInput(attrs={"data-inputmask": "'mask': '99999-999'"}),
            "telefone_pessoal": forms.TextInput(attrs={"data-inputmask": "'mask': '(99) 99999-9999'"}),
            "telefone_emergencia": forms.TextInput(attrs={"data-inputmask": "'mask': '(99) 99999-9999'"}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        # corrigir indentação e armazenar tenant para validação futura
        self._tenant = tenant

        if tenant:
            self.fields["departamento"].queryset = Department.objects.filter(tenant=tenant)
            # Filtrar usuários que ainda não são funcionários
            usuarios_sem_funcionario = CustomUser.objects.filter(tenant_memberships__tenant=tenant).exclude(
                funcionario_profile__isnull=False
            )
            if self.instance.pk and self.instance.user:
                # Se estamos editando e já tem um usuário, incluir o usuário atual
                usuarios_sem_funcionario = usuarios_sem_funcionario | CustomUser.objects.filter(
                    pk=self.instance.user.pk
                )

            self.fields["user"].queryset = usuarios_sem_funcionario
            self.fields["user"].required = False

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf")
        if cpf:
            # Remove formatação
            cpf = "".join(filter(str.isdigit, cpf))
            if len(cpf) != 11:
                raise ValidationError(_("CPF deve ter 11 dígitos."))

            # Verifica se já existe outro funcionário com o mesmo CPF no tenant
            if self.instance.pk:
                existing = Funcionario.objects.filter(tenant=self.instance.tenant, cpf=cpf).exclude(pk=self.instance.pk)
            else:
                # Para novos funcionários, precisamos do tenant do contexto
                tenant = getattr(self, "_tenant", None)
                existing = Funcionario.objects.filter(cpf=cpf)
                if tenant:
                    existing = existing.filter(tenant=tenant)

            if existing.exists():
                raise ValidationError(_("Já existe um funcionário com este CPF."))

        return cpf

    def clean_data_nascimento(self):
        data_nascimento = self.cleaned_data.get("data_nascimento")
        if data_nascimento:
            hoje = date.today()
            idade = (
                hoje.year
                - data_nascimento.year
                - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))
            )
            if idade < 14:
                raise ValidationError(_("Funcionário deve ter pelo menos 14 anos."))
            if idade > 100:
                raise ValidationError(_("Data de nascimento inválida."))
        return data_nascimento

    def clean(self):
        cleaned_data = super().clean()
        data_admissao = cleaned_data.get("data_admissao")
        data_demissao = cleaned_data.get("data_demissao")
        data_nascimento = cleaned_data.get("data_nascimento")

        if data_admissao and data_nascimento and data_admissao <= data_nascimento:
            raise ValidationError(_("Data de admissão deve ser posterior à data de nascimento."))

        if data_admissao and data_demissao and data_demissao <= data_admissao:
            raise ValidationError(_("Data de demissão deve ser posterior à data de admissão."))

        return cleaned_data


class FeriasForm(BasePandoraForm):
    class Meta:
        model = Ferias
        fields = [
            "funcionario",
            "periodo_aquisitivo_inicio",
            "periodo_aquisitivo_fim",
            "data_inicio",
            "data_fim",
            "dias_gozados",
            "abono_pecuniario",
            "dias_abono",
            "data_pagamento",
            "valor_pago",
            "status",
            "observacoes",
        ]
        widgets = {
            "periodo_aquisitivo_inicio": forms.DateInput(attrs={"type": "date"}),
            "periodo_aquisitivo_fim": forms.DateInput(attrs={"type": "date"}),
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
            "data_pagamento": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        funcionario = kwargs.pop("funcionario", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields["funcionario"].queryset = Funcionario.objects.filter(tenant=tenant, ativo=True)

        if funcionario:
            self.fields["funcionario"].initial = funcionario
            self.fields["funcionario"].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get("data_inicio")
        data_fim = cleaned_data.get("data_fim")
        dias_gozados = cleaned_data.get("dias_gozados")
        abono_pecuniario = cleaned_data.get("abono_pecuniario")
        dias_abono = cleaned_data.get("dias_abono")

        if data_inicio and data_fim:
            if data_fim <= data_inicio:
                raise ValidationError(_("Data de fim deve ser posterior à data de início."))

            # Calcular dias úteis entre as datas
            dias_periodo = (data_fim - data_inicio).days + 1
            if dias_gozados and dias_gozados > dias_periodo:
                raise ValidationError(_("Dias gozados não pode ser maior que o período das férias."))

        if abono_pecuniario and not dias_abono:
            raise ValidationError(_("Quando há abono pecuniário, deve ser informado o número de dias."))

        if dias_abono and dias_abono > 10:
            raise ValidationError(_("Abono pecuniário não pode exceder 10 dias."))

        return cleaned_data


class DecimoTerceiroForm(BasePandoraForm):
    class Meta:
        model = DecimoTerceiro
        fields = [
            "funcionario",
            "ano_referencia",
            "tipo_parcela",
            "meses_trabalhados",
            "valor_bruto",
            "desconto_inss",
            "desconto_irrf",
            "outros_descontos",
            "data_pagamento",
            "status",
            "observacoes",
        ]
        widgets = {
            "data_pagamento": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        funcionario = kwargs.pop("funcionario", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields["funcionario"].queryset = Funcionario.objects.filter(tenant=tenant)

        if funcionario:
            self.fields["funcionario"].initial = funcionario
            self.fields["funcionario"].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        funcionario = cleaned_data.get("funcionario")
        ano_referencia = cleaned_data.get("ano_referencia")
        tipo_parcela = cleaned_data.get("tipo_parcela")

        if funcionario and ano_referencia and tipo_parcela:
            # Verificar se já existe registro para este funcionário, ano e tipo de parcela
            existing = DecimoTerceiro.objects.filter(
                funcionario=funcionario, ano_referencia=ano_referencia, tipo_parcela=tipo_parcela
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(
                    _(f"Já existe registro de {tipo_parcela} do 13º salário para este funcionário em {ano_referencia}.")
                )

        return cleaned_data


class FolgaForm(BasePandoraForm):
    class Meta:
        model = Folga
        fields = ["funcionario", "data_inicio", "data_fim", "tipo_folga", "motivo", "documento_comprobatorio", "status"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
            "motivo": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        kwargs.pop("funcionario", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields["funcionario"].queryset = Funcionario.objects.filter(tenant=tenant, ativo=True)


class RemuneracaoRegraForm(BasePandoraForm):
    class Meta:
        model = FuncionarioRemuneracaoRegra
        fields = [
            "funcionario",
            "tipo_regra",
            "descricao",
            "valor_base",
            "percentual",
            "codigo_procedimento",
            "vigencia_inicio",
            "vigencia_fim",
            "ativo",
        ]
        widgets = {
            "vigencia_inicio": forms.DateInput(attrs={"type": "date"}),
            "vigencia_fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        funcionario = kwargs.pop("funcionario", None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields["funcionario"].queryset = Funcionario.objects.filter(tenant=tenant)
        if funcionario:
            self.fields["funcionario"].initial = funcionario
            self.fields["funcionario"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo_regra")
        valor = cleaned.get("valor_base")
        perc = cleaned.get("percentual")
        if tipo in ("FIXO_MENSAL", "HORA", "TAREFA", "PROCEDIMENTO_FIXO", "COMISSAO_FIXA") and not valor:
            self.add_error("valor_base", "Informe o valor base para este tipo de regra.")
        if tipo in ("PROCEDIMENTO_PERCENTUAL", "COMISSAO_PERCENTUAL") and not perc:
            self.add_error("percentual", "Informe o percentual para este tipo de regra.")
        if perc and perc > 100:
            self.add_error("percentual", "Percentual não pode exceder 100%.")
        vi = cleaned.get("vigencia_inicio")
        vf = cleaned.get("vigencia_fim")
        if vi and vf and vf < vi:
            self.add_error("vigencia_fim", "Vigência final deve ser posterior ou igual ao início.")
        return cleaned

        if funcionario:
            self.fields["funcionario"].initial = funcionario
            self.fields["funcionario"].widget = forms.HiddenInput()


class CartaoPontoForm(BasePandoraForm):
    class Meta:
        model = CartaoPonto
        fields = ["funcionario", "data_hora_registro", "tipo_registro", "justificativa", "observacoes"]
        widgets = {
            "data_hora_registro": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "justificativa": forms.Textarea(attrs={"rows": 2}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        funcionario = kwargs.pop("funcionario", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields["funcionario"].queryset = Funcionario.objects.filter(tenant=tenant, ativo=True)

        if funcionario:
            self.fields["funcionario"].initial = funcionario
            self.fields["funcionario"].widget = forms.HiddenInput()


class BeneficioForm(BasePandoraForm):
    class Meta:
        model = Beneficio
        fields = [
            "funcionario",
            "tipo_beneficio",
            "categoria",
            "valor",
            "data_referencia",
            "recorrente",
            "ativo",
            "observacoes",
        ]
        widgets = {
            "data_referencia": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        funcionario = kwargs.pop("funcionario", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields["funcionario"].queryset = Funcionario.objects.filter(tenant=tenant)

        if funcionario:
            self.fields["funcionario"].initial = funcionario
            self.fields["funcionario"].widget = forms.HiddenInput()


class SalarioHistoricoForm(BasePandoraForm):
    class Meta:
        model = SalarioHistorico
        fields = ["funcionario", "data_vigencia", "valor_salario", "motivo_alteracao"]
        widgets = {
            "data_vigencia": forms.DateInput(attrs={"type": "date"}),
            "motivo_alteracao": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        funcionario = kwargs.pop("funcionario", None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields["funcionario"].queryset = Funcionario.objects.filter(tenant=tenant)

        if funcionario:
            self.fields["funcionario"].initial = funcionario
            self.fields["funcionario"].widget = forms.HiddenInput()


class DependenteForm(BasePandoraForm):
    class Meta:
        model = Dependente
        fields = [
            "nome_completo",
            "cpf",
            "data_nascimento",
            "tipo_dependente",
            "dependente_ir",
            "dependente_salario_familia",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "cpf": forms.TextInput(attrs={"data-inputmask": "'mask': '999.999.999-99'"}),
        }

    def clean_data_nascimento(self):
        data_nascimento = self.cleaned_data.get("data_nascimento")
        if data_nascimento and data_nascimento > date.today():
            raise ValidationError(_("Data de nascimento não pode ser futura."))
        return data_nascimento


class HorarioTrabalhoForm(BasePandoraForm):
    class Meta:
        model = HorarioTrabalho
        fields = ["dia_semana", "hora_entrada", "hora_saida", "hora_inicio_almoco", "hora_fim_almoco", "ativo"]
        widgets = {
            "hora_entrada": forms.TimeInput(attrs={"type": "time"}),
            "hora_saida": forms.TimeInput(attrs={"type": "time"}),
            "hora_inicio_almoco": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim_almoco": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        hora_entrada = cleaned_data.get("hora_entrada")
        hora_saida = cleaned_data.get("hora_saida")
        hora_inicio_almoco = cleaned_data.get("hora_inicio_almoco")
        hora_fim_almoco = cleaned_data.get("hora_fim_almoco")

        if hora_entrada and hora_saida and hora_saida <= hora_entrada:
            raise ValidationError(_("Hora de saída deve ser posterior à hora de entrada."))

        if hora_inicio_almoco and hora_fim_almoco and hora_fim_almoco <= hora_inicio_almoco:
            raise ValidationError(_("Hora de fim do almoço deve ser posterior à hora de início."))

        if hora_entrada and hora_inicio_almoco and hora_inicio_almoco <= hora_entrada:
            raise ValidationError(_("Hora de início do almoço deve ser posterior à hora de entrada."))

        if hora_fim_almoco and hora_saida and hora_saida <= hora_fim_almoco:
            raise ValidationError(_("Hora de saída deve ser posterior à hora de fim do almoço."))

        return cleaned_data


# Formsets para relacionamentos
DependenteFormSet = inlineformset_factory(
    Funcionario,
    Dependente,
    form=DependenteForm,
    fields=[
        "nome_completo",
        "cpf",
        "data_nascimento",
        "tipo_dependente",
        "dependente_ir",
        "dependente_salario_familia",
    ],
    extra=0,
    can_delete=True,
)

HorarioTrabalhoFormSet = inlineformset_factory(
    Funcionario,
    HorarioTrabalho,
    form=HorarioTrabalhoForm,
    fields=["dia_semana", "hora_entrada", "hora_saida", "hora_inicio_almoco", "hora_fim_almoco", "ativo"],
    extra=0,
    can_delete=True,
)
