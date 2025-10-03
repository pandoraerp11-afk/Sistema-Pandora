"""Formulários do módulo Fornecedores (versão pós-migração para Wizard).

Este arquivo foi simplificado para conter apenas formulários efetivamente
utilizados fora do fluxo principal do wizard (documentos e categoria). Os
formulários de criação/edição direta de Fornecedor (PF/PJ) foram removidos em
favor do fluxo centralizado em ``wizard_views.py``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:  # pragma: no cover - somente para tipos
    from collections.abc import Mapping

from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _

from cadastros_gerais.models import ItemAuxiliar

from .models import CategoriaFornecedor, FornecedorDocumento, FornecedorDocumentoVersao


class CategoriaFornecedorForm(forms.ModelForm):
    """Form para criação/edição de categorias de fornecedor dentro de um tenant.

    A validação de unicidade é aplicada por tenant para evitar duplicidades
    lógicas sem depender de constraint específica (permite nomes iguais entre tenants).
    """

    tenant: Any  # definido dinamicamente no __init__

    class Meta:
        """Configuração de mapeamento do ModelForm."""

        model = CategoriaFornecedor
        # Usar tupla imutável evita alerta de mutabilidade compartilhada (RUF012)
        fields: ClassVar[tuple[str, ...]] = ("nome",)

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003 - interface padrão do Django
        """Captura o tenant explicitamente ou via instance existente."""
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if not self.tenant and self.instance and getattr(self.instance, "tenant_id", None):
            self.tenant = self.instance.tenant

    def clean_nome(self) -> str:
        """Garante unicidade do nome dentro do tenant atual."""
        nome: str = self.cleaned_data["nome"]
        if self.tenant:
            base_qs = CategoriaFornecedor.objects.filter(tenant=self.tenant, nome=nome)
            if self.instance and self.instance.pk:
                base_qs = base_qs.exclude(pk=self.instance.pk)
            if base_qs.exists():
                raise forms.ValidationError(_("Já existe uma categoria com este nome para esta empresa."))
        return nome


class FornecedorDocumentoVersaoCreateForm(forms.Form):
    """Form auxiliar para anexar uma nova versão de documento de fornecedor.

    Não usa ModelForm para permitir lógica customizada de seleção/criação de
    ``FornecedorDocumento`` pai antes de persistir a versão.
    """

    tipo = forms.ModelChoiceField(queryset=ItemAuxiliar.objects.none(), label=_("Tipo de Documento"))
    periodicidade = forms.ChoiceField(choices=FornecedorDocumento.PERIODICIDADE_CHOICES, label=_("Periodicidade"))
    exigencia = forms.ChoiceField(choices=FornecedorDocumento.EXIGENCIA_CHOICES, label=_("Exigência"))
    arquivo = forms.FileField(label=_("Arquivo"))
    competencia = forms.CharField(label=_("Competência (MM/AAAA)"), required=False)
    observacao = forms.CharField(label=_("Observação"), required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Inicializa filtrando somente tipos aplicáveis a fornecedor."""
        self.fornecedor = kwargs.pop("fornecedor", None)
        super().__init__(*args, **kwargs)
        qs = ItemAuxiliar.objects.filter(ativo=True)
        qs = qs.filter(models.Q(alvo="fornecedor") | models.Q(targets__code="fornecedor")).distinct()
        qs = qs.filter(categoria__slug__in=["documentos-da-empresa", "documentos-financeiros", "outros-documentos"])
        self.fields["tipo"].queryset = qs.order_by("categoria__ordem", "ordem", "nome")

    def clean_competencia(self) -> str | None:
        """Valida formato MM/AAAA quando informado."""
        comp = self.cleaned_data.get("competencia")
        if comp:
            comp = comp.strip()
            if not re.match(r"^(0[1-9]|1[0-2])\/(19|20)\d{2}$", comp):
                raise forms.ValidationError(_("Formato inválido. Use MM/AAAA."))
        return comp

    def save(self, user: Any | None = None) -> FornecedorDocumentoVersao:  # noqa: ANN401 - user pode ser qualquer User
        """Cria/atualiza o documento pai e adiciona uma nova versão."""
        if not self.fornecedor:
            msg = "fornecedor é obrigatório"
            raise ValueError(msg)
        tipo = self.cleaned_data["tipo"]
        periodicidade = self.cleaned_data["periodicidade"]
        exigencia = self.cleaned_data["exigencia"]
        arquivo = self.cleaned_data["arquivo"]
        competencia = self.cleaned_data.get("competencia") or None
        observacao = self.cleaned_data.get("observacao") or ""

        doc, _ = FornecedorDocumento.objects.get_or_create(
            fornecedor=self.fornecedor,
            tipo=tipo,
            defaults={"periodicidade": periodicidade, "exigencia": exigencia},
        )
        doc.periodicidade = periodicidade
        doc.exigencia = exigencia
        doc.save(update_fields=["periodicidade", "exigencia"])

        qs = doc.versoes
        if competencia:
            qs = qs.filter(competencia=competencia)
        current_max = qs.aggregate(models.Max("versao")).get("versao__max") or 0
        nova_versao_num = current_max + 1

        return FornecedorDocumentoVersao.objects.create(
            documento=doc,
            versao=nova_versao_num,
            arquivo=arquivo,
            usuario=user,
            observacao=observacao,
            competencia=competencia,
            status="enviado",
        )


class FornecedorDocumentoForm(forms.ModelForm):
    """Form simples para edição direta de metadados de um documento.

    Mantido por compatibilidade potencial (admin/scripts). Se não houver uso
    futuro poderá ser removido.
    """

    class Meta:
        """Configuração básica do ModelForm."""

        model = FornecedorDocumento
        fields: ClassVar[tuple[str, ...]] = ("fornecedor", "tipo", "periodicidade", "exigencia")

    widgets: ClassVar[Mapping[str, Any]] = {
        "fornecedor": forms.HiddenInput(),
        "tipo": forms.Select(attrs={"class": "form-select"}),
        "periodicidade": forms.Select(attrs={"class": "form-select"}),
        "exigencia": forms.Select(attrs={"class": "form-select"}),
    }

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Inicializa queryset de tipos dependendo do fornecedor passado."""
        fornecedor = kwargs.get("initial", {}).get("fornecedor") or kwargs.get("instance")
        super().__init__(*args, **kwargs)
        if fornecedor:
            self.fields["tipo"].queryset = ItemAuxiliar.objects.filter(
                categoria__slug__icontains="documento",
                ativo=True,
            )
