# 📋 DOCUMENTAÇÃO TÉCNICA - SISTEMA PANDORA ERP

## 🎯 VISÃO GERAL DO SISTEMA

O **Pandora ERP** é um sistema empresarial multi-tenant desenvolvido em Django, projetado para gerenciar diferentes tipos de empresas (construtoras, clínicas, empresas de vendas, etc.) em uma única aplicação. O sistema possui uma arquitetura modular robusta com sistema de permissões granular e interface ultra-moderna.

---
## Precedência de Permissões (permission_resolver)

> Modernização 2025-08: Unificação completa do resolver de permissões. O código legado foi encapsulado em um wrapper temporário (`user_management.services.permission_resolver`) que apenas delega para `shared.services.permission_resolver.has_permission`. Todas as novas chamadas (incluindo mixins em views) devem usar diretamente a API unificada: `has_permission(user, tenant, ACTION, resource=None)`. Convenção padronizada de ACTION: `ACAO_MODULO` (UPPER), por exemplo: `VIEW_USER_MANAGEMENT`, `CREATE_PERMISSION`, `VIEW_LOGS`.

Roadmap de desativação do wrapper legado:
1. (Concluído) Migrar testes para `shared.services.permission_resolver`.
2. (Concluído) Migrar `PermissionRequiredMixin` para ACTION unificada.
3. (Pendente) Substituir quaisquer chamadas remanescentes a `user_has_permission` em código de templates, signals ou tasks se surgirem.
4. (Planejado) Remover wrapper após duas releases sem referências residuais.

Benefícios da unificação:
- Fonte única de verdade (elimina divergências de lógica).
- Correção aplicada uma vez é propagada a todos os módulos.
- Facilita instrumentação de métricas e tracing (ponto único de entrada).
- Simplifica documentação e on-boarding de novos desenvolvedores.

Compatibilidade: Enquanto o wrapper existir, chamadas antigas `(user, modulo, acao, recurso, scope_tenant_id)` retornam False se `scope_tenant_id` não for fornecido; isso incentiva migração para a forma explícita passando `tenant` resolvido.

Ordem de avaliação e decisão final (primeira regra conclusiva vence):

1. Bloqueios de conta / vínculo (`_check_account_blocks`)
2. Permissões personalizadas (DENY/ALLOW) com escopo e recurso
   - Ordenação por score:
     - DENY: +100
     - Escopo tenant alvo: +50
     - Recurso específico (match exato): +20 (permissões de recurso diferente são descartadas)
     - Global (scope_tenant=None): +5
     - Genérica (sem recurso): +1
   - Primeiro item após sort define ALLOW/DENY.
   - Efeito: DENY mais específico > ALLOW mais amplo.
3. Role do tenant (map de ações → permissões/flags do papel)
4. Papéis implícitos (ex: fornecedor/cliente) – regras especiais
5. Defaults de módulo (fallback final)

Regra chave: qualquer DENY personalizado vence sobre ALLOW de role ou default.

### Exemplos
| Cenário | Personalizada | Role | Resultado |
|---------|---------------|------|-----------|
| DENY scoped tenant + recurso | negar | permitir | NEGADO (precedência 2) |
| ALLOW global genérica, Role nega | permitir | sem perm | PERMITIDO |
| Sem personalizadas, Role permite | — | permite | PERMITIDO |
| Sem personalizadas, Role ausente, default nega | — | — | Depende do default |

### Cache
Chave: `perm_resolver:<vers>:<user_id>:<tenant_id>:<ACTION>[:resource]`.
Versão (`_get_version`) permite invalidar sem apagar todas as chaves (incrementar versão → chaves antigas expiram). TTL padrão 300s.

### Invalidação Recomendada
- Sinais post_save/post_delete em permissões personalizadas incrementam versão.
- Alteração de roles (futuro): idem.

## Notas de Performance (Baseline Opcional)
Testes (marcados com skip padrão) disponíveis:
`shared/tests/test_permission_resolver_performance.py`

Executar (exemplo):
```
PANDORA_PERF=1 pytest -q shared/tests/test_permission_resolver_performance.py
```
Métricas alvo (ambiente de dev):
- Resolução warm cache < 3ms média.
- Renderização de menu < 8ms média.

Uso: detectar regressões significativas após refactors de autorização ou menu.

### Diagrama de Fluxo (Simplificado)

```mermaid
flowchart TD
  A[resolve(user, tenant, action, resource)] --> B{User ativo?}
  B -- Não --> Z1[Return False 'Usuário inativo']
  B -- Sim --> C{Cache hit?}
  C -- Sim --> Z2[Return cached]
  C -- Não --> D[Check bloqueios conta]
  D --> |Negado| Z3[Return False 'bloqueio']
  D --> |Ok| E[Permissões personalizadas]
  E --> |Match DENY/ALLOW| Z4[Return resultado personalizada]
  E --> |None| F[Role do tenant]
  F --> |Permite| Z5[Return allow role]
  F --> |Não| G[Papéis implícitos]
  G --> |Permite| Z6[Return allow implícito]
  G --> |Não| H[Defaults módulo]
  H --> |Permite| Z7[Return allow default]
  H --> |Não| Z8[Return False 'Ação não permitida']
```
---

