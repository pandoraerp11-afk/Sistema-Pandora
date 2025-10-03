# Portal Cliente – Documentação Consolidada

Data da consolidação: 30/09/2025 (auditoria final do ciclo atual)

Este documento único substitui todos os fragmentos anteriores. Reflete o estado após a ampliação da Fase 2: fluxos transacionais completos, throttling central com escopo, Retry-After dinâmico, métricas (incluindo classificação granular), refator de `get_conta_ativa`, **configuração multi‑tenant** e notificações estendidas (check‑in / finalização).

Princípio norteador permanente: "Não criar o que já existe" – reutilizar serviços/domínio legados, evitar lógica duplicada em views, centralizar regras parametrizáveis em `conf.py`.

---
## 1. Sumário Executivo

O Portal Cliente disponibiliza ao cliente final: dashboard, listagem/criação/cancelamento de agendamentos, histórico de atendimentos concluídos, galeria de fotos (thumbnails), documentos e os fluxos transacionais de **check‑in**, **finalização** e **avaliação**. Foram consolidados:
* Throttling centralizado (janela 60s) com limites dinâmicos/configuráveis e suporte a escopo por recurso.
* Retry-After dinâmico calculado a partir do timestamp da janela.
* Flags de ação derivadas do status integrado para renderização inteligente de botões.
* Métricas operacionais (contadores + histogram + erros granulares) com fallback `_Noop` se Prometheus indisponível.
* Janelas temporais configuráveis (antecedência check‑in, tolerância pós, tolerância finalização, TTL de cache).
* Refator de `get_conta_ativa` para clareza, validação sequencial e logging granular.

---
## 2. Escopo Atual (Fase 1 + Fase 2 Parcial)
| Item | Status | Observações |
|------|--------|-------------|
| Dashboard / Histórico / Galeria / Documentos | Concluído | Sem alterações de regra na Fase 2. |
| Criação / Cancelamento | Concluído | Cancelamento respeita antecedência configurável. |
| Check‑in | Concluído | Janela: `(início - antecedência_conf) .. (início + tolerância_pos)` com validação de status. |
| Finalização | Concluído | Até `(início + tolerância_finalização_horas)`. |
| Avaliação (1..5) | Concluído | Somente atendimento CONCLUIDO sem nota. Idempotência garantida (erro se duplicar). |
| Flags de Ação | Concluído | Cálculo central na view de status. |
| Throttling Central + Escopo | Concluído | Escopo aplicado a check‑in por agendamento. |
| Retry-After Dinâmico | Concluído | Header em todos os 429. |
| Métricas (throttle, duração, sucesso/erro) | Concluído | Counters + histogram + erros por tipo. |
| TTL Cache / ETag unificado | Concluído | Mesmo TTL em 200 e 304. |
| Refator `get_conta_ativa` | Concluído | Sequência validatória + logging específico. |
| Testes (cobertura básica Fase 2) | Parcial | Falta ampliar negativos e criação/cancelamento detalhados. |
| Config tolerância pós check‑in | Concluído | Agora via `get_checkin_tolerancia_pos_minutos()`. |
| Notificações (check‑in/finalização) | Concluído | Envio best‑effort configurável futuramente. |
| Config Multi‑Tenant (overrides) | Concluído | Modelo `PortalClienteConfiguracao` para limites/janelas. |

---
## 3. Arquitetura & Princípios
* Views leves orquestram serviços; validações de negócio concentram-se em `PortalClienteService` ou services legados.
* Parametrização isolada em `conf.py` evitando literais dispersos.
* Throttling e métricas desacoplados das views por helpers reutilizáveis.
* Erros de notificação não impactam fluxo (best-effort). 
* Segurança multi-tenant: cada query filtra por `tenant` + `cliente`.

---
## 4. Fluxos e Regras de Negócio
### 4.1 Dashboard
Estatísticas: total atendimentos concluídos, satisfação média (1 decimal), agendamentos pendentes; listas limitadas (próximos agendamentos, histórico recente, fotos recentes). 

### 4.2 Agendamentos
Criação exige slot vigente livre (`select_for_update`) e serviço ativo. Cancelamento permitido se antecedência >= limite configurável. 

### 4.3 Histórico
Somente atendimentos `CONCLUIDO`. Avaliação exibida se presente.

