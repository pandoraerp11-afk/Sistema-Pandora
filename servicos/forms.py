# servicos/forms.py

from django import forms
from django.forms import modelformset_factory
from django.utils.translation import gettext_lazy as _

# Importações de outros apps
from cadastros_gerais.forms import BasePandoraForm

# Importações locais
from .models import (
    Avaliacao,
    CategoriaServico,
    RegraCobranca,
    Servico,
    ServicoClinico,
    ServicoDocumento,
    ServicoFornecedor,
    ServicoImagem,
)


class CategoriaServicoForm(BasePandoraForm):
    class Meta:
        model = CategoriaServico
        fields = ["nome", "slug", "descricao", "ativo"]
        widgets = {
            "slug": forms.TextInput(attrs={"placeholder": _("Gerado automaticamente se em branco")}),
        }
        labels = {
            "nome": _("Nome da Categoria"),
        }
        help_texts = {
            "slug": _("Usado na URL. Deixe em branco para ser gerado automaticamente a partir do nome."),
        }


class RegraCobrancaForm(BasePandoraForm):
    class Meta:
        model = RegraCobranca
        fields = [
            "nome",
            "descricao",
            "unidade_medida",
            "valor_base",
            "valor_minimo",
            "incremento",
            "taxa_adicional",
            "tipo_calculo",
            "formula_personalizada",
            "ativo",
        ]
        widgets = {
            "formula_personalizada": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": _("Ex: (Q * {vb}) + ({ta} / 100 * Q * {vb})").format(
                        vb=RegraCobranca._meta.get_field("valor_base").verbose_name,
                        ta=RegraCobranca._meta.get_field("taxa_adicional").verbose_name,
                    ),
                }
            ),
        }
        help_texts = {
            "valor_minimo": _("Opcional. Deixe 0 ou em branco se não houver valor mínimo."),
            "taxa_adicional": _("Opcional. Percentual a ser adicionado (ex: 10 para 10%)."),
            "formula_personalizada": _("Apenas para 'Tipo de Cálculo' personalizado. Use 'Q' para quantidade."),
        }


class ServicoForm(BasePandoraForm):
    class Meta:
        model = Servico
        fields = [
            "tipo_servico",
            "is_clinical",
            "nome_servico",
            "slug",
            "categoria",
            "imagem_principal",
            "clientes",  # Adicionado para vincular clientes
            "descricao_curta",
            "descricao",
            "regra_cobranca",
            "preco_base",
            "tempo_estimado",
            "prazo_entrega",
            "materiais_inclusos",
            "materiais_nao_inclusos",
            "requisitos",
            "disponivel_online",
            "requer_visita_tecnica",
            "requer_aprovacao",
            "palavras_chave",
            "destaque",
            "ativo",
        ]
        widgets = {
            "tipo_servico": forms.Select(attrs={"class": "form-control select2", "id": "id_tipo_servico"}),
            "clientes": forms.SelectMultiple(attrs={"class": "form-control select2"}),
            "descricao": forms.Textarea(attrs={"rows": 8}),
            "descricao_curta": forms.Textarea(attrs={"rows": 2}),
            "materiais_inclusos": forms.Textarea(attrs={"rows": 3}),
            "materiais_nao_inclusos": forms.Textarea(attrs={"rows": 3}),
            "requisitos": forms.Textarea(attrs={"rows": 3}),
            "palavras_chave": forms.TextInput(
                attrs={"placeholder": _("Ex: limpeza de escritórios, manutenção predial")}
            ),
            "slug": forms.TextInput(attrs={"placeholder": _("Gerado automaticamente se em branco")}),
            "tempo_estimado": forms.TextInput(attrs={"placeholder": _("Ex: 2 horas, 1 dia útil")}),
            "prazo_entrega": forms.NumberInput(attrs={"placeholder": _("Em dias")}),
        }
        help_texts = {
            "slug": _("Usado na URL. Deixe em branco para ser gerado automaticamente."),
            "palavras_chave": _("Separadas por vírgula, para SEO e busca interna."),
            "regra_cobranca": _("Regra de cobrança para seus 'Serviços Ofertados'."),
            "preco_base": _(
                "Para 'Serviços Ofertados', este é o seu preço de venda. Para 'Serviços Contratados', este é apenas um valor de referência."
            ),
            "clientes": _("Associe clientes a este serviço. Visível apenas para 'Serviços Ofertados'."),
        }
        labels = {
            "nome_servico": _("Nome do Serviço"),
            "disponivel_online": _("Disponível para contratação/agendamento online?"),
            "requer_visita_tecnica": _("Requer visita técnica para orçamento/execução?"),
            "requer_aprovacao": _("Requer aprovação de orçamento antes da execução?"),
            "destaque": _("Marcar como serviço em destaque na listagem?"),
            "is_clinical": _("É um Serviço Clínico?"),
        }