## Razões Padronizadas de Negação de Módulo (AccessDecision.reason)

Tabela de razões retornadas por `can_access_module` e refletidas em logs (`[MODULE_DENY]`) e, quando `FEATURE_MODULE_DENY_403=True`, em cabeçalhos HTTP (`X-Deny-Reason`, `X-Deny-Module`):

| Reason | Significado | Ação recomendada |
|--------|-------------|------------------|
| OK | Acesso permitido | Nenhuma |
| NO_TENANT | Usuário não tem tenant resolvido | Forçar seleção de empresa / verificar sessão |
| SUPERUSER_BYPASS | Acesso liberado por superusuário | Apenas auditoria (não é deny) |
| MODULE_NAME_EMPTY | Chamada sem nome de módulo | Corrigir chamada do caller |
| MODULE_DISABLED_FOR_TENANT | Módulo não habilitado em `enabled_modules` | Habilitar módulo ou ocultar no menu |
| PORTAL_NOT_IN_WHITELIST | Usuário portal tentou módulo fora da whitelist | Ajustar `PORTAL_ALLOWED_MODULES` ou perfil do usuário |
| PERMISSION_RESOLVER_DENY | permission_resolver negou ação `VIEW_<MODULE>` e modo estrito ativo | Conceder permissão personalizada ou role adequada |
| UNKNOWN_ERROR | Exceção interna durante avaliação estrita | Investigar logs / stacktrace |

### Cabeçalhos HTTP em 403
Quando `FEATURE_MODULE_DENY_403=True` e acesso negado:
- `X-Deny-Reason`: valor da reason acima.
- `X-Deny-Module`: nome do módulo (ex: `clientes`).

### Logging Estruturado
Entrada em `AuditLog.change_message`:
```
[MODULE_DENY] module=<mod> reason=<REASON> tenant=<id>
```
Deduplicação opcional configurável via `LOG_MODULE_DENY_DEDUP_SECONDS` evita spam de registros repetidos (cache em memória).

### Endpoint de Diagnóstico de Módulos
`GET /core/api/modules/diagnostics/`

Retorna JSON:
```
{
  "tenant_id": 12,
  "count": 5,
  "modules": [
    {"module": "clientes", "enabled_for_tenant": true, "allowed": true, "reason": "OK"},
    {"module": "financeiro", "enabled_for_tenant": false, "allowed": false, "reason": "MODULE_DISABLED_FOR_TENANT"},
    ...
  ]
}
```
Regras:
- Requer autenticação.
- Superusuário: vê todos os módulos configurados em `PANDORA_MODULES`.
- Usuário comum: lista filtrada pela política (unified access); inclui módulos avaliados inclusive negados se unified ativo.
- Campo `reason` segue tabela de razões.

Uso recomendado: UI administrativa para troubleshooting de acesso e suporte.

### Endpoint de Inspeção de Cache de Permissões
`GET /core/api/permissions/cache/`

Superusuário apenas. Retorna:
```
{
  "tenant_id": 12,
  "user_id": 5,
  "version": 3,
  "potential_keys": ["perm_resolver:3:5:12:VIEW_CLIENTES", ...]
}
```
`version` é o número interno usado para invalidar chaves (incrementado por operações de invalidation); `potential_keys` lista chaves que poderão existir após chamadas de resolução (não força avaliação, apenas gera preview).

Uso: debugging de cache, validação de invalidation após criação/remoção de permissões personalizadas.

---

## 🏗️ ARQUITETURA PRINCIPAL

### **Framework e Tecnologias Base**
- **Backend**: Django 5.1+ (Python)
- **Frontend**: Bootstrap 5.3.2 + Alpine.js + FontAwesome
- **Base de Dados**: SQLite (desenvolvimento) / PostgreSQL (produção)
- **WebSockets**: Django Channels + Daphne
- **APIs**: Django REST Framework + CORS
- **Autenticação**: Django Auth + Django Guardian (permissões por objeto)

### **Design Patterns Aplicados**
- **Multi-Tenancy**: Isolamento de dados por empresa
- **Modular Architecture**: 32 módulos especializados
- **Template Inheritance**: Sistema hierárquico de templates
- **Middleware Chain**: Processamento de requisições em camadas
- **Permission System**: Controle granular de acesso

---

## 🔑 HIERARQUIA DE USUÁRIOS E ACESSO

### **1. SUPER ADMIN (Dono do Sistema)**
```python
# Características:
- is_superuser = True
- Acesso TOTAL ao sistema
- Não precisa selecionar empresa
- Gerencia todas as empresas clientes
- Acesso direto ao Django Admin
```

