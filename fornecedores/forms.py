# fornecedores/forms.py (VERSÃO FINAL, COMPLETA E "DE PONTA")

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from cadastros_gerais.models import ItemAuxiliar

from .models import (
    CategoriaFornecedor,
    ContatoFornecedor,
    DadosBancariosFornecedor,
    EnderecoFornecedor,
    Fornecedor,
    FornecedorDocumento,
    FornecedorDocumentoVersao,
    FornecedorPF,
    FornecedorPJ,
)


class BaseFornecedorForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if not self.tenant and self.instance and self.instance.pk:
            self.tenant = self.instance.tenant

    class Meta:
        abstract = True


class FornecedorForm(BaseFornecedorForm):
    class Meta:
        model = Fornecedor
        fields = [
            "tipo_pessoa",
            "tipo_fornecimento",
            "categoria",
            "logo",
            "status",
            "status_homologacao",
            "avaliacao",
            "condicoes_pagamento",
            "observacoes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["categoria"].queryset = CategoriaFornecedor.objects.filter(tenant=self.tenant)


class FornecedorPJForm(BaseFornecedorForm):
    class Meta:
        model = FornecedorPJ
        fields = [
            "razao_social",
            "nome_fantasia",
            "cnpj",
            "inscricao_estadual",
            "inscricao_municipal",
            "data_fundacao",
            "data_abertura",
            "porte_empresa",
            "ramo_atividade",
            "cnae_principal",
            "cnae_secundarios",
            "website",
            "redes_sociais",
            "nome_responsavel_financeiro",
            "nome_responsavel_comercial",
            "nome_responsavel_tecnico",
        ]

    def clean_cnpj(self):
        cnpj = self.cleaned_data["cnpj"]
        if cnpj:
            cnpj_limpo = "".join(filter(str.isdigit, cnpj))
            if self.instance and self.instance.pk:
                qs = FornecedorPJ.objects.filter(fornecedor__tenant=self.tenant, cnpj=cnpj_limpo).exclude(
                    fornecedor_id=self.instance.pk
                )
            else:
                qs = FornecedorPJ.objects.filter(fornecedor__tenant=self.tenant, cnpj=cnpj_limpo)
            if qs.exists():
                raise ValidationError(_("Este CNPJ já está em uso por outro fornecedor nesta empresa."))
        return cnpj


class FornecedorPFForm(BaseFornecedorForm):
    class Meta:
        model = FornecedorPF
        fields = [
            "nome_completo",
            "cpf",
            "rg",
            "data_nascimento",
            "sexo",
            "naturalidade",
            "nacionalidade",
            "nome_mae",
            "nome_pai",
            "estado_civil",
            "profissao",
        ]

    def clean_cpf(self):
        cpf = self.cleaned_data["cpf"]
        if cpf:
            cpf_limpo = "".join(filter(str.isdigit, cpf))
            if self.instance and self.instance.pk:
                qs = FornecedorPF.objects.filter(fornecedor__tenant=self.tenant, cpf=cpf_limpo).exclude(
                    fornecedor_id=self.instance.pk
                )
            else:
                qs = FornecedorPF.objects.filter(fornecedor__tenant=self.tenant, cpf=cpf_limpo)
            if qs.exists():
                raise ValidationError(_("Este CPF já está em uso por outro fornecedor nesta empresa."))
        return cpf


class ContatoFornecedorForm(BaseFornecedorForm):
    class Meta:
        model = ContatoFornecedor
        fields = ["nome", "email", "telefone", "cargo"]


class EnderecoFornecedorForm(BaseFornecedorForm):
    class Meta:
        model = EnderecoFornecedor
        fields = ["logradouro", "numero", "complemento", "bairro", "cidade", "estado", "cep"]
        widgets = {"cep": forms.TextInput(attrs={"class": "cep-mask"})}


class DadosBancariosFornecedorForm(BaseFornecedorForm):
    class Meta:
        model = DadosBancariosFornecedor
        fields = ["banco", "agencia", "conta", "tipo_chave_pix", "chave_pix"]


class CategoriaFornecedorForm(BaseFornecedorForm):
    class Meta:
        model = CategoriaFornecedor
        fields = ["nome"]

    def clean_nome(self):
        nome = self.cleaned_data["nome"]
        if self.tenant:
            if self.instance and self.instance.pk:
                if (
                    CategoriaFornecedor.objects.filter(tenant=self.tenant, nome=nome)
                    .exclude(pk=self.instance.pk)
                    .exists()
                ):
                    raise ValidationError(_("Já existe uma categoria com este nome para esta empresa."))
            elif CategoriaFornecedor.objects.filter(tenant=self.tenant, nome=nome).exists():
                raise ValidationError(_("Já existe uma categoria com este nome para esta empresa."))
        return nome


class FornecedorDocumentoVersaoCreateForm(forms.Form):
    tipo = forms.ModelChoiceField(queryset=ItemAuxiliar.objects.none(), label=_("Tipo de Documento"))
    periodicidade = forms.ChoiceField(choices=FornecedorDocumento.PERIODICIDADE_CHOICES, label=_("Periodicidade"))
    exigencia = forms.ChoiceField(choices=FornecedorDocumento.EXIGENCIA_CHOICES, label=_("Exigência"))
    arquivo = forms.FileField(label=_("Arquivo"))
    competencia = forms.CharField(label=_("Competência (MM/AAAA)"), required=False)
    observacao = forms.CharField(label=_("Observação"), required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        self.fornecedor = kwargs.pop("fornecedor", None)
        super().__init__(*args, **kwargs)
        # Filtrar tipos aplicáveis a FORNECEDOR nas categorias conhecidas
        qs = ItemAuxiliar.objects.filter(ativo=True)
        qs = qs.filter(models.Q(alvo="fornecedor") | models.Q(targets__code="fornecedor")).distinct()
        # Opcional: filtrar por categorias de documentos como no core
        qs = qs.filter(categoria__slug__in=["documentos-da-empresa", "documentos-financeiros", "outros-documentos"])
        self.fields["tipo"].queryset = qs.order_by("categoria__ordem", "ordem", "nome")

    def clean_competencia(self):
        comp = self.cleaned_data.get("competencia")
        if comp:
            comp = comp.strip()
            # Aceitar MM/AAAA
            import re

            if not re.match(r"^(0[1-9]|1[0-2])\/(19|20)\d{2}$", comp):
                raise forms.ValidationError(_("Formato inválido. Use MM/AAAA."))
        return comp

    def save(self, user=None):
        if not self.fornecedor:
            raise ValueError("fornecedor é obrigatório")
        tipo = self.cleaned_data["tipo"]
        periodicidade = self.cleaned_data["periodicidade"]
        exigencia = self.cleaned_data["exigencia"]
        arquivo = self.cleaned_data["arquivo"]
        competencia = self.cleaned_data.get("competencia") or None
        observacao = self.cleaned_data.get("observacao") or ""

        # Criar/obter documento pai com periodicidade e exigência
        doc, _ = FornecedorDocumento.objects.get_or_create(
            fornecedor=self.fornecedor,
            tipo=tipo,
            defaults={
                "periodicidade": periodicidade,
                "exigencia": exigencia,
            },
        )
        # Atualiza caso já exista
        doc.periodicidade = periodicidade
        doc.exigencia = exigencia
        doc.save()

        # Determinar próxima versão para a competência
        qs = doc.versoes
        if competencia:
            qs = qs.filter(competencia=competencia)
        current_max = qs.aggregate(models.Max("versao")).get("versao__max") or 0
        nova_versao_num = current_max + 1

        versao = FornecedorDocumentoVersao.objects.create(
            documento=doc,
            versao=nova_versao_num,
            arquivo=arquivo,
            usuario=user,
            observacao=observacao,
            competencia=competencia,
            status="enviado",
        )
        return versao


class FornecedorDocumentoForm(forms.ModelForm):
    class Meta:
        model = FornecedorDocumento
        fields = ["fornecedor", "tipo", "periodicidade", "exigencia"]
        widgets = {
            "fornecedor": forms.HiddenInput(),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "periodicidade": forms.Select(attrs={"class": "form-select"}),
            "exigencia": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        fornecedor = kwargs.get("initial", {}).get("fornecedor") or kwargs.get("instance")
        super().__init__(*args, **kwargs)
        if fornecedor:
            self.fields["tipo"].queryset = ItemAuxiliar.objects.filter(
                categoria__slug__icontains="documento", ativo=True
            )


# --- DEFINIÇÃO DOS FORMSETS ---

ContatoFornecedorFormSet = inlineformset_factory(
    Fornecedor,  # Modelo Pai
    ContatoFornecedor,  # Modelo Filho
    form=ContatoFornecedorForm,  # Formulário a ser usado para cada item
    extra=0,  # Quantos formulários extras em branco mostrar
    can_delete=True,  # Permitir que os usuários marquem para exclusão
    can_delete_extra=True,
)

EnderecoFornecedorFormSet = inlineformset_factory(
    Fornecedor, EnderecoFornecedor, form=EnderecoFornecedorForm, extra=0, can_delete=True, can_delete_extra=True
)

DadosBancariosFormSet = inlineformset_factory(
    Fornecedor,
    DadosBancariosFornecedor,
    form=DadosBancariosFornecedorForm,
    extra=0,
    can_delete=True,
    can_delete_extra=True,
)
