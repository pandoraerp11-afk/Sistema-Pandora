# Permission Resolver – Documento Dedicado

Este documento consolida comportamento, precedência e exemplos do resolvedor unificado localizado em `shared.services.permission_resolver`.

## Objetivo
Única fonte de verdade para resolução de permissões multi‑tenant com suporte a:
- Permissões personalizadas (allow/deny) com escopo por tenant e recurso.
- Roles do tenant (flags/campos do papel – mapa de ações).
- Papéis implícitos (fornecedor / cliente) – regras automáticas.
- Defaults de módulo (fallback mínimo).
- Cache versionado com invalidação reativa.
- Métricas opcionais (Prometheus: decisões, cache hits/misses, latência).

## (Novo) Padrão `module_key` para UI Permissions
Camada unificada usada por views/templates via `build_ui_permissions`.

### Objetivo Rápido
Expor em templates um objeto `perms_ui` com:
```
perms_ui.can_view
perms_ui.can_add
perms_ui.can_edit
perms_ui.can_delete
```
Sem o template precisar conhecer action strings internas.

### Derivação de Ações
Para `module_key='FORNECEDOR'` são consultadas ações:
- VIEW_FORNECEDOR
- CREATE_FORNECEDOR
- EDIT_FORNECEDOR
- DELETE_FORNECEDOR

### Resolução Interna
1. `build_ui_permissions` chama o permission resolver para cada ação CRUD.
2. `_get_action_map()` provê lista de flags/atalhos (ex.: `['can_add_fornecedor', 'is_admin']`).
3. Ordem de tentativa de cada elemento da lista:
   - Campo boolean futuro em `Role` (ainda não existente para fornecedor/funcionário).
   - Fallback automático: `can_add_fornecedor` → codename Django `add_fornecedor` em `role.permissions`.
   - Flag implícita `is_admin` (nome do papel: admin, superadmin, owner).

### Convenções de Nomenclatura
- module_key: UPPER_SNAKE (FORNECEDOR, FUNCIONARIO, PRODUTO, SERVICO).
- Ações CRUD: VIEW_, CREATE_, EDIT_, DELETE_ + module_key.
- Fallback codename Django: `can_<op>_<entidade>` => `<op>_<entidade>` onde `<op>` ∈ {add, view, change, delete}.

### Exemplo de Uso
View:
```python
ui_perms = build_ui_permissions(request.user, tenant=current_tenant, module_key='FORNECEDOR')
return render(request, 'fornecedores/fornecedor_list.html', {'perms_ui': ui_perms})
```
Template:
```django
{% if perms_ui.can_add %}<a href="{% url 'fornecedores:novo' %}" class="btn btn-primary">Novo Fornecedor</a>{% endif %}
```

### Boas Práticas
- Preferir `module_key` em novas telas (evitar `app_label/model_name`).
- Em templates legados mistos mantenha fallback: `perms_ui.can_add|default:perms.can_add|default:True`.
- Não colocar lógica condicional de múltiplas ações em template se puder compor no backend.

### Adicionando Novo module_key (Checklist)
1. Definir nome (ex.: PRODUTO) e garantir modelo existente.
2. Inserir no `_get_action_map()` blocos CRUD seguindo padrão.
3. Alterar view principal para usar `build_ui_permissions(... module_key='PRODUTO')`.
4. Ajustar template para `perms_ui`.
5. Criar testes similares a `shared/tests/test_ui_permissions_module_key.py`.
6. (Opcional) Evoluir para campos booleanos em `Role` se necessário (migration futura).

### Roadmap Evolutivo module_key
| Fase | Ação | Status |
|------|------|--------|
| 1 | FORNECEDOR/FUNCIONARIO integrados | Concluído |
| 2 | Fallback codenames Django | Concluído |
| 3 | Documentação consolidada (este doc) | Concluído |
| 4 | Externalizar action map em settings | Pendente |
| 4 | Externalizar action map em settings | Concluído |
| 5 | Tracing amplo (`PERMISSION_RESOLVER_TRACE`) | Concluído (trace + explain_permission) |
| 6 | Função `explain_permission` estruturada | Concluído |
| 7 | Provider dinâmico (`PERMISSION_ACTION_MAP_PROVIDER`) | Concluído |
| 8 | Expandir PRODUTO / SERVICO | Pendente |
| 9 | Avaliar flags físicas em Role | Pendente |

