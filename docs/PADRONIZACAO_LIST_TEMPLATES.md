# Padronização de Listas Ultra-Modernas (`*_list.html`)

Guia atualizado (ref. `core/tenant_list.html` + `pandora_list_ultra_modern.html`). Objetivo: identidade visual consistente, zero CSS inline, reutilização total do template base.

Principais blocos suportados pelo base:
- `page_title`, `page_subtitle`
- `add_button_url` + `add_button_text` (botão criar)
- `table_content` (quando precisa markup custom) OU estrutura dinâmica via `object_list` + `table_columns` + `actions`
- `list_filters` (filtros customizados) – opcional

Evite duplicar lógica: priorize usar `table_columns`/`actions`. Use `table_content` apenas quando a linha exige layout complexo (avatar, badges compostas, etc.).

## 1) Template base obrigatório

- Todas as listas devem estender o template base: `pandora_list_ultra_modern.html`.
- Exemplo de cabeçalho do arquivo:

```django
{% extends "pandora_list_ultra_modern.html" %}
{% load i18n %}

{% block title %}{% trans "Módulo" %} - {{ block.super }}{% endblock %}
{% block page_title %}{% trans "Módulo" %}{% endblock %}
{% block page_subtitle %}{% trans "Descrição da lista" %}{% endblock %}
```

## 2) Estatísticas (cards do topo)

Passe uma lista `statistics` no contexto da view. Cada item suporta:
- `value` (número), `label` (texto), `icon` (classe FontAwesome)
- Cor: use preferencialmente `bg` e `text_color` (ex.: `bg-gradient-primary`, `text-primary`). Alternativamente, use `color` (ex.: `primary`, `success`, `warning`), e o base aplicará o gradiente/texto automaticamente.
- `url` (opcional) para tornar o card clicável.

Exemplo na view:

```python
context["statistics"] = [
    {"value": total, "label": _("Total"), "icon": "fas fa-database", "bg": "bg-gradient-primary", "text_color": "text-primary", "url": reverse("app:list")},
    {"value": ativos, "label": _("Ativos"), "icon": "fas fa-check", "bg": "bg-gradient-success", "text_color": "text-success", "url": f"{reverse('app:list')}?status=active"},
    {"value": inativos, "label": _("Inativos"), "icon": "fas fa-ban", "bg": "bg-gradient-secondary", "text_color": "text-secondary"},
    {"value": novos30, "label": _("Novos (30d)"), "icon": "fas fa-plus", "bg": "bg-gradient-warning", "text_color": "text-warning"},
]
```

## 3) Ações da página (botão adicionar)

- Use o bloco `add_button` para trocar o botão padrão quando necessário:

```django
{% block add_button %}
<a href="{{ add_url }}" class="btn btn-outline-secondary" title="{% trans 'Adicionar' %}">
  <i class="fas fa-plus"></i>
</a>
{% endblock %}
```

- Na view, informe `add_url` quando houver criação.

## 4) Tabela: duas abordagens

Abordagem A – Estrutura dinâmica (preferida para casos simples):
```python
context.update({
  'object_list': qs,
  'table_columns': [
      {'label': _('Nome'), 'field': 'nome', 'sortable': True},
      {'label': _('Status'), 'field': 'status'},
  ],
  'actions': [
      {'title': _('Editar'), 'icon': 'fas fa-edit', 'url': reverse('app:edit', args=['{id}']), 'class': 'btn-outline-primary'},
  ],
})
```

Abordagem B – Sobrescrever `table_content` (quando precisa avatar, badges multi-linha, cartões kanban ou grade específica). Ex.: `tenant_list.html`.
Diretrizes para custom:
- Manter classes: `table table-hover` e linha `d-flex gap-1` para ações.
- Largura de coluna de ações: usar classe `col-acoes` (base já estiliza) ou width ~160px.
- Usar badges padronizadas: `badge-ultra-modern badge-status-compact ...` conforme tenant.

```python
context.update({
  "object_list": queryset,
  "table_columns": [
      {"label": _("Nome"), "field": "nome", "sortable": True},
      {"label": _("Status"), "field": "status"},
  ],
  "actions": [
      {"title": _("Ver"), "icon": "fas fa-eye", "url": reverse("app:detail", args=["{id}"]), "class": "btn-outline-info"},
      {"title": _("Editar"), "icon": "fas fa-edit", "url": reverse("app:edit", args=["{id}"]), "class": "btn-outline-primary"},
      {"title": _("Excluir"), "icon": "fas fa-trash", "url": reverse("app:delete", args=["{id}"]), "class": "btn-outline-danger", "confirm": True},
  ],
  # opcional
  "bulk_actions": [
      {"label": _("Ativar"), "icon": "fas fa-check", "action": "activate"},
      {"label": _("Desativar"), "icon": "fas fa-ban", "action": "deactivate", "confirm": _("Confirmar desativação?")},
  ],
})
```

B) Sobrescrever apenas o conteúdo da tabela
- Quando a estrutura for muito específica, sobrescreva `{% block table_content %}` no template do módulo e renderize sua própria `<table>`. Continue usando as classes utilitárias e componentes do design; não adicione CSS inline.

Exemplo mínimo:

