import csv
import io

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

# cadastros_gerais/views.py
from django.views.generic import CreateView, DeleteView, UpdateView
from django_filters.views import FilterView
from django_tables2 import SingleTableView

from core.utils import get_current_tenant

# Importando o Mixin do local correto e centralizado: 'core'
from core.views import PageTitleMixin

from .filters import UnidadeMedidaFilter
from .forms import UnidadeMedidaForm, UnidadeMedidaImportForm
from .models import AlvoAplicacao, CategoriaAuxiliar, ItemAuxiliar, UnidadeMedida
from .tables import UnidadeMedidaTable


@login_required
def cadastros_gerais_home(request):
    """
    Página Home do módulo Cadastros Gerais (sem dashboard), seguindo a mesma
    estrutura visual de core_home.html (pandora_home_ultra_modern).
    """
    template_name = "cadastros_gerais/cadastros_gerais_home.html"
    tenant = get_current_tenant(request)

    # Permitir que superusuários acessem sem selecionar empresa
    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver a página."))
        return redirect(reverse("core:tenant_select"))

    # Contadores para os cards da Home
    total_unidades = UnidadeMedida.objects.count()
    total_categorias_aux = CategoriaAuxiliar.objects.count()
    total_itens_aux = ItemAuxiliar.objects.count()

    context = {
        "titulo": _("Cadastros Gerais"),
        "subtitulo": _("Central de cadastros básicos e auxiliares do sistema"),
        "tenant": tenant,
        "total_unidades": total_unidades,
        "total_categorias_aux": total_categorias_aux,
        "total_itens_aux": total_itens_aux,
    }

    return render(request, template_name, context)


class UnidadeMedidaListView(LoginRequiredMixin, PageTitleMixin, FilterView, SingleTableView):
    model = UnidadeMedida
    table_class = UnidadeMedidaTable
    filterset_class = UnidadeMedidaFilter
    template_name = "cadastros_gerais/unidade_medida_list.html"
    paginate_by = 10
    page_title = _("Unidades de Medida")


class UnidadeMedidaCreateView(LoginRequiredMixin, PageTitleMixin, CreateView):
    model = UnidadeMedida
    form_class = UnidadeMedidaForm
    template_name = "cadastros_gerais/unidade_medida_form.html"
    success_url = reverse_lazy("cadastros_gerais:unidade_medida_list")
    page_title = _("Adicionar Nova Unidade de Medida")

    def form_valid(self, form):
        messages.success(self.request, _('Unidade de Medida "{}" criada com sucesso!').format(form.instance.nome))
        return super().form_valid(form)