class ServicoClinicoForm(BasePandoraForm):
    """Form separado para os campos do perfil clínico.
    Mantém separação de responsabilidades (evita multi-model save no ModelForm principal).
    """

    duracao_estimada = forms.CharField(
        label=_("Duração Estimada"),
        help_text=_("Formato HH:MM ou HH:MM:SS. Ex: 00:30 para 30 minutos."),
        widget=forms.TextInput(attrs={"placeholder": "00:30"}),
    )

    class Meta:
        model = ServicoClinico
        fields = [
            "duracao_estimada",
            "requisitos_pre_procedimento",
            "contraindicacoes",
            "cuidados_pos_procedimento",
            "requer_anamnese",
            "requer_termo_consentimento",
            "permite_fotos_evolucao",
            "intervalo_minimo_sessoes",
        ]
        widgets = {
            "requisitos_pre_procedimento": forms.Textarea(attrs={"rows": 2}),
            "contraindicacoes": forms.Textarea(attrs={"rows": 2}),
            "cuidados_pos_procedimento": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "requisitos_pre_procedimento": _("Requisitos Pré-Procedimento"),
            "cuidados_pos_procedimento": _("Cuidados Pós-Procedimento"),
            "requer_anamnese": _("Requer Anamnese"),
            "requer_termo_consentimento": _("Requer Termo de Consentimento"),
            "permite_fotos_evolucao": _("Permitir Fotos de Evolução"),
            "intervalo_minimo_sessoes": _("Intervalo Mínimo entre Sessões (dias)"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Se houver instance e duracao_estimada for um timedelta, formata
        inst = getattr(self, "instance", None)
        if inst and getattr(inst, "duracao_estimada", None):
            td = inst.duracao_estimada
            total_seconds = int(td.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            # Se segundos forem 0, omitimos para simplificar
            if seconds == 0:
                self.initial["duracao_estimada"] = f"{hours:02d}:{minutes:02d}"
            else:
                self.initial["duracao_estimada"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def clean_duracao_estimada(self):
        value = self.cleaned_data.get("duracao_estimada")
        if not value:
            return None
        value = value.strip()
        # Normaliza para HH:MM:SS
        import re

        if re.fullmatch(r"\d{1,2}:\d{2}$", value):
            value = value + ":00"
        if not re.fullmatch(r"\d{1,2}:\d{2}:\d{2}$", value):
            raise forms.ValidationError(_("Formato inválido. Use HH:MM ou HH:MM:SS."))
        # Converte para timedelta
        from datetime import timedelta

        h, m, s = map(int, value.split(":"))
        return timedelta(hours=h, minutes=m, seconds=s)


class ServicoFornecedorForm(BasePandoraForm):
    class Meta:
        model = ServicoFornecedor
        fields = ["fornecedor", "preco_base_fornecedor", "regra_cobranca_fornecedor", "codigo_fornecedor"]
        widgets = {
            "fornecedor": forms.Select(attrs={"class": "form-control select2"}),
            "regra_cobranca_fornecedor": forms.Select(attrs={"class": "form-control select2"}),
        }


ServicoFornecedorFormSet = modelformset_factory(ServicoFornecedor, form=ServicoFornecedorForm, extra=0, can_delete=True)


class ServicoImagemForm(BasePandoraForm):
    class Meta:
        model = ServicoImagem
        fields = ["imagem", "titulo", "descricao", "ordem"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "imagem": _("Ficheiro da Imagem"),
            "titulo": _("Título da Imagem (Opcional)"),
            "descricao": _("Descrição da Imagem (Opcional)"),
        }


class ServicoDocumentoForm(BasePandoraForm):
    class Meta:
        model = ServicoDocumento
        fields = ["titulo", "arquivo", "tipo"]
        labels = {
            "titulo": _("Título do Documento"),
            "arquivo": _("Ficheiro do Documento"),
            "tipo": _("Tipo de Documento"),
        }


class AvaliacaoForm(BasePandoraForm):
    class Meta:
        model = Avaliacao
        fields = ["nome_cliente", "email_cliente", "nota", "comentario"]
        widgets = {
            "nota": forms.Select(),
            "comentario": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "nome_cliente": _("O seu nome"),
            "email_cliente": _("O seu e-mail (opcional)"),
            "nota": _("A sua nota (1 a 5)"),
            "comentario": _("O seu comentário"),
        }


class CalculoPrecoForm(forms.Form):
    quantidade = forms.DecimalField(
        label=_("Quantidade"),
        initial=1,
        min_value=0.01,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}),
    )

    def __init__(self, *args, servico=None, **kwargs):
        super().__init__(*args, **kwargs)
        if servico and servico.regra_cobranca:
            unidade_medida = servico.regra_cobranca.unidade_medida
            self.fields["quantidade"].label = unidade_medida.nome
            self.fields["quantidade"].help_text = _("Insira a quantidade em {unidade} ({simbolo})").format(
                unidade=unidade_medida.nome.lower(), simbolo=unidade_medida.simbolo
            )
        elif servico:
            self.fields["quantidade"].label = _("Quantidade (para preço base)")
            self.fields["quantidade"].help_text = _("Normalmente 1 para serviços de preço fixo.")
