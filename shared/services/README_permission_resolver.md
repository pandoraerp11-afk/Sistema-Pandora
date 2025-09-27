# Permission Resolver (Modern & Legacy APIs)

Este documento descreve a arquitetura e contratos do `permission_resolver.py`.

## Objetivos
- Unificar lógica de permissões (moderna e legada) sem quebrar testes existentes.
- Fornecer rastreabilidade (trace) opcional.
- Garantir cache consistente e invalidável (era global + versão user/tenant + hash de action map).

## APIs Disponíveis

### Moderna
1. `has_permission(user, tenant, action, resource=None, _force_trace=False) -> bool`
   - Retorna apenas True/False.
   - Usa cache (chave inclui modo `has`).
2. `explain_permission(user, tenant, action, resource=None, _force_trace=False) -> PermissionResult`
   - Retorna `PermissionResult(allowed, source, reason)`.
   - Preenche `_last_trace_lines` se trace ativo.
   - Use este método para inspeção detalhada (preferível para testes e auditoria).
3. `resolve_decision(user, tenant, action, resource=None, trace=False)`
   - Compat: retorna `PermissionDecision` com string de trace concatenada.
4. `get_last_trace_lines() -> list[str]`
   - Novo método público seguro para recuperar as linhas do último trace sem acessar atributo privado.
5. `debug_personalized(user, tenant, action, resource=None) -> list[dict]`
   - Inspeciona regras personalizadas candidatas, exibindo score, se foi aplicada e motivo de exclusão.

### Enum PermissionSource
`PermissionSource` (subclasse de `str, Enum`) padroniza valores de `source`:
`personalizada`, `role`, `default`, `public`, `account_block`, `invalid_user`, `anonymous_user`, `inactive_user`, `no_tenant`, `cache`, `implicit`, `exception`.
Os testes que comparam com literais continuam funcionando pois o Enum herda de `str`.

### Legada (mantida para compatibilidade)
1. `resolve(user_id, tenant_id, action, resource=None)`
   - Usa chave de cache legada (sem o segmento de modo) e retorna bool.
2. `invalidate_cache(user_id=None, tenant_id=None)`
   - Bump da era global ou da versão específica user/tenant.
3. `list_pipeline_steps()` / `add_pipeline_step(name)` / `remove_pipeline_step(name)`
   - Manipulam a lista de passos `_step_role`, `_step_implicit`, `_step_default`.

## Chaves de Cache
Formato moderno:
```
perm_resolver:{mode}:{era}:{action_map_hash}:{version}:{user_id}:{tenant_id}:{action}:{resource}
```
Formato legado:
```
perm_resolver:{era}:{action_map_hash}:{version}:{user_id}:{tenant_id}:{action}:{resource}
```
Diferenças: legado não inclui `{mode}`.

## Invalidação
- Global: incrementa `perm_resolver:global_era`.
- Específica: versão por `(user_id, tenant_id)` em `perm_resolver:ver:{user_id}:{tenant_id}`.

## Precedência de Decisão
Ordem conceitual (da maior prioridade para a menor):

1. Personalized DENY (permissões personalizadas `concedida=False` têm score mais alto para garantir bloqueio prioritário).
2. Personalized ALLOW (quando nenhuma deny aplicável prevalece).
3. Roles (tokens do action map e flag implícita admin: `is_admin`).
4. Implícitas (papéis inferidos como fornecedor/cliente) – `_step_implicit`.
5. Default (deny explícito se nada anterior conceder).

Detalhes de scoring personalizados:
- Regras são pontuadas; deny inicia com base maior para preceder allow.
- Escopo de tenant e recurso específico aumentam o score (maior especificidade = maior prioridade).
- Regras inválidas para o tenant ou recurso são descartadas.

Observação: No caminho legado/compat o step de role pode produzir uma negativa com `source="role"` sem gerar marcador `default_result`; assim, um deny final pode ter `source='role'` ou `source='default'` dependendo de onde foi decidido.

## Trace (quando habilitado)
Lista de marcadores como:
- `role_allow:ACTION`
- `personalizada: regra=<id>`
- `default_result: allow|deny`
- `cache_hit: key=...`

Notas atualizadas:
- O marcador `default_result` aparece apenas quando a decisão final vem da etapa default e `source='default'`.
- Negativas originadas diretamente no step de role (`source='role'`) não inserem `default_result`.
- Testes devem preferir inspecionar `decision.source` ao invés de depender estritamente de marcadores de trace que podem variar após cache.

## Extensão de Action Map
- Via settings `PERMISSION_ACTION_MAP_EXTRA` (dict simples)
- Via provider dinâmico `PERMISSION_ACTION_MAP_PROVIDER = 'modulo.funcao'`

## Métricas (Prometheus)
Nomes (prefixo futuro recomendado: `pandora_permission_`):
- `permission_resolver_decisions_total`
- `permission_resolver_cache_hits_total`
- `permission_resolver_cache_misses_total`
- `permission_resolver_latency_seconds`
- `permission_resolver_cache_ttl_seconds`

Se `django_prometheus` não instalado, métricas usam dummies.

## Role Default
- Convenção padronizada: `ROLE_DEFAULT_NAME = "USER"` definida em `core.models` e utilizada em `TenantUser.save`.
- Para compat, se existir antigo "Usuário Padrão" renomeia para `USER`.

## Próximos Melhoramentos (Backlog)
- Padronizar nomes de métricas: prefixar `pandora_permission_`.
- Extrair passos do pipeline em funções públicas testáveis.
- Converter reason/source em Enum para reduzir erros tipográficos.
   (PARCIAL) Fonte convertida para Enum `PermissionSource` mantendo compatibilidade.
- Adicionar TTL adaptativo baseado em frequência de hits.
- Documentar formato de scoring de permissões personalizadas em seção separada e expor API para debugging do score (futuro).

## Testes de Proteção Recomendados
1. Snapshot de trace para action de role permitida (ex: VIEW_PRODUTO com papel que tem token).
2. Personalized deny precedendo personalized allow e role (precedência A-D coberta).
3. Personalized allow isolada sem role.
4. Default/role negative garantindo ausência de `default_result` quando origem não é default.
5. Cache hit reproduzindo resultado consistente após primeira resolução.

---
Documento gerado automaticamente para apoiar refatorações futuras.
