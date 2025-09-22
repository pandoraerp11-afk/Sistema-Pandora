# Handoff para Próximo Agente de IA

Atualizado: 2025-09-11

Este documento guia a continuidade do trabalho com segurança e consistência.

## Resumo do estado atual
- Documentação consolidada: User Management (USER_MANAGEMENT.md) e Permission Resolver (PERMISSION_RESOLVER.md).
- Índice canônico: docs/INDEX.md e log de remoções: docs/_DELETION_LOG.md.
- Prontuários: status “feito × faltante” e próximos passos em docs/PRONTUARIOS_ARQUITETURA.md.
- Duplicatas/obsoletos removidos; plano legado de Prontuários está em docs/legacy/.
- Teste de higiene impede reintroduzir arquivos obsoletos: tests/test_docs_hygiene.py.

## Política de trabalho (fases)
1) Modernizar e corrigir sem excluir (fase 1): não remover funcionalidades/arquivos existentes; apenas melhorar/segurar/padronizar.
2) Limpeza definitiva (fase 2): após validar melhorias e testes, remover legados obsoletos, registrando no docs/_DELETION_LOG.md.
3) Documentação unificada (fase 3): atualizar docs/INDEX.md e manter 1 guia por tema; material antigo vai para docs/legacy/.

## Como testar (essencial)
- Use docs/TESTES_ORGANIZACAO.md como fonte única de padrões.
- Estruture por domínio (ex.: tests/prontuarios, shared/tests).
- Markers: slow, permission, security, login, twofa (ver pytest.ini).
- Execução comum (Windows cmd na raiz backand):
  - pytest -q
  - pytest -m "not slow" -q
  - pytest tests\test_docs_hygiene.py -q
- Ao tocar um módulo, adicione testes relevantes no mesmo PR.

## Regras de dúvida e pesquisa exaustiva
- Em caso de dúvida, questione o requisito antes de implementar.
- Evite criar do zero: há grande chance de existir função/serviço/comando reutilizável.
- Pesquise definições e usos no workspace inteiro antes de alterar contratos.

## Próximos passos sugeridos (baixo risco → impacto)
1. **Finalizar Migração para `agendamentos`**: O novo módulo `agendamentos` já substitui a maior parte da lógica de agendamento do `prontuarios`. O próximo passo é refatorar as views e templates de `prontuarios` para utilizarem os serviços e APIs do novo módulo, desativando as implementações legadas.
2. **Consolidar Documentação**: Atualizar `docs/PRONTUARIOS_ARQUITETURA.md` para marcar as seções de agendamento como obsoletas e apontar para `docs/MODULO_AGENDAMENTOS.md` como a nova fonte da verdade.
3. **Testes de Integração**: Criar testes que validem o fluxo completo de agendamento através das novas APIs e serviços, garantindo que a integração com `clientes` e `profissionais` (usuários) está correta.
4. **Limpeza Definitiva**: Após a migração ser validada em produção, planejar a remoção dos modelos, views e URLs de agendamento do módulo `prontuarios`, registrando a remoção em `docs/_DELETION_LOG.md`.

## Estado Específico Após Limpeza de "procedimento" (2025-09-11)
Conclusões alcançadas nesta rodada:
- Removidos endpoints, formulários, rota Select2 e testes ligados a `procedimento` em `prontuarios`.
- Portal / JS migrado para `servico_id` (sem alias de URL). Cache keys atualizados (`portal_serv_*`).
- Comando de auditoria e comando de migração para eventos legado de agenda criados: `audit_evento_tipo_procedimento` e `migrate_evento_tipo_procedimento_to_servico`.
- Testes focados de Select2 reescritos para clientes / profissionais / slots; nenhum uso residual de `create_procedimento_basico`.
- Alias helper removido de `tests/prontuarios/helpers.py` (só permanece `create_servico_basico`).
- Documentação atualizada: `MODULO_PRONTUARIOS.md`, `prontuarios/API_README.md`, `MODULO_SERVICOS.md` seção de limpeza.
 - Frontend atualizado para serviços clínicos: `ServicoForm` agora inclui toggle `is_clinical`; bloco dinâmico com `ServicoClinicoForm` renderizado em `partials/servico_form_tab_dados_principais.html`.

Itens pendentes (prioridade para próximo agente):
1. Grep final global para "procedimento" excluindo `migrations/` e histórico (confirmar zero ocorrências funcionais). Caso só sobrem comentários de histórico, decidir se mantêm como nota de migração ou movem para `docs/legacy/`.
2. Remover choice legacy `tipo_evento='procedimento'` de `agenda.Evento` após janela de auditoria (14 dias sem registros novos). Exigir: rodar `manage.py audit_evento_tipo_procedimento --since 14d` (se existir opção — se não, adaptar) e validar retorno vazio; então aplicar migração.
3. Adicionar 1–2 testes de integração ponta-a-ponta envolvendo: criação de Serviço Clínico -> criação de Agendamento -> criação de Atendimento ligado ao slot -> cancelamento libera slot.
4. Revisar se há caches ou serializers antigos esperando chaves `procedimento_*` fora de prontuários (ex: módulos `portal_cliente`, `relatorios`, `bi`). Se encontrados, renomear para `servico_*`.
5. Criar pequena doc em `docs/FRONTEND_PORTAL_SERVICOS.md` consolidando parâmetros usados pelo JS (atual fonte é `static/js/portal_cliente.js`).
6. (Opcional) Elevar cobertura de testes das novas branches de permission caching (já existem testes edge, mas podem ser expandidos para cenários de invalidation sob carga / multi-tenant simultâneo).