---

## Formato de Ação (ACTION)
Padrão canônico usado em todo o sistema:

```
<VERBO>_<MODULO>[_<SUBCONTEXTO>...]
```

- VERBO em UPPER: CREATE, VIEW, UPDATE, DELETE, LIST, EXPORT, SUBMIT, SELECT, APPROVE, REJECT.
- MODULO em UPPER sem espaços: USER_MANAGEMENT, COTACAO, PROPOSTA, DASHBOARD_FORNECEDOR.
- Subcontexto é opcional e mantém underscores (ex.: `VIEW_RELATORIO_FINANCEIRO`).

Exemplos válidos:
- VIEW_USER_MANAGEMENT
- CREATE_COTACAO
- VIEW_DASHBOARD_FORNECEDOR
- EXPORT_RELATORIO_FINANCEIRO

## Ordem de Avaliação
1. Blocos de conta / vínculo (usuário pertence ao tenant? está ativo? bloqueios portal fornecedor/cliente).
2. Permissões personalizadas (score: deny > allow; scoped > global; recurso específico > genérico; não expiradas).
3. Pipeline (configurável) – por padrão:
   - Role (`_step_role`)
   - Implícito (`_step_implicit`)
   - Default (`_step_default`)
4. Se nada conceder: nega explicitamente (pipeline exhausted).

### Precedência detalhada (primeira que decidir encerra)
1) Permissão personalizada DENY (scoped + recurso exato)
2) Permissão personalizada DENY (scoped genérica)
3) Permissão personalizada DENY (global + recurso)
4) Permissão personalizada DENY (global genérica)
5) Permissão personalizada ALLOW (scoped + recurso)
6) Permissão personalizada ALLOW (scoped genérica)
7) Permissão personalizada ALLOW (global + recurso)
8) Permissão personalizada ALLOW (global genérica)
9) Role do tenant (mapeamento action -> flags)
10) Papéis implícitos (ex.: fornecedor)
11) Defaults de módulo (fallback)
12) Caso nenhum aceite: nega

## Regras de Score (Permissões Personalizadas)
```
deny +100 | scoped +50 | recurso específico +20 | global +5 | genérica +1
Expirada ou recurso divergente => descartada.
Primeira após ordenação (maior score) define allow/deny final deste estágio.
```

## Cache
Chave: `perm_resolver:<vers>:<user_id>:<tenant_id>:<ACTION>[:resource]`.
`invalidate_cache(user_id=..., tenant_id=...)` incrementa versão seletiva; não faz varredura ampla.

- TTL default: 300s (settings `PERMISSION_CACHE_TTL`).
- Trace de cache hit com TTL: quando habilitado, o `trace` pode registrar `cache_hit~ttl=Ns`.

## Fontes (`source`)
- `account_block` – usuário não pertence / bloqueado.
- `personalizada` – permissão custom definida.
- `role` – role do tenant permitiu / negou.
- `implicit` – fornecedor / cliente.
- `default` – fallback de módulo.
- `cache` – resultado em cache.
- `exception` – erro interno levou a negação segura.

## Exemplos
| Cenário | Resultado | Fonte |
|---------|-----------|-------|
| Usuário fora do tenant | False | account_block |
| DENY scoped recurso vs ALLOW global genérico | False | personalizada |
| Sem personalizadas; role permite | True | role |
| Implícito fornecedor dashboard | True | implicit |
| Ação desconhecida | False | default |

## Recomendado em Testes
Cobrir: cache warm, precedence deny>allow, recurso específico, invalidação de versão, pipeline exhausted, implicit roles.

## Migração do Wrapper Legado
O arquivo `user_management/services/permission_resolver.py` (wrapper) foi removido após confirmar ausência de imports residuais.
Utilizar somente: `from shared.services.permission_resolver import has_permission, permission_resolver`.