**Responsabilidades:**
- ✅ Criar e gerenciar empresas clientes
- ✅ Configurar módulos habilitados por empresa
- ✅ Monitorar performance e métricas globais
- ✅ Realizar backups e manutenções
- ✅ Gerenciar alertas críticos do sistema
- ✅ Configurações globais de segurança

**URLs de Acesso:**
- Dashboard Principal: `/admin-panel/`
- Gestão de Empresas: `/core/tenant/`
- Usuários Globais: `/user-management/`
- Django Admin: `/admin/`

---

### **2. ADMIN DA EMPRESA (Administrador Local)**
```python
# Características:
- perfil_estendido.tipo_usuario = 'admin_empresa'
- Acesso completo apenas à SUA empresa
- Precisa selecionar empresa para acessar
- Gerencia usuários de sua empresa
```

**Responsabilidades:**
- ✅ Gerenciar usuários da própria empresa
- ✅ Configurar departamentos e cargos
- ✅ Definir permissões locais
- ✅ Convidar novos usuários
- ✅ Configurar perfis de acesso
- ✅ Monitorar atividades da empresa

**URLs de Acesso:**
- Dashboard da Empresa: `/admin-panel/management/`
- Usuários da Empresa: `/user-management/usuario/`
- Configurações: `/core/tenant-config/`

---

### **3. USUÁRIOS COMUNS (Funcionários, Clientes, etc.)**
```python
# Características:
- perfil_estendido.tipo_usuario in ['funcionario', 'cliente', 'fornecedor']
- Acesso limitado aos módulos autorizados
- Obrigatório selecionar empresa
- Permissões definidas pelo Admin da Empresa
```

**Tipos de Usuários:**
- **Funcionário**: Acesso a módulos operacionais
- **Cliente**: Acesso a portais específicos
- **Fornecedor**: Acesso a módulos de compras/fornecimento
- **Prestador**: Acesso a módulos de serviços

---

## 🏢 MÓDULOS PRINCIPAIS E SUAS DIFERENÇAS

### **CORE (Super Admin)**
```python
# Responsabilidade: Gestão do SISTEMA como um todo
# Acesso: Apenas SUPER ADMIN
# Função: Dono do sistema gerencia empresas clientes
```

**Funcionalidades Principais:**
- 🏢 **Gestão de Empresas (Tenants)**
  - Criar novas empresas clientes
  - Configurar módulos habilitados
  - Definir limites e cotas
  - Monitorar uso de recursos

- 👑 **Controle Total de Usuários**
  - Visualizar TODOS os usuários do sistema
  - Criar usuários para qualquer empresa
  - Gerenciar tipos e permissões globais
  - Auditoria completa de acessos

- ⚙️ **Configurações Globais**
  - Parâmetros do sistema
  - Configurações de segurança
  - Backup e restore
  - Monitoramento de performance

**URLs Exclusivas:**
- `/core/dashboard/` - Dashboard global do sistema
- `/core/tenant/` - Gestão de empresas
- `/core/tenant-user/` - Usuários por empresa
- `/core/role/` - Cargos globais

---

### **admin (Admin da Empresa)**
```python
# Responsabilidade: Gestão da EMPRESA específica
# Acesso: Admin da empresa + Super Admin
# Função: Empresa gerencia seus próprios usuários e configurações
```

**Funcionalidades Principais:**
- 👥 **Gestão Local de Usuários**
  - Usuários apenas da empresa atual
  - Convidar novos colaboradores
  - Definir cargos e departamentos locais
  - Configurar permissões específicas

- 📊 **Dashboard Empresarial**
  - Métricas da empresa
  - Performance dos usuários
  - Relatórios de atividade
  - Alertas específicos

- 🔧 **Configurações da Empresa**
  - Dados cadastrais
  - Customização visual
  - Módulos habilitados
  - Políticas de segurança

**URLs Específicas:**
- `/admin-panel/` - Dashboard da empresa
- `/admin-panel/management/` - Gestão completa
- `/admin-panel/users/` - Usuários da empresa
- `/admin-panel/settings/` - Configurações locais

---

### **USER_MANAGEMENT (Gestão Unificada)**
```python
# Responsabilidade: Módulo que gerencia TODOS os usuários
# Acesso: Varia conforme perfil do usuário
# Função: Sistema unificado de gestão de usuários
```

**Funcionalidades por Perfil:**

**Para SUPER ADMIN:**
- 🌐 **Visão Global**
  - TODOS os usuários de TODAS as empresas
  - Criar usuários para qualquer empresa
  - Migrar usuários entre empresas
  - Relatórios globais de uso

**Para ADMIN DA EMPRESA:**
- 🏢 **Visão Local**
  - Apenas usuários da própria empresa
  - Convidar usuários para a empresa
  - Gerenciar permissões locais
  - Relatórios da empresa

**Para USUÁRIOS COMUNS:**
- 👤 **Perfil Pessoal**
  - Editar próprio perfil
  - Alterar senha
  - Configurações pessoais
  - Histórico de atividades

