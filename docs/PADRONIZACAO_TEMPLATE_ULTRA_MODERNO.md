# 📋 Guia de Padronização - Template Ultra Moderno Pandora ERP

## 📊 SISTEMA DE DASHBOARDS (ESCLARECIMENTO)

### **Estrutura Atual**

#### **1. Dashboards Específicos por Módulo**
- ✅ **32 dashboards implementados** (um para cada módulo)
- ✅ **Padrão**: `{modulo}_dashboard.html`
- ✅ **Localização**: `{modulo}/templates/{modulo}/{modulo}_dashboard.html`

#### **2. Engine Universal**
- ✅ **Template base**: `templates/pandora_dashboard_ultra_modern.html`
- ✅ **CSS único**: `static/dist/css/pandora-ultra-modern.css`
- ✅ **JS único**: `static/dist/js/pandora-ultra-modern.js`

#### **3. Dashboard Geral** 
- ❌ **Ainda não implementado**
- 🎯 **Objetivo futuro**: Visão consolidada de todos os módulos

## 🎯 Objetivo
Este documento estabelece a padronização para implementação da hierarquia de templates ultra-modernos em todos os módulos do Pandora ERP, garantindo consistência visual, funcional e de experiência do usuário.

## 🏗️ Hierarquia de Templates Base

### 1. Template Principal
```
templates/pandora_ultra_modern_base.html
```
- **Função**: Template base principal com estrutura HTML, CSS e JavaScript
- **Contém**: Meta tags, Bootstrap 5.3.2, Font Awesome, Alpine.js, AOS animations
- **Blocos principais**: `title`, `extra_css`, `content`, `extra_js`

### 2. Templates Especializados
```
templates/pandora_dashboard_ultra_modern.html     → Dashboard widgets
templates/pandora_list_ultra_modern.html          → Listagens com filtros
templates/pandora_form_ultra_modern.html          → Formulários multi-seção
templates/pandora_detail_ultra_modern.html        → Visualização detalhada
templates/pandora_confirm_delete_ultra_modern.html → Confirmação de exclusão
templates/pandora_home_ultra_modern.html          → Páginas home dos módulos
```

## 📁 Estrutura de Arquivos por Módulo

Para cada módulo (exemplo: `fornecedores`):

```
app_name/
├── templates/
│   └── app_name/
│       ├── app_name_dashboard.html      → Dashboard do módulo
│       ├── app_name_list.html           → Lista de registros
│       ├── app_name_form.html           → Formulário (create/edit)
│       ├── app_name_detail.html         → Detalhes do registro
│       └── app_name_confirm_delete.html → Confirmação de exclusão
├── views.py
├── urls.py
├── models.py
└── forms.py
```

## 🎨 Padrões de Template por Tipo

### 1. Dashboard Template (`app_name_dashboard.html`)

```django
{% extends "pandora_dashboard_ultra_modern.html" %}
{% load static %}

{% block title %}Dashboard - Nome do Módulo{% endblock %}

{% block dashboard_title %}Nome do Módulo{% endblock %}
{% block dashboard_subtitle %}Gestão completa de [descrição]{% endblock %}
{% block dashboard_icon %}fas fa-[icone-apropriado]{% endblock %}

{% block dashboard_widgets %}
<div class="row mb-4">
    <!-- Widget de Estatísticas -->
    <div class="col-xl-3 col-md-6 mb-3">
        {% include 'widgets/stat_widget.html' with title="Total" value=total_count icon="fas fa-list" color="primary" %}
    </div>
    
    <div class="col-xl-3 col-md-6 mb-3">
        {% include 'widgets/stat_widget.html' with title="Ativos" value=active_count icon="fas fa-check-circle" color="success" %}
    </div>
    
    <!-- Mais widgets conforme necessário -->
</div>

<!-- Gráficos e Tabelas -->
<div class="row">
    <div class="col-lg-8">
        {% include 'widgets/chart_widget.html' with title="Gráfico Principal" chart_id="main-chart" %}
    </div>
    
    <div class="col-lg-4">
        {% include 'widgets/list_widget.html' with title="Itens Recentes" items=recent_items %}
    </div>
</div>
{% endblock %}

{% block dashboard_actions %}
<a href="{% url 'app_name:create' %}" class="btn btn-primary">
    <i class="fas fa-plus me-2"></i> Novo Item
</a>
<a href="{% url 'app_name:list' %}" class="btn btn-outline-primary">
    <i class="fas fa-list me-2"></i> Ver Todos
</a>
{% endblock %}
```