```django
{% block table_content %}
{% if object_list %}
  <div class="table-responsive">
    <table class="table table-hover table-sm">
      <thead class="table-header">
        <tr>
          <th>{% trans "Nome" %}</th>
          <th>{% trans "Status" %}</th>
          <th width="160">{% trans "Ações" %}</th>
        </tr>
      </thead>
      <tbody>
        {% for obj in object_list %}
        <tr>
          <td>{{ obj.nome }}</td>
          <td>{{ obj.status }}</td>
          <td width="160">
            <div class="d-flex gap-1">
              <a href="{# detail url #}" class="btn btn-outline-info btn-action-sm" title="{% trans 'Ver' %}"><i class="fas fa-eye"></i></a>
              <a href="{# edit url #}" class="btn btn-outline-primary btn-action-sm" title="{% trans 'Editar' %}"><i class="fas fa-edit"></i></a>
              <a href="{# delete url #}" class="btn btn-outline-danger btn-action-sm" title="{% trans 'Excluir' %}"><i class="fas fa-trash"></i></a>
            </div>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% else %}
  {{ block.super }} {# usa empty-state padrão do base #}
{% endif %}
{% endblock %}
```

Observação: padronizamos a largura da coluna "Ações" em ~160px para comportar 3–4 botões sem truncar.

## 5) Filtros e busca

- Busca rápida: informe `search_query` no contexto para preencher o input do painel de busca.
- Filtros avançados (opcional): passe `filters` como lista de dicts com `{name, label, type, options|value|placeholder}`.
- Tipos aceitos por padrão: `select`, `date`, `text`.

Exemplo:

```python
context["search_query"] = request.GET.get("q", "")
context["filters"] = [
  {"name": "status", "label": _("Status"), "type": "select", "options": [
      {"label": _("Todos"), "value": "", "selected": request.GET.get("status", "") == ""},
      {"label": _("Ativo"), "value": "active", "selected": request.GET.get("status") == "active"},
  ]},
  {"name": "inicio", "label": _("Início"), "type": "date", "value": request.GET.get("inicio")},
]
```

## 6) Empty state

Não replique empty-states nos templates de módulo. Quando a lista estiver vazia, deixe o base renderizar o estado padrão. Se precisar de CTA, passe `add_url` no contexto.

## 7) Boas práticas de UI

- Ícones em botões devem ter `title` (tooltip) para acessibilidade.
- Use `btn-action-sm` para ações compactas em tabelas.
- Mantenha os avatares/indicadores consistentes com outros módulos (ex.: `avatar-sm`, `avatar-placeholder`).
- Evite `style="..."` em qualquer elemento. Qualquer ajuste deve ser via classes ou parâmetros aceitos pelo base.

## 8) Passo-a-passo para migrar / revisar

1. Extender `pandora_list_ultra_modern.html`.
2. Definir blocos: `title`, `page_title`, `page_subtitle`.
3. Passar `add_button_url` e opcional `add_button_text` (senão base mostra padrão).
4. Implementar estatísticas se relevantes (`statistics`).
5. Escolher abordagem da tabela (A ou B). Evitar markup manual quando dinâmica atende.
6. Nenhum `style=""` inline (auditar com busca literal).
7. Ações sempre usam `btn-action-sm` + outline.
8. Empty-state: nunca duplicar, deixar base exibir (ou usar `{{ block.super }}` dentro de override custom).
9. Evitar scripts inline repetitivos; se houver JS específico, considerar modularizar.

## 9) Exemplo de view completa (padrão)

```python
class ItemListView(ListView):
    model = Item
    template_name = "app/item_list.html"
    context_object_name = "object_list"  # recomendado para alinhar com o base
    paginate_by = 25

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = ctx["object_list"]
        ctx.update({
            "page_title": _("Itens"),
            "page_subtitle": _("Gerencie todos os itens"),
            "add_url": reverse("app:item_create"),
            "statistics": [
                {"value": qs.count(), "label": _("Total"), "icon": "fas fa-boxes", "bg": "bg-gradient-primary", "text_color": "text-primary"},
                {"value": qs.filter(status="active").count(), "label": _("Ativos"), "icon": "fas fa-check", "bg": "bg-gradient-success", "text_color": "text-success"},
            ],
            "table_columns": [
                {"label": _("Nome"), "field": "nome", "sortable": True},
                {"label": _("Status"), "field": "status"},
            ],
            "actions": [
                {"title": _("Ver"), "icon": "fas fa-eye", "url": reverse("app:item_detail", args=["{id}"]), "class": "btn-outline-info"},
                {"title": _("Editar"), "icon": "fas fa-edit", "url": reverse("app:item_edit", args=["{id}"]), "class": "btn-outline-primary"},
                {"title": _("Excluir"), "icon": "fas fa-trash", "url": reverse("app:item_delete", args=["{id}"]), "class": "btn-outline-danger", "confirm": True},
            ],
        })
        return ctx
```

## 10) Conformidade

Checklist rápido (aplicar antes de abrir PR interno):
- [ ] Sem `style="` inline
- [ ] Usa base e blocos corretos
- [ ] Botão adicionar via `add_button_url`
- [ ] Ações com `btn-action-sm`
- [ ] Empty-state padrão preservado
- [ ] Estatísticas coerentes (se existirem)
- [ ] Sem JS redundante já coberto pelo base

Auditoria: grep global por `style="` dentro de `*_list.html` exceto o template base.

---

Dúvidas ou melhorias? Registre nos documentos do projeto e mantenha este guia atualizado conforme evoluírem os componentes do template base.