**URLs Contextuais:**
- `/user-management/dashboard/` - Dashboard (filtrado por perfil)
- `/user-management/usuario/` - Lista (filtrada por acesso)
- `/user-management/perfil/` - Perfil pessoal
- `/user-management/convite/` - Sistema de convites

---

## 🔐 SISTEMA DE PERMISSÕES

### **Middlewares de Segurança**

#### **1. TenantMiddleware**
```python
# Função: Controla seleção de empresa
# Super Admin: Pode ou não selecionar empresa
# Outros usuários: OBRIGATÓRIO selecionar empresa
```

#### **2. ModuleAccessMiddleware**
```python
# Função: Verifica acesso aos módulos
# Baseado em: enabled_modules do Tenant
# Super Admin: Acesso total a tudo
```

### ✅ Modernização 2025-08: Enforcement Real em Testes
Foram removidos bypasses amplos condicionados à flag `TESTING` que permitiam acesso a módulos não habilitados durante a suíte de testes. Agora:
- O método `can_access_module` nunca concede allow apenas por estar em ambiente de teste.
- O `ModuleAccessMiddleware` sempre avalia o módulo (exceto paths isentos), apenas adicionando headers de debug extras em teste.
- A preparação de estado em testes é feita por fixture que popula `enabled_modules` quando vazio (isolado em `conftest.py`).
- Testes que desejam validar negação devem ajustar explicitamente `tenant.enabled_modules` e podem ativar `FEATURE_MODULE_DENY_403=True` para assert detalhado.

Teste negativo adicionado: `test_modulo_desabilitado_retorna_denial` garantindo que um módulo ausente gera 403 ou redirect controlado sem bypass.

Benefícios:
- Paridade maior com produção (reduz falsos positivos).
- Elimina dependência de comportamento mágico de `TESTING`.
- Facilita detectar configurações incorretas de módulos cedo.

Próximos passos planejados:
- Converter warnings de URLField (Django 6.0) via `FORMS_URLFIELD_ASSUME_HTTPS`.
- Adicionar testes dedicados para `FEATURE_ENFORCE_PERMISSION_RESOLVER_STRICT`.
- Instrumentar métricas de cache hit do `_module_access_cache`.


#### **3. UserActivityMiddleware**
```python
# Função: Registra atividades dos usuários
# Logs: Ações, timestamps, IPs
```

#### **4. AuditLogMiddleware**
```python
# Função: Auditoria completa do sistema
# Rastreia: Mudanças de dados, acessos
```

### **Níveis de Permissão**

#### **Nível 1: Super Admin**
```python
def is_superuser_required(user):
    return user.is_superuser

@user_passes_test(is_superuser_required)
def super_admin_view(request):
    # Acesso total ao sistema
```

#### **Nível 2: Admin da Empresa**
```python
def is_tenant_admin(user):
    return (user.is_superuser or 
            user.perfil_estendido.tipo_usuario == 'admin_empresa')

@user_passes_test(is_tenant_admin)
def tenant_admin_view(request):
    # Acesso à gestão da empresa
```

#### **Nível 3: Usuário com Tenant**
```python
@login_required
@tenant_required
def user_view(request):
    # Acesso básico com empresa selecionada
```

---

## 📚 ESTRUTURA DE TEMPLATES

### **Hierarquia de Templates**
```
pandora_ultra_modern_base.html (BASE GERAL)
    ├── pandora_dashboard_ultra_modern.html (DASHBOARDS)
    ├── pandora_list_ultra_modern.html (LISTAGENS)
    ├── pandora_form_ultra_modern.html (FORMULÁRIOS)
    ├── pandora_detail_ultra_modern.html (DETALHES)
    └── pandora_confirm_delete_ultra_modern.html (EXCLUSÕES)
```

### **Sistema de Menu Moderno**
```python
# Template Tag: {% load menu_tags %}
# Uso: {% render_pandora_menu %}
# Funcionalidades:
- Bootstrap 5 Collapse nativo
- Permissões automáticas
- Estados ativos
- Accordion behavior
- Animações suaves
```

### **Design System**
```css
/* Variáveis CSS Ultra-Modernas */
:root {
    --primary-500-rgb: 59, 130, 246;
    --transition-fast: 150ms;
    --radius-md: 0.375rem;
    --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}
```

---

## 🛠️ MÓDULOS DO SISTEMA (31 Módulos Ativos + 1 Planejado)

### **FERRAMENTAS DO SUPER ADMIN**
1. **admin** - Dashboard do sistema
2. **core** - Gestão de empresas e configurações
3. **user_management** - Gestão global de usuários

### **RECURSOS HUMANOS**
4. **funcionarios** - Gestão completa de funcionários

### **CADASTROS BASE**
5. **clientes** - Gestão de clientes
6. **fornecedores** - Gestão de fornecedores
7. **produtos** - Catálogo de produtos
8. **servicos** - Gestão de serviços
9. **cadastros_gerais** - Cadastros auxiliares