### 2. List Template (`app_name_list.html`)

```django
{% extends "pandora_list_ultra_modern.html" %}
{% load static %}

{% block title %}Lista - Nome do Módulo{% endblock %}

{% block list_title %}Nome do Módulo{% endblock %}
{% block list_subtitle %}Gestão de todos os registros{% endblock %}
{% block list_icon %}fas fa-[icone-apropriado]{% endblock %}

{% block list_actions %}
<a href="{% url 'app_name:create' %}" class="btn btn-primary">
    <i class="fas fa-plus me-2"></i> Novo Item
</a>
<a href="{% url 'app_name:dashboard' %}" class="btn btn-outline-secondary">
    <i class="fas fa-chart-bar me-2"></i> Dashboard
</a>
{% endblock %}

{% block list_filters %}
<form method="get" class="filter-form">
    <div class="row g-3">
        <div class="col-md-4">
            <label class="form-label">Nome</label>
            <input type="text" name="nome" class="form-control" value="{{ request.GET.nome }}" placeholder="Buscar por nome...">
        </div>
        
        <div class="col-md-3">
            <label class="form-label">Status</label>
            <select name="status" class="form-select">
                <option value="">Todos</option>
                <option value="active" {% if request.GET.status == 'active' %}selected{% endif %}>Ativo</option>
                <option value="inactive" {% if request.GET.status == 'inactive' %}selected{% endif %}>Inativo</option>
            </select>
        </div>
        
        <div class="col-md-3">
            <label class="form-label">&nbsp;</label>
            <div class="d-flex gap-2">
                <button type="submit" class="btn btn-outline-primary">
                    <i class="fas fa-search me-1"></i> Filtrar
                </button>
                <a href="{% url 'app_name:list' %}" class="btn btn-outline-secondary">
                    <i class="fas fa-times me-1"></i> Limpar
                </a>
            </div>
        </div>
    </div>
</form>
{% endblock %}

{% block list_table %}
<div class="table-responsive">
    <table class="table table-hover">
        <thead>
            <tr>
                <th>Nome</th>
                <th>Status</th>
                <th>Data Criação</th>
                <th width="120">Ações</th>
            </tr>
        </thead>
        <tbody>
            {% for item in object_list %}
            <tr>
                <td>
                    <strong>{{ item.nome }}</strong>
                    {% if item.descricao %}
                    <br><small class="text-muted">{{ item.descricao|truncatechars:50 }}</small>
                    {% endif %}
                </td>
                <td>
                    <span class="badge bg-{{ item.status|yesno:'success,danger' }}">
                        {{ item.get_status_display|default:"Ativo" }}
                    </span>
                </td>
                <td>{{ item.created_at|date:"d/m/Y H:i" }}</td>
                <td>
                    <div class="btn-group" role="group">
                        <a href="{% url 'app_name:detail' item.pk %}" class="btn btn-sm btn-outline-info" title="Visualizar">
                            <i class="fas fa-eye"></i>
                        </a>
                        <a href="{% url 'app_name:edit' item.pk %}" class="btn btn-sm btn-outline-warning" title="Editar">
                            <i class="fas fa-edit"></i>
                        </a>
                        <a href="{% url 'app_name:delete' item.pk %}" class="btn btn-sm btn-outline-danger" title="Excluir">
                            <i class="fas fa-trash"></i>
                        </a>
                    </div>
                </td>
            </tr>
            {% empty %}
            <tr>
                <td colspan="4" class="text-center text-muted py-5">
                    <i class="fas fa-inbox fa-3x mb-3 d-block"></i>
                    Nenhum registro encontrado
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

### 3. Form Template (`app_name_form.html`)

```django
{% extends "pandora_form_ultra_modern.html" %}
{% load static widget_tweaks %}

{% block title %}
{% if form.instance.pk %}Editar{% else %}Novo{% endif %} - Nome do Módulo
{% endblock %}

{% block form_title %}
{% if form.instance.pk %}Editar Item{% else %}Novo Item{% endif %}
{% endblock %}

{% block form_subtitle %}Preencha as informações do item{% endblock %}
{% block form_icon %}fas fa-[icone-apropriado]{% endblock %}