class UnidadeMedidaUpdateView(LoginRequiredMixin, PageTitleMixin, UpdateView):
    model = UnidadeMedida
    form_class = UnidadeMedidaForm
    template_name = "cadastros_gerais/unidade_medida_form.html"
    success_url = reverse_lazy("cadastros_gerais:unidade_medida_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.page_title = _("Editar Unidade de Medida")
        self.page_subtitle = self.object.nome
        return context

    def form_valid(self, form):
        messages.success(self.request, _('Unidade de Medida "{}" atualizada com sucesso!').format(form.instance.nome))
        return super().form_valid(form)


class UnidadeMedidaDeleteView(LoginRequiredMixin, PageTitleMixin, DeleteView):
    model = UnidadeMedida
    template_name = "cadastros_gerais/generic_confirm_delete.html"
    success_url = reverse_lazy("cadastros_gerais:unidade_medida_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.page_title = _("Excluir Unidade de Medida")
        self.page_subtitle = self.object.nome
        context["cancel_url"] = self.success_url
        return context

    def post(self, request, *args, **kwargs):
        nome_obj = self.get_object().nome
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(request, _('Unidade de Medida "{}" excluída com sucesso!').format(nome_obj))
            return response
        except Exception:
            messages.error(
                request,
                _('Não foi possível excluir "{}". Esta unidade de medida provavelmente está em uso.').format(nome_obj),
            )
            return redirect(self.success_url)


@login_required
def unidade_medida_import(request):
    page_title = _("Importar Unidades de Medida")
    form = UnidadeMedidaImportForm()

    if request.method == "POST":
        form = UnidadeMedidaImportForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo_csv = request.FILES["arquivo"]

            if not arquivo_csv.name.endswith(".csv"):
                messages.error(request, _("Este não é um arquivo CSV válido."))
                return redirect("cadastros_gerais:unidade_medida_import")

            try:
                data_set = arquivo_csv.read().decode("UTF-8")
                io_string = io.StringIO(data_set)
                next(io_string)
                importados_count = 0
                reader = csv.reader(io_string, delimiter=";")
                for linha in reader:
                    if len(linha) < 2:
                        continue
                    nome_unidade = linha[0].strip()
                    simbolo_unidade = linha[1].strip()
                    descricao_unidade = linha[2].strip() if len(linha) > 2 else ""
                    _, created = UnidadeMedida.objects.get_or_create(
                        simbolo=simbolo_unidade,
                        defaults={"nome": nome_unidade, "descricao": descricao_unidade},
                    )
                    if created:
                        importados_count += 1
                messages.success(
                    request, f"{importados_count} unidades de medida foram importadas/atualizadas com sucesso."
                )
                return redirect("cadastros_gerais:unidade_medida_list")

            except Exception as e:
                messages.error(request, _(f"Ocorreu um erro ao processar o arquivo: {e}"))
                return redirect("cadastros_gerais:unidade_medida_import")

    context = {"page_title": page_title, "page_subtitle": "Importação em lote via CSV", "form": form}
    return render(request, "cadastros_gerais/unidade_medida_import.html", context)


# Tabelas simples internas (evitar criar arquivos neste passo)
import django_tables2 as tables


class CategoriaAuxiliarTable(tables.Table):
    class Meta:
        model = CategoriaAuxiliar
        fields = ("nome", "slug", "ativo", "ordem")
        attrs = {"class": "table table-hover table-striped"}
        template_name = "django_tables2/bootstrap5.html"


class ItemAuxiliarTable(tables.Table):
    alvos = tables.Column(verbose_name=_("Aplicado em"), accessor="alvos_display")

    class Meta:
        model = ItemAuxiliar
        fields = ("nome", "categoria", "ativo", "ordem")
        attrs = {"class": "table table-hover table-striped"}
        template_name = "django_tables2/bootstrap5.html"
        sequence = ("nome", "categoria", "alvos", "ativo", "ordem")


class CategoriaAuxiliarListView(LoginRequiredMixin, PageTitleMixin, SingleTableView):
    model = CategoriaAuxiliar
    table_class = CategoriaAuxiliarTable
    template_name = "cadastros_gerais/auxiliar_categoria_list.html"
    paginate_by = 10
    page_title = _("Categorias Auxiliares")


class ItemAuxiliarListView(LoginRequiredMixin, PageTitleMixin, SingleTableView):
    model = ItemAuxiliar
    table_class = ItemAuxiliarTable
    template_name = "cadastros_gerais/auxiliar_item_list.html"
    paginate_by = 10
    page_title = _("Itens Auxiliares")


class CategoriaAuxiliarForm(forms.ModelForm):
    class Meta:
        model = CategoriaAuxiliar
        fields = ["nome", "descricao", "ativo", "ordem"]  # slug oculto/automático
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": _("Ex.: Documentos da Empresa")}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def save(self, commit=True):
        obj = super().save(commit=False)
        # slug será gerado no save() do model caso vazio
        if commit:
            obj.save()
        return obj


TIPOS_CAMPO = (
    ("arquivo", _("Arquivo")),
    ("texto", _("Texto")),
    ("numero", _("Número")),
    ("data", _("Data")),
    ("selecao", _("Seleção")),
)


class ItemAuxiliarForm(forms.ModelForm):
    # Campos amigáveis para popular config
    tipo_campo = forms.ChoiceField(
        choices=TIPOS_CAMPO, label=_("Tipo de Campo"), widget=forms.Select(attrs={"class": "form-select"})
    )
    obrigatorio = forms.BooleanField(
        label=_("Obrigatório"), required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    multiplos = forms.BooleanField(
        label=_("Permitir múltiplos"), required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    extensoes_permitidas = forms.CharField(
        label=_("Extensões permitidas"),
        required=False,
        help_text=_("Ex.: pdf,jpg,png"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    tamanho_max_mb = forms.IntegerField(
        label=_("Tamanho máximo (MB)"),
        required=False,
        initial=10,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    validade_dias = forms.IntegerField(
        label=_("Validade (dias)"), required=False, widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    opcoes = forms.CharField(
        label=_("Opções (para Seleção, separadas por vírgula)"),
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = ItemAuxiliar
        fields = [
            "categoria",
            "nome",
            "descricao",
            "targets",
            "ativo",
            "ordem",
            "tipo_campo",
            "obrigatorio",
            "multiplos",
            "extensoes_permitidas",
            "tamanho_max_mb",
            "validade_dias",
            "opcoes",
        ]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "targets": forms.CheckboxSelectMultiple(attrs={"class": "list-unstyled mb-0"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Preencher defaults a partir do config existente ao editar
        if self.instance and self.instance.pk and isinstance(self.instance.config, dict):
            cfg = self.instance.config or {}
            self.fields["tipo_campo"].initial = cfg.get("tipo", "arquivo")
            self.fields["obrigatorio"].initial = cfg.get("obrigatorio", False)
            self.fields["multiplos"].initial = cfg.get("multiplos", False)
            self.fields["extensoes_permitidas"].initial = (
                ",".join(cfg.get("extensoes", [])) if cfg.get("extensoes") else ""
            )
            self.fields["tamanho_max_mb"].initial = cfg.get("tamanho_max_mb", 10)
            self.fields["validade_dias"].initial = cfg.get("validade_dias")
            if cfg.get("opcoes"):
                self.fields["opcoes"].initial = ",".join(cfg.get("opcoes"))

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo_campo")
        # Validações simples
        if tipo == "arquivo":
            # tamanho e extensões fazem sentido
            pass
        if tipo == "selecao" and not cleaned.get("opcoes"):
            self.add_error("opcoes", _("Informe as opções para seleção"))
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        tipo = self.cleaned_data.get("tipo_campo")
        cfg = {
            "tipo": tipo,
            "obrigatorio": bool(self.cleaned_data.get("obrigatorio")),
            "multiplos": bool(self.cleaned_data.get("multiplos")),
        }
        if self.cleaned_data.get("extensoes_permitidas"):
            cfg["extensoes"] = [
                e.strip().lower() for e in self.cleaned_data["extensoes_permitidas"].split(",") if e.strip()
            ]
        if self.cleaned_data.get("tamanho_max_mb") is not None:
            cfg["tamanho_max_mb"] = int(self.cleaned_data["tamanho_max_mb"])
        if self.cleaned_data.get("validade_dias") is not None:
            cfg["validade_dias"] = int(self.cleaned_data["validade_dias"])
        if tipo == "selecao" and self.cleaned_data.get("opcoes"):
            cfg["opcoes"] = [o.strip() for o in self.cleaned_data["opcoes"].split(",") if o.strip()]

        instance.config = cfg
        # Preencher campo legado 'alvo' quando houver somente 1 target
        if not instance.pk:
            # manter compatibilidade
            targets = self.cleaned_data.get("targets")
            if targets and len(targets) == 1:
                code = targets[0].code if hasattr(targets[0], "code") else None
                mapping = {
                    "cliente": "cliente",
                    "fornecedor": "fornecedor",
                    "funcionario": "funcionario",
                    "empresa": "empresa",
                    "produto": "produto",
                    "servico": "servico",
                    "outro": "outro",
                }
                instance.alvo = mapping.get(code, "outro")
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CategoriaAuxiliarCreateView(LoginRequiredMixin, PageTitleMixin, CreateView):
    model = CategoriaAuxiliar
    form_class = CategoriaAuxiliarForm
    template_name = "cadastros_gerais/auxiliar_categoria_form.html"
    success_url = reverse_lazy("cadastros_gerais:categoria_aux_list")
    page_title = _("Nova Categoria Auxiliar")


class CategoriaAuxiliarUpdateView(LoginRequiredMixin, PageTitleMixin, UpdateView):
    model = CategoriaAuxiliar
    form_class = CategoriaAuxiliarForm
    template_name = "cadastros_gerais/auxiliar_categoria_form.html"
    success_url = reverse_lazy("cadastros_gerais:categoria_aux_list")
    page_title = _("Editar Categoria Auxiliar")


class CategoriaAuxiliarDeleteView(LoginRequiredMixin, PageTitleMixin, DeleteView):
    model = CategoriaAuxiliar
    template_name = "cadastros_gerais/generic_confirm_delete.html"
    success_url = reverse_lazy("cadastros_gerais:categoria_aux_list")


class ItemAuxiliarCreateView(LoginRequiredMixin, PageTitleMixin, CreateView):
    model = ItemAuxiliar
    form_class = ItemAuxiliarForm
    template_name = "cadastros_gerais/auxiliar_item_form.html"
    success_url = reverse_lazy("cadastros_gerais:item_aux_list")
    page_title = _("Novo Item Auxiliar")


class ItemAuxiliarUpdateView(LoginRequiredMixin, PageTitleMixin, UpdateView):
    model = ItemAuxiliar
    form_class = ItemAuxiliarForm
    template_name = "cadastros_gerais/auxiliar_item_form.html"
    success_url = reverse_lazy("cadastros_gerais:item_aux_list")
    page_title = _("Editar Item Auxiliar")


class ItemAuxiliarDeleteView(LoginRequiredMixin, PageTitleMixin, DeleteView):
    model = ItemAuxiliar
    template_name = "cadastros_gerais/generic_confirm_delete.html"
    success_url = reverse_lazy("cadastros_gerais:item_aux_list")


# Ação rápida: criar presets de documentos
@login_required
def criar_presets_documentos(request):
    """Cria categorias e itens padrão de documentos com multi-alvo (empresa, fornecedor, cliente)."""
    # garantir alvos
    alvos = {
        "empresa": AlvoAplicacao.objects.get_or_create(code="empresa", defaults={"nome": _("Empresa/Tenant")})[0],
        "fornecedor": AlvoAplicacao.objects.get_or_create(code="fornecedor", defaults={"nome": _("Fornecedor")})[0],
        "cliente": AlvoAplicacao.objects.get_or_create(code="cliente", defaults={"nome": _("Cliente")})[0],
    }

    def cfg_doc(obrigatorio=False, multiplos=False):
        return {
            "tipo": "arquivo",
            "obrigatorio": obrigatorio,
            "multiplos": multiplos,
            "extensoes": ["pdf", "jpg", "png"],
            "tamanho_max_mb": 10,
        }

    cat_docs, created_docs = CategoriaAuxiliar.objects.get_or_create(nome=_("Documentos da Empresa"))
    cat_fin, created_fin = CategoriaAuxiliar.objects.get_or_create(nome=_("Documentos Financeiros"))
    cat_outros, created_outros = CategoriaAuxiliar.objects.get_or_create(nome=_("Outros Documentos"))

    itens_por_cat = {
        cat_docs: [
            (_("Contrato Social"), True),
            (_("Cartão CNPJ"), True),
            (_("Inscrição Estadual"), False),
            (_("Alvará de Funcionamento"), False),
        ],
        cat_fin: [
            (_("Comprovante de Endereço"), False),
            (_("Balanço Patrimonial"), False),
            (_("DRE (Demonstração de Resultados)"), False),
            (_("Certidões Negativas"), False),
        ],
        cat_outros: [
            (_("Procuração (se aplicável)"), False),
            (_("Documentos Adicionais"), False),
        ],
    }

    total_criados = 0
    for cat, itens in itens_por_cat.items():
        for nome, obrigatorio in itens:
            item, created_item = ItemAuxiliar.objects.get_or_create(
                categoria=cat,
                slug=slugify(nome),
                defaults={
                    "nome": nome,
                    "config": cfg_doc(obrigatorio=obrigatorio),
                },
            )
            if created_item:
                total_criados += 1
            # aplicar alvos multi
            item.targets.set([alvos["empresa"], alvos["fornecedor"], alvos["cliente"]])
            # manter compat com campo legado, define 'empresa'
            if created_item:
                item.alvo = "empresa"
                item.save()

    messages.success(request, _("Presets criados/atualizados. Itens afetados: %(qtd)s.") % {"qtd": total_criados})
    return redirect("cadastros_gerais:dashboard")