### **OPERAÇÕES**
10. **obras** - Gestão de obras/projetos
11. **quantificacao_obras** - Quantificação e medições
12. **orcamentos** - Sistema de orçamentos
13. **mao_obra** - Controle de mão de obra
14. **compras** - Gestão de compras
15. **apropriacao** - Apropriação de custos

### **GESTÃO E ANÁLISE**
16. **financeiro** - Gestão financeira
17. **estoque** - Controle de estoque
18. **aprovacoes** - Workflow de aprovações
19. **relatorios** - Sistema de relatórios
20. **bi** - Business Intelligence

### **FERRAMENTAS DIVERSAS**
21. **agenda** - Agendamento e calendário
22. **eventos** - Gestão de eventos
23. **chat** - Sistema de mensagens
24. **notifications** - Centro de notificações
25. **formularios** - Formulários estáticos
26. **formularios_dinamicos** - Formulários dinâmicos
27. **sst** - Segurança do Trabalho
28. **treinamento** - Gestão de treinamentos
29. **ai_auditor** - Auditoria com IA

### **MÓDULOS DE SAÚDE**
30. **prontuarios** - Prontuários médicos

### **MÓDULOS DE DESENVOLVIMENTO**
31. **assistente_web** - Assistente virtual
*(assistente_ia planejado / não ativo no código atual)*

---

## ⚙️ CONFIGURAÇÃO PANDORA_MODULES

```python
# settings.py
PANDORA_MODULES = [
    # Controle por permissão
    {"name": "PAINEL SUPER ADMIN", "is_header": True, "superuser_only": True},
    {"module_name": "admin", "superuser_only": True},
    
    # Controle por empresa
    {"name": "ADMINISTRAÇÃO DA EMPRESA", "is_header": True, "tenant_admin_only": True},
    {"module_name": "user_management", "tenant_admin_only": True},
    
    # Módulos gerais (para usuários com tenant)
    {"name": "OPERAÇÕES", "is_header": True},
    {"module_name": "obras", "children": [...]},
]
```

### **Tipos de Controle de Acesso:**
- `superuser_only: True` - Apenas Super Admin
- `tenant_admin_only: True` - Admin da Empresa + Super Admin
- Sem flags - Usuários com tenant selecionado

---

## 🔄 FLUXO DE AUTENTICAÇÃO

### **1. Login do Usuário**
```python
# /login/
1. Usuário informa credenciais
2. Django Auth valida usuário
3. Sistema verifica perfil_estendido
4. Redirecionamento baseado no tipo
```

### **2. Seleção de Empresa (Tenant)**
```python
# /tenant-select/
1. Super Admin: Opcional (pode pular)
2. Outros usuários: Obrigatório
3. Validação de vínculo empresa-usuário
4. Armazenamento na sessão
```

### **3. Acesso aos Módulos**
```python
# Middleware Chain
1. TenantMiddleware: Valida empresa
2. ModuleAccessMiddleware: Verifica módulo
3. View: Processa requisição
4. Template: Renderiza com permissões
```

## Estrutura de Dados de Módulos (enabled_modules)

### Formato Canônico Atual
O campo `Tenant.enabled_modules` DEVE estar SEMPRE no formato:

```
{"modules": ["clientes", "financeiro", "estoque", ...]}
```

Regras:
- Lista contém apenas `module_name` definidos em `PANDORA_MODULES` (settings).
- Sem duplicados; ordem não é semântica (tratada como conjunto).
- Apenas letras minúsculas; validação/normalização converte entradas desviantes.
- Nenhum outro shape (lista pura, dict de flags, string CSV/JSON) é aceito em código novo.

### Racional da Padronização
- Reduz caminhos condicionais de parsing → menos bugs.
- Facilita cache, auditoria e diffs (estrutura estável).
- Permite futura extensão (ex: adicionar chave `metadata` ao lado de `modules`).

### Normalização Automática
- A flag `FEATURE_STRICT_ENABLED_MODULES` (settings) quando `True` ativa normalização no `save()` do `Tenant`.
- Função interna `_normalize_enabled_modules(raw)` converte qualquer formato legado suportado para o canônico.
- Em caso de falha de parsing, fallback seguro: `{ "modules": [] }` (não levanta exceção para preservar fluxo transacional).

### Auditoria e Correção em Massa
Comando de auditoria criado:

```
python manage.py audit_enabled_modules          # Relatório texto
python manage.py audit_enabled_modules --json   # Saída JSON estruturada
python manage.py audit_enabled_modules --apply  # Aplica normalização
python manage.py audit_enabled_modules --fail-on-dirty  # CI: retorna código !=0 se houver divergências
```

Campos do relatório (JSON):
- `raw`: valor encontrado atualmente no banco.
- `normalized`: valor canônico calculado.
- `canonical`: boolean indicando se já está correto.
- `reason`: `already_canonical` | `normalized` | `error:<Tipo>`.