## Próximo Foco Sugerido (Frontend / UX)
Agora que a camada de domínio está estável:
- Revisar componentes front (templates + JS) para remover nomes visuais antigos (ex: rótulos exibindo "Procedimento").
- Introduzir loading states uniformes para selects AJAX (clientes, profissionais, serviços). Padrão sugerido: spinner inline + atributo `aria-busy="true"`.
- Adicionar debounce (250ms) nas buscas Select2 custom se ainda não implementado.
- Avaliar pré-busca (prefetch) de 5 serviços mais usados por tenant (cache local por 5 min) para melhorar UX inicial.

## Referências Canônicas Rápidas
- Regras imutáveis: `docs/MODULO_SERVICOS.md` (seção Regras de Negócio IMUTÁVEIS).
- Agenda (novo): `docs/MODULO_AGENDAMENTOS.md`.
- Prontuários arquitetura: `docs/MODULO_PRONTUARIOS.md`.
- Auditoria / AI: `ai_auditor/` + comandos de auditoria.

## Mini Checklist para Retomar
- [ ] Rodar grep final "procedimento" (sem migrations) e registrar resultado no `_DELETION_LOG.md`.
- [ ] Avaliar remoção do choice legacy em agenda (após janela). 
- [ ] Criar testes E2E de fluxo Serviço → Agendamento → Atendimento → Cancelamento.
- [ ] Documentar portal front: parâmetros e eventos JS em arquivo dedicado.
- [ ] Integrar referências do bloco clínico (ver seção 9 em `MODULO_SERVICOS.md`).
- [ ] Revisar rótulos UI (substituir qualquer "Procedimento" remanescente por "Serviço").
- [ ] Planejar migração final de choice e atualizar CHANGELOG.

## Alertas Importantes
- NÃO alterar validações ou semântica de `ServicoClinico`.
- NÃO reintroduzir alias de compatibilidade implícita (`procedimento_id`). Se integração externa precisar, criar camada explícita versionada.
- Usar sempre `servico`/`servico_id` em novas APIs, DTOs e eventos de domínio.

---
Documento pronto para handoff. Atualize esta seção ao concluir cada item pendente.

---

## Atualização de Sessão – 2025-09-19 (Wizard Tenant / Métricas / Correlation ID)

### Contexto Trabalhado
- Foco: Observabilidade do Wizard de criação de Tenant (métricas, correlation id em headers) e testes associados.
- Implementações pré-existentes já traziam: métricas avançadas (`record_finish_latency` com outcomes, abandono, gauges Prometheus, função `reset_all_metrics`, management command `wizard_metrics_reset`).
- Objetivo da sessão: Garantir header `X-Wizard-Correlation-Id` em finalização do wizard + teste dedicado; validar comando de reset de métricas.

### Alterações Realizadas
- Criados / ajustados testes:
  - `core/tests/test_wizard_correlation_header.py` (novo) – valida presença de header e criação de tenant.
  - `core/tests/test_wizard_metrics_reset_command.py` – ajustado para usar API correta (`inc_finish_success`, `inc_finish_subdomain_duplicate`) e validar reset.
- View `finish_wizard` recebeu múltiplos ajustes para tentar garantir header em todos os retornos (early returns, exceções, duplicidades) incluindo:
  - Helper `_redirect_wizard_home()` modificado para já anexar o header.
  - Adicionadas inserções de header em blocos de exceção e caminhos de validação falha.
- Teste de métricas passou após correção (reset confirmando counters zerados).
- Teste de correlation header ainda falha (header ausente) indicando que o fluxo *não alcança* o trecho de finalização real do wizard (redirect sem header provém de caminho anterior ou não instrumentado antes da modificação). Migrações longas mascaram o tempo de execução.

### Diagnóstico Profundo do Header Ausente
1. `finish_wizard` só é chamado quando a lógica de POST reconhece a intenção final + integridade dos dados do wizard. 
2. O teste injeta diretamente `tenant_wizard_step=7` e uma estrutura mínima de dados; porém podem faltar pré-condições implícitas (progressão de steps, marcações internas ou permissão exata). 
3. Possível verificação de permissão (ex.: `is_superuser`) pode impedir a execução completa usando apenas `is_staff=True`. 
4. A estratégia atual (espalhar header em early returns) aumenta complexidade e ainda não garante interceptação antes de um *possível redirect externo* (ex.: middleware ou mixin antes de `finish_wizard`). 
5. Causa raiz provável: fluxo não chega ao bloco de finalização; correção durável = centralizar geração/aplicação do correlation id no `dispatch` da view em vez de em múltiplos retornos.