## Regras de Recursos (resource)
- Se a ação requer recurso específico (ex.: ID), passe string canônica `tipo:id` (ex.: `cotacao:123`).
- Permissão com recurso específico NÃO cobre consulta genérica sem resource.
- Permissão genérica cobre recursos específicos se mesma ação (com menor prioridade).

## Decision API (resolve_decision)
API opcional que retorna uma decisão estruturada para auditoria/diagnóstico, sem quebrar `resolve(...)`:

Dataclass
```
PermissionDecision(
   allowed: bool,
   reason: str,        # motivo simplificado (sem sufixo de trace)
   trace: Optional[str],  # etapas como "account_blocks>personalizada>role_allow>..."
   source: Optional[str]  # reservado
)
```

Uso básico
```python
from shared.services.permission_resolver import permission_resolver

dec = permission_resolver.resolve_decision(user, tenant, 'VIEW_FINANCEIRO')
if dec.allowed:
      ...
```

Trace
- Habilite via `settings.PERMISSION_RESOLVER_TRACE = True` (ex.: em testes).
- Se resultado vier do cache sem trace e o trace estiver habilitado, o resolver recomputa para gerar trace.

Compatibilidade
- `permission_resolver.resolve(...)` permanece inalterado.
- `has_permission` e `@require_permission` seguem usando a interface antiga.

Boas práticas
- Use `resolve_decision` em rotas administrativas ou de diagnóstico.
- Em rotas críticas de performance, mantenha o trace desligado (default: False).

## Notas Técnicas
- Era global de invalidação: muda a chave-base e invalida tudo de forma barata.
- Hash do mapa de ações: alterações estruturais invalidam automaticamente.
- Pipeline dinâmico: é possível adicionar/remover etapas em runtime (feature flags / testes).
- Scoring otimizado: evita varredura O(n) por ação agregando previamente permissões personalizadas.
- Métricas: decisões, hits/misses de cache, latência e TTL podem ser expostas (Prometheus).

## Extensão do Action Map (Novo)
O dicionário base de ações → tokens agora reside em `get_base_action_map()` dentro do módulo e pode ser estendido sem editar o core.

Settings suportadas (ambas opcionais):
```python
PERMISSION_ACTION_MAP_EXTRA = {
   'EXPORT_RELATORIO_FINANCEIRO': ['can_export_relatorio_financeiro', 'is_admin'],
}

def custom_action_map_provider():
   # Pode carregar de BD / feature flags / plugin
   return {
      'VIEW_KANBAN_OBRAS': ['can_view_obras', 'is_admin'],
   }

PERMISSION_ACTION_MAP_PROVIDER = 'myproj.permissions.custom_action_map_provider'
```

Regras de merge:
- Chaves novas são adicionadas integralmente.
- Chaves existentes têm tokens anexados apenas se ainda não presentes (ordem original preservada).
- Ordem final: base → EXTRA → PROVIDER.
- Mudança estrutural (nova chave ou token) gera novo hash e invalida cache automaticamente.

Debug rápido:
```python
from shared.services.permission_resolver import permission_resolver
print(permission_resolver._get_action_map().get('EXPORT_RELATORIO_FINANCEIRO'))
```

## explain_permission (Novo)
Função auxiliar para obter explicação estruturada sem depender de parsing de string manual.

```python
from shared.services.permission_resolver import explain_permission

info = explain_permission(user, tenant, 'VIEW_PRODUTO')
print(info)
```

Formato de retorno:
```json
{
  "action": "VIEW_PRODUTO",
  "resource": null,
  "allowed": true,
  "reason": "Role Admin permite VIEW_PRODUTO",
  "source": "role",
  "steps": ["account_blocks:Conta ativa", "role_allow"],
  "action_tokens": ["can_view_produto", "is_admin"]
}
```

Notas:
- Sempre força geração de trace apenas para a chamada (não polui caminho hot comum).
- `steps` seguem a ordem real de avaliação.
- `action_tokens` refletem tokens pós-merge (incluindo extras/provider).

---
Atualizado: 2025-09-09.