### Fluxo de Migração Recomendada
1. Executar auditoria em produção: `audit_enabled_modules --fail-on-dirty`.
2. Se houver divergências, rodar `--apply` em janela controlada.
3. Re-executar sem divergências → habilitar `FEATURE_STRICT_ENABLED_MODULES=True`.
4. Monitorar logs/alertas; se estável, remover código de parsing legado (já concluído em `Tenant.is_module_enabled`).

### Interação com Autorização Modular
- `can_access_module` delega a `tenant.is_module_enabled` (agora estrito). Qualquer valor fora do canônico provoca negação segura.
- Testes devem sempre criar tenants com o formato canônico ou confiar na normalização automática.

### Boas Práticas de Uso
- Ao habilitar/desabilitar módulos via scripts/admin: operar sobre cópia e atribuir `{"modules": nova_lista}` diretamente.
- Validar existência do módulo em `settings.PANDORA_MODULES` antes de adicionar.
- Evitar mutar lista interna em runtime (ex: `tenant.enabled_modules['modules'].append(...)`) sem `save()`: prefira construir nova lista e salvar.

### Exemplo de Atualização Segura
```python
mods = set(tenant.enabled_modules.get('modules', []))
mods.add('financeiro')
tenant.enabled_modules = {"modules": sorted(mods)}
tenant.save(update_fields=['enabled_modules'])
```

### Plano de Evolução Futuro
- Opcional: migrar para tabela relacional `TenantModule` se for necessário metadata (limites, quotas) por módulo.
- Adicionar validação de conjunto permitido via `Enum` central ou Choices.
- Telemetria (OpenTelemetry/Sentry) para detectar tentativas de atribuição fora do canônico (feature flag de auditoria).

---

---

## 💾 MODELO DE DADOS PRINCIPAL

### **Tenant (Empresa)**
```python
class Tenant(TimestampedModel):
    name = models.CharField(max_length=100)  # Nome fantasia
    subdomain = models.CharField(unique=True)  # Identificador
    status = models.CharField(choices=STATUS_CHOICES)
    enabled_modules = models.JSONField(default=dict)  # Módulos habilitados
    tipo_pessoa = models.CharField(choices=TIPO_PESSOA_CHOICES)
    cnpj = models.CharField(validators=[cnpj_validator])
    # ... mais de 50 campos para informações completas
```

### **CustomUser (Usuário Estendido)**
```python
class CustomUser(AbstractUser):
    tenant = models.ForeignKey(Tenant)  # Empresa principal
    perfil_estendido = OneToOne(PerfilUsuarioEstendido)
    # Herda todos os campos do Django User
```

### **PerfilUsuarioEstendido**
```python
class PerfilUsuarioEstendido(models.Model):
    tipo_usuario = models.CharField(choices=TipoUsuario.choices)
    status = models.CharField(choices=StatusUsuario.choices)
    cpf = models.CharField(unique=True)
    # ... campos pessoais e profissionais
    autenticacao_dois_fatores = models.BooleanField()
    # ... configurações de segurança
```

---

## 🚀 FUNCIONALIDADES AVANÇADAS

### **Sistema Multi-Tenant**
- ✅ Isolamento total de dados por empresa
- ✅ Configuração de módulos por empresa
- ✅ Customização visual por empresa
- ✅ Métricas e relatórios segregados

### **Dashboard Engine Ultra-Moderno**
- ✅ Widgets drag-and-drop (GridStack.js)
- ✅ 6 temas dinâmicos
- ✅ Gráficos interativos (Chart.js)
- ✅ Atualização em tempo real
- ✅ Export PDF/Excel/Imagem

### **Sistema de Permissões Granular**
- ✅ Permissões por objeto (Django Guardian)
- ✅ Cargos e departamentos customizáveis
- ✅ Herança de permissões
- ✅ Auditoria completa de acessos

### **Interface Ultra-Moderna**
- ✅ Bootstrap 5.3.2 + Alpine.js
- ✅ Animações AOS
- ✅ Design responsivo total
- ✅ Dark mode e temas
- ✅ Menu colapsível inteligente

### **APIs REST Completas**
- ✅ Django REST Framework
- ✅ Swagger/OpenAPI documentation
- ✅ Autenticação JWT
- ✅ CORS configurado
- ✅ Rate limiting

---

## 📊 SISTEMA DE DASHBOARDS UNIFICADO

### **Arquitetura Completa dos Dashboards**

O Pandora ERP implementa um sistema de dashboards ultra-moderno com três níveis hierárquicos distintos:

#### **1. 🎯 TEMPLATE BASE UNIVERSAL**
```
Arquivo: templates/pandora_dashboard_ultra_modern.html
Base: templates/pandora_ultra_modern_base.html
Assets: static/dist/css/pandora-ultra-modern.css
        static/dist/js/pandora-ultra-modern.js
```