### Riscos Técnicos Introduzidos
- Múltiplos pontos de escrita do header geram risco de inconsistência se futura refatoração alterar algum caminho.
- Duplicações de lógica de early return dificultam manutenção (efeito cascata se a view sofrer reorganização).

### Plano Definitivo Recomendado (Próxima Sessão)
1. Refatorar `dispatch` da view do wizard:
   - Gerar `correlation_id` único no início.
   - Armazenar em `request._wizard_cid` e chamar `set_last_finish_correlation_id`.
   - Envolver `super().dispatch`; qualquer `HttpResponse` final recebe header centralizado.
   - Em exceções, registrar métricas (`inc_finish_exception`, `record_finish_latency(..., outcome='exception')`).
2. Ajustar `finish_wizard` para reutilizar `request._wizard_cid` (não gerar novo).
3. Remover código redundante de inserção de header em early returns (limpeza). 
4. Ajustar teste para criar usuário com `is_superuser=True` (confirmar regra) e usar fixture helper para wizard data mínima válida.
5. Criar helper de teste `build_minimal_wizard_session(client, tipo='PJ')` evitando repetição de dicionários.
6. Adicionar teste negativo: usuário sem permissão recebe redirect com header (valida abordagem via `dispatch`).
7. Otimização de tempo: habilitar `--reuse-db` usando backend persistente (não `:memory:`) ou configurar `TEST_DB_NAME` temporário para minimizar migrações repetidas.

### Itens Entregues vs Pendentes
- ENTREGUE: Teste de reset de métricas verde; comando de reset validado – Backlog B1 pode ser marcado como concluído.
- ENTREGUE: Instrumentação ampla para header (ainda não consolidada, mas funcional em múltiplos caminhos).
- PENDENTE: Header ainda não presente no redirect do teste de criação (refatorar dispatch + permissões).
- PENDENTE: Simplificação de código removendo duplicações de header após refatoração.
- PENDENTE: Documentar seção “Correlation ID Global” no `WIZARD_TENANT_README.md` e marcar B1 concluído.

### Próximas Ações Prioritárias (Checklist)
- [ ] Refatorar `dispatch` (centralizar correlation id + header universal).
- [ ] Atualizar `finish_wizard` para usar `request._wizard_cid`.
- [ ] Remover headers redundantes dos early returns (após garantir testes verdes).
- [ ] Criar fixture/helper de sessão do wizard.
- [ ] Ajustar teste para superuser (ou alinhar regra de permissão se o negócio exigir apenas staff).
- [ ] Adicionar teste de header em cenário de permissão negada.
- [ ] Atualizar README / `WIZARD_TENANT_README.md` (seção Observabilidade: fonte única do correlation id).
- [ ] Marcar Backlog B1 como concluído na doc.

### Observabilidade e Métricas – Notas
- `record_finish_latency` não incrementa counters; counters dependem de `inc_finish_success|duplicate|exception` (validado em teste). 
- Tempo de teste alto está dominado por migrações; ganho imediato usando base reutilizável persistente.

### Sugestão de Rollback Parcial (se necessário)
Se a refatoração via `dispatch` demorar, manter apenas uma função utilitária para anexar header e chamá-la no retorno final + exceção enquanto investiga a causa (permissão / progression). Porém a abordagem do `dispatch` é mais robusta.

### Anotações Rápidas para o Próximo Agente
- Evitar novos patches incrementais em `finish_wizard` antes da refatoração, para não aumentar divergência.
- Validar permissão real exigida: se a business rule for “apenas superuser cria tenants”, atualizar teste (estratégia preferível a afrouxar política sem aprovação).
- Após centralização, rever se `set_last_finish_correlation_id` deve migrar para `dispatch` (provável sim) para coerência.

---

## Quality gates por entrega
- Lint/build ok; pytest verde; tests/test_docs_hygiene.py verde.
- Smoke test do fluxo alterado.
- Documentação sincronizada se houver mudança de comportamento público.

## Política específica — ServicoClinico (NÃO ALTERAR REGRAS)

- As regras de negócio do perfil clínico (`servicos.ServicoClinico`) são IMUTÁVEIS sem aprovação explícita do responsável do domínio.
- Não altere semântica, validações, defaults, nem cálculos de campos clínicos. Qualquer mudança deve ser aditiva e opcional.
- Centralize a lógica clínica em `servico.perfil_clinico`. Evite duplicar regras em outros módulos.
- Documento canônico: `docs/MODULO_SERVICOS.md` (seção "Regras de Negócio IMUTÁVEIS (ServicoClinico)").