{% block form_navigation %}
<div class="form-navigation" x-data="{ activeSection: 'dados-basicos' }">
    <div class="nav nav-pills nav-justified" role="tablist">
        <button class="nav-link" :class="{ 'active': activeSection === 'dados-basicos' }" 
                @click="activeSection = 'dados-basicos'" type="button">
            <i class="fas fa-info-circle me-2"></i> Dados Básicos
        </button>
        <button class="nav-link" :class="{ 'active': activeSection === 'detalhes' }" 
                @click="activeSection = 'detalhes'" type="button">
            <i class="fas fa-list me-2"></i> Detalhes
        </button>
        <button class="nav-link" :class="{ 'active': activeSection === 'configuracoes' }" 
                @click="activeSection = 'configuracoes'" type="button">
            <i class="fas fa-cog me-2"></i> Configurações
        </button>
    </div>
</div>
{% endblock %}

{% block form_content %}
<form method="post" x-data="{ activeSection: 'dados-basicos' }" novalidate>
    {% csrf_token %}
    
    <!-- Seção: Dados Básicos -->
    <div class="form-section" x-show="activeSection === 'dados-basicos'" x-transition>
        <div class="section-header">
            <h4><i class="fas fa-info-circle me-2"></i> Dados Básicos</h4>
            <p class="text-muted">Informações principais do item</p>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <div class="form-group">
                    <label for="{{ form.nome.id_for_label }}" class="form-label required">Nome</label>
                    {{ form.nome|add_class:"form-control" }}
                    {% if form.nome.errors %}
                    <div class="invalid-feedback d-block">{{ form.nome.errors.0 }}</div>
                    {% endif %}
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="form-group">
                    <label for="{{ form.status.id_for_label }}" class="form-label">Status</label>
                    {{ form.status|add_class:"form-select" }}
                    {% if form.status.errors %}
                    <div class="invalid-feedback d-block">{{ form.status.errors.0 }}</div>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
    
    <!-- Seção: Detalhes -->
    <div class="form-section" x-show="activeSection === 'detalhes'" x-transition>
        <div class="section-header">
            <h4><i class="fas fa-list me-2"></i> Detalhes</h4>
            <p class="text-muted">Informações detalhadas</p>
        </div>
        
        <!-- Formsets aqui se necessário -->
        {{ formset.management_form }}
        <div id="formset-container">
            {% for form in formset %}
                {% include 'partials/formset_item.html' with form=form forloop=forloop %}
            {% endfor %}
        </div>
        
        <button type="button" class="btn btn-outline-primary btn-add-formset">
            <i class="fas fa-plus me-2"></i> Adicionar Item
        </button>
    </div>
    
    <!-- Seção: Configurações -->
    <div class="form-section" x-show="activeSection === 'configuracoes'" x-transition>
        <div class="section-header">
            <h4><i class="fas fa-cog me-2"></i> Configurações</h4>
            <p class="text-muted">Configurações avançadas</p>
        </div>
        
        <!-- Campos de configuração aqui -->
    </div>
</form>
{% endblock %}

{% block form_actions %}
<div class="d-flex justify-content-between">
    <a href="{% url 'app_name:list' %}" class="btn btn-outline-secondary">
        <i class="fas fa-arrow-left me-2"></i> Voltar
    </a>
    
    <div class="d-flex gap-2">
        {% if form.instance.pk %}
        <a href="{% url 'app_name:delete' form.instance.pk %}" class="btn btn-outline-danger">
            <i class="fas fa-trash me-2"></i> Excluir
        </a>
        {% endif %}
        
        <button type="submit" class="btn btn-primary">
            <i class="fas fa-save me-2"></i> Salvar
        </button>
    </div>
</div>
{% endblock %}
```

### 4. Detail Template (`app_name_detail.html`)

```django
{% extends "pandora_detail_ultra_modern.html" %}
{% load static %}

{% block title %}{{ object.nome }} - Nome do Módulo{% endblock %}

{% block detail_title %}{{ object.nome }}{% endblock %}
{% block detail_subtitle %}Detalhes completos do item{% endblock %}
{% block detail_icon %}fas fa-[icone-apropriado]{% endblock %}

{% block detail_actions %}
<a href="{% url 'app_name:edit' object.pk %}" class="btn btn-primary">
    <i class="fas fa-edit me-2"></i> Editar
</a>
<a href="{% url 'app_name:list' %}" class="btn btn-outline-secondary">
    <i class="fas fa-list me-2"></i> Voltar à Lista