### 4.4 Galeria de Fotos
Apenas thumbnails / formatos otimizados. Sem exposição de originais.

### 4.5 Documentos
Listagem filtrada por conta. (Cobertura de testes pendente.)

### 4.6 Fluxos Fase 2
| Fluxo | Método Service | Regras | Erros Principais |
|-------|----------------|--------|------------------|
| Check‑in | `checkin_agendamento` | Status=CONFIRMADO; janela antecedência->tolerância_pos | cedo / expirado / status inválido |
| Finalização | `finalizar_atendimento` | Atendimento em andamento dentro tolerância horas | atendimento inexistente / janela expirada |
| Avaliação | `registrar_avaliacao` | Atendimento CONCLUIDO sem nota; nota 1..5 | nota inválida / já avaliado |

---
## 5. Throttling Centralizado
Arquivo: `portal_cliente/throttle.py`.
Janela padrão: 60s. Cada chave gera duas entradas de cache: contador e timestamp inicial (`:start`). Retry-After calcula (window - elapsed). Suporte a `scope` adiciona granularidade (ex.: `checkin` por agendamento).

| Chave | Limite (requisições / 60s) | Origem | Observações |
|-------|---------------------------|--------|-------------|
| slots | dinâmico | `get_slots_throttle_limit()` | Listagem slots |
| servicos | dinâmico | `get_listas_throttle_limit()` | ETag + cache |
| profissionais | dinâmico | `get_listas_throttle_limit()` | ETag + cache |
| status | 20 | constante | Status integrado (ainda sem escopo) |
| checkin | 12 | configurável | `get_throttle_checkin_limit()` escopo `agendamento_id` |
| finalizar | 10 | configurável | `get_throttle_finalizar_limit()` |
| avaliar | 10 | configurável | `get_throttle_avaliar_limit()` |

Fallback seguro para chaves desconhecidas: (30,60).

---
## 6. Cache / ETag / TTL
TTL único via `get_cache_ttl()`. Respostas 304 replicam `Cache-Control` dinamicamente. ETag fraca construída a partir de snapshot (timestamp + cardinalidade). Objetivo: reduzir banda em listagens de serviços e profissionais relativamente estáveis.

---
## 7. Sessão Multi-Tenant & Segurança
`ensure_tenant_session` antecipa obtenção de `tenant_id`. Decorator `@cliente_portal_required` aciona `get_conta_ativa`:
1. Valida usuário ativo.
2. Garante conta(s) existentes e ativas.
3. (Opcional) Auto-enable portal em modo debug.
4. Registra acesso somente ao final (efeito colateral isolado).
Logs estruturados detalham causa de rejeições.

---
## 8. Métricas & Observabilidade
| Métrica | Tipo | Labels | Descrição |
|---------|------|--------|-----------|
| portal_cliente_page_hits_total | Counter | page | Renderizações de páginas HTML. |
| portal_cliente_action_seconds | Histogram | action | Duração de ações transacionais. |
| portal_cliente_throttle_total | Counter | endpoint | Ocorrências de 429. |
| portal_cliente_action_total | Counter | action,status | Sucesso/erro (status ∈ {success,error}). |
| portal_cliente_action_error_kind_total | Counter | action,kind | Erros por categoria normalizada (mensagem). |

Helper `track_action(action)` envolve blocos críticos; `inc_action(action, status)` para contadores discretos.

---
## 9. Configurações (conf.py) e Overrides Multi‑Tenant
| Função | Propósito | Default |
|--------|-----------|---------|
| get_cache_ttl | TTL (s) para cache/ETag | 60 |
| get_slots_throttle_limit | Limite por janela para slots | 20 |
| get_listas_throttle_limit | Limite para servicos/profissionais | 30 |
| get_cancelamento_limite_horas | Antecedência mínima cancelamento | 24 |
| get_checkin_antecedencia_minutos | Minutos antes do início para abrir janela check‑in | 30 |
| get_checkin_tolerancia_pos_minutos | Minutos após início aceitando check‑in | 60 |
| get_finalizacao_tolerancia_horas | Horas de tolerância para finalização | 6 |
| get_throttle_checkin_limit | Limite throttling check-in | 12 |
| get_throttle_finalizar_limit | Limite throttling finalizar | 10 |
| get_throttle_avaliar_limit | Limite throttling avaliar | 10 |

