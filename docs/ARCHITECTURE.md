# Arquitetura Pandora ERP

## Camadas

| Camada | Conteúdo | Notas |
|--------|----------|-------|
| UI / Templates | Bases ultra_modern + partials reutilizáveis | Estatísticas via contexto `statistics` |
| Views (CBVs) | ListView, DetailView, Create/Update, TemplateView | Mixins de tenant e permissões |
| Services | `agendamentos.services` (AgendamentoService, SlotService) | Contém regras de negócio reutilizáveis |
| Models | Entidades por app (isolamento de domínio) | Campos `tenant` para isolação lógica |
| Tasks (Celery) | Processamento de mídia, limpeza, KPIs | Fila dedicada para vídeo |
| Observabilidade | Prometheus metrics + logs estruturados | Endpoint `/metrics` |

## Multi-tenant
- Abordagem single-database, chave estrangeira `tenant`.
- Resolução do tenant: `core.utils.get_current_tenant(request)` com cache de atributo.
- Mixins:
  - `TenantMixin` (agendamentos) liga objetos ao tenant do usuário.
  - `TenantSafeMixin` (prontuarios) evita exceções quando tenant não definido.

## Padrões de Código
- Views de lista: nunca contam sobre queryset paginado; sempre usam `full_qs = self.get_queryset()`.
- Estatísticas: lista de dicts `[{label, value, icon, color}]` para renderização genérica.
- Auditoria: modelos específicos registram transições e ações (ex: `AuditoriaAgendamento`).

## Assíncrono
- Celery + Redis.
- Fila `default`, fila `media`, opcional `video`.
- Tasks idempotentes onde possível.

## WebSockets
- Grupos: `estoque_stream`, `picking_stream`.
- Eventos broadcast para atualizações em tempo real (movimentos de estoque, picking status).

## Segurança
- Separação de tenant em queries obrigatória.
- Permissões granulares via Django auth + grupos (ex: grupo secretaria).
- Proteções CSRF padrão Django.

## Extensão / Novos Módulos
1. Criar app.
2. Adicionar modelos com campo `tenant` se multi-tenant.
3. Registrar URLs e templates base herdando da família ultra_modern.
4. Se expõe métricas, adicionar counters/gauges nomeados com prefixo `pandora_`.

## Migrações & Evolução
- Evitar mudanças destrutivas sem migração de dados auxiliar (commands em `management/commands`).
- Scripts utilitários: conferência de auditoria, reprocessamento de valuation.

## Erros Comuns Evitados
- Template filters inexistentes substituídos por lógica no Python (ex: substituição de `.split(',')` e filtros aritméticos inválidos por contexto + `widthratio`).
- Indentação incorreta de `get_context_data` corrigida (evita `self` undefined).

## Futuro (Roadmap Alto Nível)
- Cache de estatísticas pesadas.
- Paginação assíncrona (HTMX ou Alpine.js) para listas grandes.
- Monitoramento estruturado de eventos de domínio.