</a>
{% endblock %}

{% block detail_content %}
<div class="row">
    <div class="col-lg-8">
        <!-- Informações Principais -->
        <div class="detail-card">
            <div class="detail-card-header">
                <h5><i class="fas fa-info-circle me-2"></i> Informações Básicas</h5>
            </div>
            <div class="detail-card-body">
                <div class="row">
                    <div class="col-md-6">
                        <div class="detail-field">
                            <label>Nome:</label>
                            <span>{{ object.nome }}</span>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="detail-field">
                            <label>Status:</label>
                            <span class="badge bg-{{ object.status|yesno:'success,danger' }}">
                                {{ object.get_status_display|default:"Ativo" }}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Itens Relacionados -->
        {% if object.items.exists %}
        <div class="detail-card">
            <div class="detail-card-header">
                <h5><i class="fas fa-list me-2"></i> Itens Relacionados</h5>
            </div>
            <div class="detail-card-body">
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Nome</th>
                                <th>Valor</th>
                                <th>Data</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in object.items.all %}
                            <tr>
                                <td>{{ item.nome }}</td>
                                <td>{{ item.valor|floatformat:2 }}</td>
                                <td>{{ item.data|date:"d/m/Y" }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        {% endif %}
    </div>
    
    <div class="col-lg-4">
        <!-- Sidebar com Informações Extras -->
        <div class="detail-card">
            <div class="detail-card-header">
                <h5><i class="fas fa-clock me-2"></i> Auditoria</h5>
            </div>
            <div class="detail-card-body">
                <div class="detail-field">
                    <label>Criado em:</label>
                    <span>{{ object.created_at|date:"d/m/Y H:i" }}</span>
                </div>
                
                {% if object.updated_at %}
                <div class="detail-field">
                    <label>Última atualização:</label>
                    <span>{{ object.updated_at|date:"d/m/Y H:i" }}</span>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

### 5. Delete Template (`app_name_confirm_delete.html`)

```django
{% extends "pandora_confirm_delete_ultra_modern.html" %}
{% load static %}

{% block title %}Excluir {{ object.nome }} - Nome do Módulo{% endblock %}

{% block delete_title %}Confirmar Exclusão{% endblock %}
{% block delete_subtitle %}Esta ação não pode ser desfeita{% endblock %}
{% block delete_icon %}fas fa-exclamation-triangle{% endblock %}

{% block delete_object_info %}
<div class="alert alert-warning">
    <h5 class="alert-heading">
        <i class="fas fa-exclamation-triangle me-2"></i>
        Você está prestes a excluir:
    </h5>
    <p class="mb-0"><strong>{{ object.nome }}</strong></p>
    {% if object.descricao %}
    <small class="text-muted">{{ object.descricao }}</small>
    {% endif %}
</div>
{% endblock %}

{% block delete_warnings %}
{% if object.items.exists %}
<div class="alert alert-danger">
    <h6><i class="fas fa-exclamation-circle me-2"></i> Atenção:</h6>
    <p class="mb-2">Este item possui {{ object.items.count }} itens relacionados que também serão excluídos:</p>
    <ul class="mb-0">
        {% for item in object.items.all|slice:":5" %}
        <li>{{ item.nome }}</li>
        {% endfor %}
        {% if object.items.count > 5 %}
        <li><em>... e mais {{ object.items.count|add:"-5" }} itens</em></li>
        {% endif %}
    </ul>
</div>
{% endif %}
{% endblock %}

{% block delete_form %}
<form method="post">
    {% csrf_token %}
    <div class="d-flex justify-content-between">
        <a href="{% url 'app_name:detail' object.pk %}" class="btn btn-outline-secondary">
            <i class="fas fa-arrow-left me-2"></i> Cancelar
        </a>
        
        <button type="submit" class="btn btn-danger">
            <i class="fas fa-trash me-2"></i> Sim, Excluir
        </button>
    </div>
</form>
{% endblock %}
```

## 🔧 Configuração de Views

### Views.py Padrão

```python
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from .models import ModelName
from .forms import ModelForm

class ModelDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'app_name/app_name_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'total_count': ModelName.objects.count(),
            'active_count': ModelName.objects.filter(status='active').count(),
            'recent_items': ModelName.objects.order_by('-created_at')[:5],
        })
        return context

class ModelListView(LoginRequiredMixin, ListView):
    model = ModelName
    template_name = 'app_name/app_name_list.html'
    context_object_name = 'object_list'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        nome = self.request.GET.get('nome')
        if nome:
            queryset = queryset.filter(nome__icontains=nome)
            
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        return queryset.order_by('-created_at')

class ModelCreateView(LoginRequiredMixin, CreateView):
    model = ModelName
    form_class = ModelForm
    template_name = 'app_name/app_name_form.html'
    success_url = reverse_lazy('app_name:list')

class ModelUpdateView(LoginRequiredMixin, UpdateView):
    model = ModelName
    form_class = ModelForm
    template_name = 'app_name/app_name_form.html'
    success_url = reverse_lazy('app_name:list')

class ModelDetailView(LoginRequiredMixin, DetailView):
    model = ModelName
    template_name = 'app_name/app_name_detail.html'

class ModelDeleteView(LoginRequiredMixin, DeleteView):
    model = ModelName
    template_name = 'app_name/app_name_confirm_delete.html'
    success_url = reverse_lazy('app_name:list')
```

### URLs.py Padrão

```python
from django.urls import path
from . import views

app_name = 'app_name'

urlpatterns = [
    path('', views.ModelDashboardView.as_view(), name='dashboard'),
    path('lista/', views.ModelListView.as_view(), name='list'),
    path('novo/', views.ModelCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ModelDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', views.ModelUpdateView.as_view(), name='edit'),
    path('<int:pk>/excluir/', views.ModelDeleteView.as_view(), name='delete'),
]
```

## ✅ Checklist de Implementação

### Preparação
- [ ] Verificar se o modelo possui campo `status` (padrão: active/inactive)
- [ ] Verificar se o modelo possui `created_at` e `updated_at`
- [ ] Verificar se existe FormSet para itens relacionados

### Templates
- [ ] Criar `app_name_dashboard.html` com widgets apropriados
- [ ] Criar `app_name_list.html` com filtros e tabela
- [ ] Criar `app_name_form.html` com seções navegáveis
- [ ] Criar `app_name_detail.html` com informações completas
- [ ] Criar `app_name_confirm_delete.html` com avisos

### Views
- [ ] Implementar DashboardView com estatísticas
- [ ] Implementar ListView com filtros
- [ ] Implementar CreateView e UpdateView
- [ ] Implementar DetailView
- [ ] Implementar DeleteView com proteções

### URLs
- [ ] Configurar rotas seguindo padrão RESTful
- [ ] Definir namespace para o app
- [ ] Testar todas as rotas

### Testes
- [ ] Testar navegação entre páginas
- [ ] Testar filtros na listagem
- [ ] Testar criação e edição
- [ ] Testar exclusão com avisos
- [ ] Testar responsividade

## 🎨 Customizações por Módulo

### Ícones por Tipo de Módulo
- **Fornecedores**: `fas fa-truck`
- **Clientes**: `fas fa-users`
- **Produtos**: `fas fa-box`
- **Financeiro**: `fas fa-dollar-sign`
- **Estoque**: `fas fa-warehouse`
- **Funcionários**: `fas fa-user-tie`
- **Obras**: `fas fa-hard-hat`

### Cores por Status
- **Ativo**: `success` (verde)
- **Inativo**: `danger` (vermelho)
- **Pendente**: `warning` (amarelo)
- **Em Análise**: `info` (azul)

## 📚 Referências e Recursos

### Componentes Disponíveis
- **Widgets**: `templates/widgets/`
- **Partials**: `templates/partials/`
- **JavaScript**: `static/js/modules/`
- **CSS**: `static/css/ultra-modern/`

### Documentação
- [Bootstrap 5.3.2](https://getbootstrap.com/docs/5.3/)
- [Font Awesome](https://fontawesome.com/icons)
- [Alpine.js](https://alpinejs.dev/)
- [AOS Animations](https://michalsnik.github.io/aos/)

## 🚀 Próximos Passos

1. **Implementar um módulo piloto** usando este guia
2. **Testar todas as funcionalidades** 
3. **Refinar o padrão** baseado no feedback
4. **Aplicar em todos os módulos** seguindo a ordem de prioridade
5. **Documentar personalizações** específicas de cada módulo

---

**Versão**: 1.0  
**Data**: 16/07/2025  
**Autor**: Pandora ERP Team  
**Status**: ✅ Aprovado para implementação