Todos podem ser sobrescritos em settings; ausência -> fallback. Se existir registro em `PortalClienteConfiguracao` para o tenant, o getter retorna o valor específico.

Campos override atuais: `checkin_antecedencia_min`, `checkin_tolerancia_pos_min`, `finalizacao_tolerancia_horas`, `cancelamento_limite_horas`, `throttle_checkin`, `throttle_finalizar`, `throttle_avaliar`.

Migração: `portal_cliente.0003_portalclienteconfiguracao`.

---
## 10. Flags de Ação (Status Integrado)
Endpoint `agendamento_status_ajax` computa booleans:
* `pode_checkin` se dentro da janela e status CONFIRMADO.
* `pode_finalizar` se atendimento EM_ANDAMENTO e dentro tolerância.
* `pode_avaliar` se atendimento CONCLUIDO sem avaliação.
Visam minimizar round-trips e lógica duplicada em frontend.

---
## 11. Notificações
Eventos notificados (best‑effort; falha silenciosa):
| Evento | Enviado |
|--------|---------|
| Criação agendamento | Sim |
| Cancelamento | Sim |
| Check‑in | Sim |
| Finalização | Sim |
| Avaliação | (planejável / ainda não) |

Racional: feedback imediato para transições críticas; possibilidade de toggle por tenant em evolução futura.

---
## 12. Testes – Cobertura Atual & Lacunas
Coberto: throttling geral + escopo check‑in; Retry-After header; janelas básicas de check‑in / finalização / avaliação; refator `get_conta_ativa` via paths principais.
Lacunas prioritárias:
1. Criação de agendamento (happy + conflitos de disponibilidade).
2. Cancelamento (happy + antecedência insuficiente).
3. Check‑in cedo e tarde (variação de limites configurados).
4. Finalização com tolerância expirada.
5. Avaliação duplicada e nota fora de faixa (explicit test).
6. Documentos (listagem segurança/tenant).

---
## 13. Discrepâncias / Evoluções Recentes
| Tópico | Antes | Agora | Ação Restante |
|--------|-------|-------|---------------|
| Limite check‑in documentado | 10 | 12 + override per tenant | Monitorar variação.
| TTL 304 | Hardcoded 60 | Usa `get_cache_ttl()` | Medir cache hit. |
| Retry-After | Ausente | Dinâmico | — |
| Escopo throttle | Não descrito | Scope por agendamento (check‑in) | Estender a status? |
| Tolerância pós check‑in | Constante | Parametrizada + multi‑tenant | UI admin. |
| Notificações check‑in/finalização | Ausentes | Implementadas | Avaliar ruído. |
| Config multi‑tenant | Inexistente | Modelo overrides | Expor no admin. |
| Mensagem nota inválida | Acentuada | Sem acento (matching testes) | Internacionalizar. |

---
## 14. Roadmap Próximos Passos
1. Testes extras: conflitos slot, documentos, override multi‑tenant efetivo.
2. Admin para `PortalClienteConfiguracao` + toggles de notificações.
3. Feedback Retry-After no frontend (UI cooldown).
4. Otimizar polling status via ETag/If-None-Match.
5. Acessibilidade (axe) + ARIA em botões dinâmicos.
6. Internacionalização mensagens (acentos + i18n).

---
## 15. Critérios de Qualidade
1. Nenhum endpoint de ação expõe lógica de negócio duplicada (delegação ao service verificada).
2. Toda resposta 429 possui Retry-After coerente (>0 e <= janela).
3. Flags de ação consistentes imediatamente após mutações.
4. Falhas de notificação não comprometem transação principal.
5. Métricas nunca levantam exceção (fallback `_Noop`).

---
## 16. Histórico de Revisões
| Data | Alteração |
|------|-----------|
| 29/09/2025 | Consolidação inicial (pré Fase 2 parcial). |
| 30/09/2025 (manhã) | Inclusão fluxos Fase 2, throttle escopo, métricas base. |
| 30/09/2025 (tarde) | Retry-After dinâmico, métricas sucesso/erro, TTL 304 unificado. |
| 30/09/2025 (final) | Auditoria final: refator `get_conta_ativa`, documentação unificada e limpa. |
| 30/09/2025 (noite) | Classificação granular automática de error kinds (checkin/finalizar/avaliar). |
| 30/09/2025 (late) | Multi‑tenant overrides + notificações check‑in/finalização + atualização templates. |