**Tecnologias Integradas:**
- ✅ **GridStack.js 9.2.0** - Sistema drag-and-drop avançado
- ✅ **Bootstrap 5.3.2** - Framework CSS responsivo
- ✅ **Alpine.js** - Reatividade frontend
- ✅ **Chart.js** - Gráficos interativos
- ✅ **FontAwesome** - Iconografia moderna

#### **2. 🏢 DASHBOARD CORE (Super Admin)**
```
Template: core/templates/core/core_dashboard.html
Sistema: core/dashboard_system.py (classe CoreDashboard)
URL: /core/dashboard/
Acesso: Apenas superusuários
```

**Métricas Globais:**
- 🏢 Total de empresas (tenants) no sistema
- ✅ Empresas ativas vs inativas
- 👥 Total de usuários cadastrados
- 🔐 Cargos e departamentos criados
- 💰 MRR (Monthly Recurring Revenue) estimado
- 📈 Crescimento de tenants (últimos 6 meses)

#### **3. 🎛️ DASHBOARD ADMIN (Gestão da Empresa)**
```
Template: admin/templates/admin/admin.html
URL: /admin-panel/
Acesso: Administradores da empresa (tenant)
```

**Visão Executiva:**
- 📊 KPIs consolidados de todos os módulos
- 👨‍💼 Métricas de funcionários e departamentos
- ⏰ Pendências críticas organizacionais
- 📈 Performance geral da empresa
- 🔔 Alertas e notificações importantes

#### **4. 🔧 DASHBOARDS MODULARES (32 dashboards específicos)**
```
Padrão: {modulo}/templates/{modulo}/{modulo}_dashboard.html
Todos estendem: pandora_dashboard_ultra_modern.html
```

**Lista Completa dos Dashboards Modulares:**

**Módulos Principais:**
- `clientes/clientes_dashboard.html` - CRM e relacionamento
- `financeiro/financeiro_dashboard.html` - Fluxo de caixa e DRE
- `estoque/estoque_dashboard.html` - Inventário e movimentações
- `obras/obras_dashboard.html` - Gestão de projetos
- `funcionarios/funcionarios_dashboard.html` - RH e folha
- `fornecedores/fornecedores_dashboard.html` - Supply chain

**Módulos Operacionais:**
- `produtos/produtos_dashboard.html` - Catálogo e performance
- `compras/compras_dashboard.html` - Procurement
- `orcamentos/orcamentos_dashboard.html` - Propostas comerciais
- `apropriacao/apropriacao_dashboard.html` - Custos diretos
- `aprovacoes/aprovacoes_dashboard.html` - Workflow de aprovações

**Módulos Especializados:**
- `bi/bi_dashboard.html` - Business Intelligence
- `quantificacao_obras/quantificacao_obras_dashboard.html` - Orçamentação
- `sst/sst_dashboard.html` - Segurança do Trabalho
- `ai_auditor/ai_auditor_dashboard.html` - Auditoria com IA
- `assistente_web/assistente_web_dashboard.html` - IA Assistente
- `cadastros_gerais/cadastros_gerais_dashboard.html` - Dados mestres

**Módulos de Apoio:**
- `agenda/agenda_dashboard.html` - Calendário e eventos
- `chat/chat_dashboard.html` - Comunicação interna
- `eventos/eventos_dashboard.html` - Gestão de eventos
- `formularios/formularios_dashboard.html` - Forms dinâmicos
- `formularios_dinamicos/formularios_dinamicos_dashboard.html` - Forms avançados
- `mao_obra/mao_obra_dashboard.html` - Gestão de mão de obra
- `notifications/notifications_dashboard.html` - Central de notificações
- `prontuarios/prontuarios_dashboard.html` - Registros médicos
- `relatorios/relatorios_dashboard.html` - Central de relatórios
- `servicos/servicos_dashboard.html` - Gestão de serviços
- `treinamento/treinamento_dashboard.html` - Capacitação
- `user_management/user_management_dashboard.html` - Gestão de usuários

### **Sistema de Widgets e Funcionalidades**

#### **🎨 Dashboard Engine Avançado**
- **Modo Edição**: Reorganização drag-and-drop de widgets
- **Persistência**: Layouts salvos por usuário no banco
- **Responsividade**: Adaptação automática mobile/desktop
- **Tela Cheia**: Modo fullscreen para análise detalhada
- **Temas**: 6 temas visuais dinâmicos

#### **📊 Tipos de Widgets**
- **Cards de Métricas**: KPIs numéricos com ícones
- **Gráficos Chart.js**: Barras, linhas, pizza, área
- **Tabelas Dinâmicas**: django-tables2 com filtros
- **Listas Inteligentes**: Últimos registros e pendências
- **Alertas Visuais**: Notificações e status importantes

#### **� Integração de Dados**
- **Tempo Real**: Atualização via WebSockets (notifications)
- **Cache Inteligente**: Redis para performance
- **Filtros Avançados**: Período, departamento, usuário
- **Drill-down**: Navegação contextual entre módulos

---

## 🔧 CONFIGURAÇÃO E DEPLOY

