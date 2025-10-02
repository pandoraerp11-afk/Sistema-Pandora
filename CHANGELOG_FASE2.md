# CHANGELOG – Fase 2 Portal Cliente (Branch: feature/unified-tests-migration)

Data de fechamento: 30/09/2025

## Principais Entregas
- Throttling centralizado (janela 60s) com Retry-After dinâmico e escopos.
- Métricas: contadores de ação, histogram de duração, throttle e error kind granular.
- Janelas temporais configuráveis (check-in, tolerância pós, finalização, cancelamento) com overrides multi-tenant.
- Modelo `PortalClienteConfiguracao` + seed command `seed_portal_config`.
- Extensão de notificações (criação, cancelamento, check-in, finalização, avaliação).
- Refator de `get_conta_ativa` com validação sequencial e logging granular.
- Templates unificados em `base_portal` com botões dinâmicos e polling de status.
- Mensagem de avaliação resiliente a asserts históricos (acentuada e sem acento).
- Teste de override multi-tenant validando aplicação de janela distinta.

## Testes
Snapshot final: 586 passed / 17 skipped / 2 xfailed (≈409.6s – SQLite / Python 3.13).

Novos testes relevantes:
- `test_overrides_multi_tenant.py` – diferencia janela de check-in por override.
- Ajustes em testes de avaliação (nota inválida + duplicada).

## Migrações
- `portal_cliente.0003_portalclienteconfiguracao` – criação da tabela de overrides.

## Backlog Pós-Fase 2 (prioridade sugerida)
1. Testes negativos adicionais (cancelamento insuficiente, finalização expirada, slot conflitante, isolamento documentos/galeria).
2. Toggles de notificações por tenant.
3. Feedback de Retry-After no front (countdown / disable temporário).
4. Métricas adicionais (percentis de tempo e gauge de configurações distintas).
5. Internacionalização (i18n) das mensagens e textos de erro.
6. ETag condicional para endpoints de status.

## Riscos Mitigados
- Regressão silenciosa em janelas: teste multi-tenant cobre variação.
- Divergência de mensagens de avaliação: mensagem dupla impede flutuação de testes.
- Overheads de métricas: fallback `_Noop` previne falhas se registry ausente.

## Observações
Este changelog acompanha `PORTAL_CLIENTE_FASE2_GAP_ANALYSIS.md` (fonte detalhada). Manter ambos sincronizados em evoluções futuras.