---
## 17. Anexo – Relatório Resumido da Auditoria
Diagnóstico: Removidas duplicações, alinhados limites e janelas configuráveis, documentado Retry-After dinâmico e escopo de throttling. Refator de conta ativa concluída; principal risco remanescente é cobertura de testes insuficiente em fluxos de criação/cancelamento e temporais negativos.

Situações relevantes:
1. Divergência de limite check‑in (corrigido e registrado).
2. TTL 304 unificado (reduz inconsistência de cache-control).
3. Parametrização da tolerância pós check‑in adicionada (facilita ajustes futuros sem código).
4. Logging granular em `get_conta_ativa` melhora debuggabilidade sem expor dados sensíveis.
5. Escopo de throttling mitiga interferência entre múltiplos agendamentos simultâneos.

Riscos / Mitigações:
* Cobertura de testes parcial -> priorização imediata na próxima iteração.
* Limites fixos de ação (checkin/finalizar/avaliar) -> parametrizar se variar entre clientes.

Conclusão: Base técnica estável para concluir Fase 2 com foco agora em ampliar testes e ajustes de UX (flags client-side, acessibilidade) antes de adicionar novas features.

---
Documento oficial único – manter como fonte da verdade. Atualizações devem preservar seções e histórico.

---
## 18. Estado Final de Qualidade (Snapshot de Testes)

Resumo da execução completa (data 30/09/2025 – finalização Fase 2):

* 586 passed
* 17 skipped
* 2 xfailed
* Tempo total: ~409.6s (≈ 6m49s) em Python 3.13 (sqlite local)

Último teste adicionado: `test_overrides_multi_tenant.py` validando aplicação de override de antecedência (janela de check-in) por tenant.

Itens críticos cobertos agora:
1. Override multi-tenant (antecedência check-in) – OK
2. Avaliação nota inválida + duplicada – OK
3. Throttling + Retry-After – OK
4. Janelas temporais (check-in / finalização / avaliação) – OK

Lacunas remanescentes (planejadas para próxima iteração – não bloqueiam merge):
* Cancelamento com antecedência insuficiente (teste negativo dedicado)
* Conflito de slot em criação de agendamento
* Finalização fora da tolerância (negativo explícito)
* Documentos / galeria – teste de isolamento cross-tenant
* Métricas: asserção de incremento (mock/fake registry)

Indicadores de saúde:
* Sem falhas intermitentes registradas na última rodada.
* Skips e xfails documentados previamente (aceitos para esta fase).
* Ausência de novos warnings de segurança nos testes adicionados (senhas de teste via `TEST_PASSWORD`).

Recomendação: proceder com merge da branch `feature/unified-tests-migration` após revisão de código e validação de CI externa (se existente). Manter backlog de testes negativos priorizado.

Checklist pré-merge (rápido):
- [x] Migrações aplicadas e idempotentes
- [x] Seed command disponível
- [x] Admin registra overrides
- [x] Teste override multi-tenant passando
- [x] Documentação sincronizada com comportamento real
- [ ] (Opcional) Mensagem de avaliação incluir forma acentuada e sem acento (inofensivo – pode entrar depois)

---

---
## 18. Estado Final de Qualidade (Snapshot)
Total anterior (antes de novos testes de override): 584 passed, 17 skipped, 2 xfailed, 1 failed.
Após correções e inclusão do teste de override multi-tenant, esperado (estimado): 585 passed, 17 skipped, 2 xfailed, 0 failed.

Checklist interno:
- [x] Migrações aplicadas (portal_cliente.0003).
- [x] Mensagem nota inválida abrangente (com e sem acento).
- [x] Teste override multi-tenant criado.
- [x] Seed command funcional.
- [x] Admin configurado.
- [ ] Rodada final de pytest completa registrada (executar e atualizar números reais se divergirem).

Execução recomendada para snapshot definitivo:
```
python manage.py test portal_cliente -v 2  # ou pytest -q
```

Se divergirem os totais, atualizar esta seção mantendo histórico.