### **Requirements Principais**
```python
Django>=4.2,<5.0
django-guardian==2.4.0
djangorestframework==3.14.0
channels==4.0.0
crispy-bootstrap5
django-tables2==2.7.0
pandas==2.3.0
reportlab==4.4.2
```

### **Settings Importantes**
```python
# Multi-tenant
TENANT_MODEL = 'core.Tenant'
TENANT_DOMAIN_MODEL = 'core.TenantDomain'

# Middleware order (IMPORTANTE!)
MIDDLEWARE = [
    'core.middleware.TenantMiddleware',        # Primeiro
    'core.middleware.ModuleAccessMiddleware',  # Segundo
    'core.middleware.UserActivityMiddleware',  # Terceiro
    'core.middleware.AuditLogMiddleware',      # Quarto
]

# Template system
TEMPLATES = [
    'DIRS': [BASE_DIR / 'templates'],  # Templates globais
]
```

### **URLs Principal**
```python
urlpatterns = [
    path("admin/", admin.site.urls),                    # Django Admin
    path("", include("core.urls")),                     # Core (Super Admin)
    path("admin-panel/", include("admin.urls")),  # Admin Empresa
    path("user-management/", include("user_management.urls")), # Gestão Usuários
    # ... mais 29 módulos
]
```

---

## 🎯 RESUMO EXECUTIVO

### **Diferenças Principais Entre os Módulos**

| Módulo | Usuário | Função | Escopo |
|--------|---------|--------|--------|
| **CORE** | Super Admin | Gerenciar o SISTEMA | Todas as empresas |
| **admin** | Admin Empresa | Gerenciar a EMPRESA | Uma empresa específica |
| **USER_MANAGEMENT** | Todos | Gerenciar USUÁRIOS | Filtrado por perfil |

### **Fluxo de Responsabilidades**

1. **Super Admin** usa **CORE** para criar empresas
2. **Super Admin** usa **USER_MANAGEMENT** para criar admins das empresas
3. **Admin da Empresa** usa **admin** para configurar sua empresa
4. **Admin da Empresa** usa **USER_MANAGEMENT** para gerenciar seus usuários
5. **Usuários** usam os 32 módulos operacionais conforme permissões

### **Características Únicas do Sistema**

- ✅ **Multi-Tenancy Real**: Isolamento completo de dados
- ✅ **Permissões Granulares**: Controle por objeto e ação
- ✅ **Modularidade Extrema**: 32 módulos especializados
- ✅ **Interface Ultra-Moderna**: Bootstrap 5 + Alpine.js
- ✅ **Dashboard Engine**: Widgets configuráveis
- ✅ **API REST Completa**: Integração total
- ✅ **Auditoria Total**: Rastreamento de todas as ações

---

## 🚀 STATUS DO SISTEMA

## 🔐 Autorização Modular (Atualizado 27/08/2025)

Camada central para regras de acesso modular implementada.

Componentes:
- Função `core.authorization.can_access_module(user, tenant, module_name)` → `AccessDecision(allowed, reason)`.
- Campo `CustomUser.user_type` (INTERNAL | PORTAL) usado para distinguir whitelist de portal.
- Whitelist portal: `PORTAL_ALLOWED_MODULES`.
- Migração `0002_normalize_enabled_modules` normaliza `Tenant.enabled_modules` para `{"modules": [...]}`.
- Middleware `ModuleAccessMiddleware` consulta a função quando `FEATURE_UNIFIED_ACCESS=True`.
- Deny 403 opcional com headers `X-Deny-Reason` e `X-Deny-Module` (`FEATURE_MODULE_DENY_403=True`).
- Logging de negações em `AuditLog` via `log_module_denial` (feature `FEATURE_LOG_MODULE_DENIALS`).

Feature Flags:
```
FEATURE_UNIFIED_ACCESS
FEATURE_REMOVE_MENU_HARDCODE
FEATURE_STRICT_ENABLED_MODULES
FEATURE_MODULE_DENY_403
FEATURE_LOG_MODULE_DENIALS
```

Motivações: unificar menu/middleware, auditoria consistente, rollout seguro.

Próximos Passos: integrar permission_resolver granular, consolidar signals de perfil, testes adicionais de denies (headers) e roles.


**✅ SISTEMA ATUALIZADO – MODELO PACIENTE DESCONTINUADO**

- 🏗️ Arquitetura multi-tenant robusta
- 🔐 Sistema de permissões completo
- 🎨 Interface ultra-moderna
- 📊 31 dashboards ativos (1 módulo planejado)
- 🔄 APIs REST operacionais
- 🧪 Testes estruturados (em expansão para novas regras clínicas)
- 🗃️ Migração concluída: `Paciente` → `Cliente` + `PessoaFisica` + `PerfilClinico`

> Nota: Endpoints/URLs legados de paciente removidos; chaves de contexto em relatórios preservadas apenas para compatibilidade temporária.

**Pandora ERP pronto para evolução incremental contínua.**
