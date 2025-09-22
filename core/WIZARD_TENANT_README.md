# Wizard de Criação/Edição de Tenant (Core)
Documento auditado e sincronizado com o código em 2025-09-22. Versão consolidada: remove redundâncias, aplica numeração linear e desloca detalhes extensos para Apêndice. Fonte autoritativa do comportamento do wizard.
## Sumário
1. Visão Geral
2. Objetivos e Escopo
3. Permissões & Acesso
4. Fluxo de Steps
5. Estrutura de Sessão
6. Navegação Livre vs Finalização
7. Regras de Negócio (Autoritativas)
8. Validação de Subdomínio
9. Persistência & Ordem de Consolidação
10. Normalização de Módulos (`enabled_modules`)
11. Administradores (Step 6)
12. Endereços
13. Contatos & Redes Sociais
14. Draft vs Dado Limpo
15. Logging (Resumo)
16. Métricas & Correlation ID
17. Tratamento de Erros & Transações
18. Segurança & Limites
19. Riscos & Assunções
20. Melhorias Futuras (Backlog)
21. Testes e Cobertura
22. Scripts Úteis
23. Checklist Pré-Deploy
24. Histórico de Alterações
25. Apêndice A – Notas de Implementação Avançadas

---

## 1. Visão Geral
Wizard multi-step para criação/edição de Tenants. Usa sessão como storage temporário; só persiste após validação integral no finish.

## 2. Objetivos e Escopo
Objetivos:
- Garantir criação/edição consistente de Tenants.
- Centralizar validações críticas (subdomínio, identificadores).
- Permitir exploração livre sem perda de rascunho.

Fora de Escopo (atual):
- Validação rígida obrigatória por step antes de navegar.
- Persistência parcial (antes do finish).
- Fluxo complexo de versionamento de rascunho.

Observação: finalização cobre admins na mesma transação — risco de órfãos mitigado.

## 3. Permissões & Acesso
Somente superusuários (`is_superuser=True`). Enforce via `test_func` na view.
Endpoints auxiliares (AJAX e navegação): restritos a superusuários autenticados e devolvem `X-Wizard-Correlation-Id`.
Rotas: `check_subdomain`, `wizard_goto_step`, `wizard_validate_field`.

## 4. Fluxo de Steps
1. Identificação (PJ/PF)
2. Endereços
3. Contatos
4. Documentos
5. Configurações
6. Administradores (opcional)
7. Confirmação & Finalização

Características:
- Navegação livre (goto step) preserva rascunho.
- Step 7 gera preview consolidado.

## 5. Estrutura de Sessão
Chaves:
```
tenant_wizard_step
tenant_wizard_editing_pk
tenant_wizard_data = {
  'step_1': {'pj': {...}, 'pf': {...}, 'main': {...}},
  'step_2': {'main': {...}},
  'step_3': {'main': {...}},
  'step_4': {'main': {}},
  'step_5': {'main': {...}},
  'step_6': {'main': {...}},
  'step_7': {'main': {}}
}
```
Skeleton: se pular direto > step 1 define apenas `step_1.main.tipo_pessoa='PJ'` (não finalizável).

## 6. Navegação Livre vs Finalização
| Aspecto | Navegação Livre | Finalização |
|---------|-----------------|-------------|
| Validação integral | Não | Sim |
| Bloqueio por erro | Não | Sim |
| Aceita skeleton | Sim | Não |
| Persistência DB | Não | Sim |
| Cria relacionados | Não | Sim |

## 7. Regras de Negócio (Autoritativas)
1. `tipo_pessoa` obrigatório (PJ/PF).
2. PJ exige `cnpj`; PF exige `cpf`.
3. Campos mínimos: `name`, `tipo_pessoa`, identificador válido.
4. Subdomínio: obrigatório, único, minúsculo, regex válido, não reservado.
5. `portal_ativo=True` → incluir `portal_cliente` em `enabled_modules` (coerência); caso contrário retirar se presente incoerente.
6. Admins opcionais; linha parcial exige e-mail válido único no lote.
7. Somente finish grava banco.
8. Apenas superusuários acessam o wizard.

## 8. Validação de Subdomínio
Regex: `^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$`.
Reservados: `www`, `admin`, `static`, `media`, `api`.
AJAX: `GET /core/tenants/check-subdomain/?subdomain=<v>` → `{available, reason, normalized}`.
Revalidado no finish (fonte de verdade).

## 9. Persistência & Ordem de Consolidação
`finish_wizard`:
1. Correlation ID (gerado em `dispatch`).
2. Cria `WizardContext` + probe defensivo `form.save(commit=False)` Step 1.
3. Pré-calcula duplicidade de subdomínio.
4. `validate_wizard_data_integrity`: tipo, mínimos, subdomínio válido/único.
5. Inválido → registra métrica (duplicate/exception) e redireciona com mensagem:
  - Edição: seta Step 5 e redireciona para `core:tenant_update`.
  - Criação: redireciona para `core:tenant_create`.
6. Válido → `transaction.atomic()` envolvendo:
   a. Aplicar Step 1 (identificação) em memória.
   b. Aplicar `subdomain` & `status` (parcial Step 5) antes do primeiro save.
   c. Primeiro `tenant.save()`.
   d. Endereços → Contatos → Configurações (módulos) → Administradores.
7. Sucesso: incrementa `finish_success`, registra latência, limpa sessão.
8. Exceção: rollback, incrementa `finish_exception`, outcome exception.

## 10. Normalização de Módulos (`enabled_modules`)
Entrada: lista, JSON, CSV, set, dict legado.
Pipeline:
1. Converte para lista.
2. Remove duplicatas preservando primeira ocorrência.
3. Ordena (previsibilidade de logs).
4. Ajusta coerência com `portal_ativo`.

## 11. Administradores (Step 6)
Fonte: `admins_json` ou campos legados.
Processo:
- Ignora linhas totalmente vazias.
- Normaliza aliases (admin_email → email etc.).
- Atualiza usuários existentes (nome, telefone, ativo, cargo, senha válida) antes de criar novos.
- Novos: senha robusta (bulk ou gerada) se ausente/curta (<8).
- Bulk create + reconsulta para garantir PK antes de criar `TenantUser`.
- Role "Administrador" garantida via `get_or_create`.

## 12. Endereços
- Principal: `update_or_create(tipo=PRINCIPAL)`.
- Adicionais: replace total (delete+create) limitado a 50.
  Limite aplicado também na gravação (slicing defensivo durante a consolidação).
- CEP: se 8 dígitos → formata `00000-000`.

## 13. Contatos & Redes Sociais
- Campos principais direto no Tenant.
- Lista adicional via `contacts_json` (replace total, limite 100).
  Limite aplicado também na gravação (slicing defensivo durante a consolidação).
- Redes Sociais via JSON (`parse_socials_json`) com fallback a campos legados.
  Limite aplicado na gravação (primeiros 50 pares nome→link são persistidos).

## 14. Draft vs Dado Limpo
| Aspecto | Draft | Dado Limpo |
|---------|-------|------------|
| Origem | POST bruto | `cleaned_data` |
| Uso | Repreencher forms | Persistência final |
| Armazenamento | Sessão incremental | Sessão consolidada |
| Pode conter inválidos | Sim | Não |

## 15. Logging (Resumo)
- info: eventos de negócio (finish ok, criação/atualização, consolidação final)
- debug: normalizações, skeleton, contagens, probe
- warning: JSON/socials inválidos ignorados
- error: integridade ou exceção em finalização

## 16. Métricas & Correlation ID
Correlation ID: gerado em `dispatch`, header `X-Wizard-Correlation-Id` em toda resposta (inclui Redirect e JSON).
Métricas: counters (success/duplicate/exception), histograma geral + por outcome, sessões ativas/abandonadas, erros recentes, tempos até abandono, último CID.
Classificação: caminhos inválidos não-duplicados são agregados como `exception` no histograma por outcome.
Hook opcional `WIZARD_LATENCY_SINK(seconds, correlation_id, outcome)` (fallback para assinatura antiga).
Probe pode elevar `finish_exception` sem bloquear sucesso (intencional: visibilidade de erros latentes).

## 17. Tratamento de Erros & Transações
- `transaction.atomic()` cobre todo pipeline (inclui admins).
- JSON inválido: warning + ignora.
- Exceções: rollback integral + métricas outcome.
 - Sessão no erro: controlada pela flag `PRESERVE_WIZARD_SESSION_ON_EXCEPTION` (default: True).
   Se `False`, a sessão do wizard é limpa ao ocorrer exceção no finish; em sucesso, sempre limpa.
  - Configuração: pode ser ajustada via `settings.PRESERVE_WIZARD_SESSION_ON_EXCEPTION` ou por variável de ambiente `PRESERVE_WIZARD_SESSION_ON_EXCEPTION`.

Exemplos:

Python (settings.py):

```
# Wizard Tenants – sessão no erro (default True)
PRESERVE_WIZARD_SESSION_ON_EXCEPTION = True  # ou False
```

Ambiente (Windows PowerShell):

```
$env:PRESERVE_WIZARD_SESSION_ON_EXCEPTION = "False"
```

## 18. Segurança & Limites
- Acesso: superusuários apenas.
- Limites: `MAX_ADDITIONAL_ADDRESSES=50`, `MAX_ADMINS=50`, `MAX_CONTACTS=100`, `MAX_SOCIALS=50`.
- Subdomínio: dupla validação (AJAX + finish) + reservas.
- Sanitização leve (CEP, trims); demais validações nos forms/validators.
 - Endpoints auxiliares exigem superusuário e sempre retornam `X-Wizard-Correlation-Id`.

## 19. Riscos & Assunções
| Risco | Situação | Mitigação |
|-------|----------|-----------|
| Skeleton parcial | Permitido | Bloqueio na integridade final |
| Sessão grande | Possível | Limites + baixo volume |
| Replace total listas | Perda se draft incompleto | Simplicidade + preview Step 7 |
| Admins órfãos | Mitigado | Transação atômica |
| Exceções de probe elevam métrica | Intencional | Transparência de falhas |
| Race subdomínio | Baixa | Validação final autoritativa |

## 20. Melhorias Futuras (Backlog)
1. Validação incremental opcional por step.
2. Hash/diff por step para reprocessamento seletivo.
3. Sanitização/truncagem central de strings extensas.
4. Services dedicados (`WizardStateService`, `TenantAssembler`).
5. Otimizar bulk de admins.
6. Badge "Rascunho incompleto".
7. Métrica de taxa sucesso/falha.
8. Flag obrigando Step 1 antes de navegar.

## 21. Testes e Cobertura
Principais:
- `core/tests/test_views.py`
- `core/tests/test_wizard_subdomain_edges.py`
- `core/tests/wizard_test_utils.py`
Coberto:
- Subdomínio: obrigatório, regex, reservas, unicidade case-insensitive.
- Módulos: normalização heterogênea.
- Métricas: counters, abandono, latências, hook.
- Fluxo E2E com admins, modules, socials.

## 22. Scripts Úteis
```
pytest -q core/tests/test_wizard_subdomain_edges.py
pytest -q
```

## 23. Checklist Pré-Deploy
- [ ] Criar PJ com subdomínio válido + `portal_cliente` ativo.
- [ ] Criar PF sem admins e finalizar.
- [ ] Pular direto para Step 5, voltar e preencher Step 1, finalizar.
- [ ] Simular subdomínio duplicado em edição (permanece Step 5).
- [ ] Admin com senha curta → senha gerada.
- [ ] Módulos: vazio → adicionar → finalizar.
- [ ] JSON inválido (admins/socials) → warning sem quebra.
- [ ] Perda de sessão entre Step 5 e 7 → reconstrução sem resíduos.

## 24. Histórico de Alterações
| Data | Alteração | Autor | Código Modificado? |
|------|-----------|-------|--------------------|
| 2025-09-22 | Sincronização pós-ajustes (redirect inválido 302, superuser em auxiliares, CID em todas respostas, slicing na gravação, flag de sessão) | Assistente | Sim |
| 2025-09-22 | Auditoria completa, numeração linear, atomicidade admins clarificada | Assistente | Não |
| 2025-09-19 | Reescrita integral consolidada | Assistente | Não |
| 2025-09-19 | Versão anterior (auditoria adicionada) | Assistente | Não |
| 2025-09-19 | Observabilidade expandida (métricas/correlation) | Assistente | Não |

---
Garantia: Regras alinhadas ao código; nenhuma regra nova introduzida.

## 25. Apêndice A – Notas de Implementação Avançadas
(Resumo condensado das notas operacionais)
- Salvamento parcial de step (edição) não revalida integridade global.
- Reaplicação de subdomínio/status após primeiro save garante coerência.
- Captura manual de `enabled_modules` fora do prefix `main`.
- Ordem relacionados: Endereços → Contatos → Configuração → Admins.
- Documentos: placeholder em sessão; processamento delegado (service externo).
- Subdomínio duplicado no finish força Step 5.
- `bulk_admin_password` fallback para linhas com senha curta.
- `WizardContext` encapsula acesso; fallback de tipo pessoa.
- Socials parse via `parse_socials_json` (defensivo).
- Enabled modules preview usa `normalize_enabled_modules`.
- Logs rebaixados (debug) para reduzir ruído.
- Limites centralizados em `wizard_limits`.
- Métricas: counters, histogramas por outcome, abandono, erros recentes, tempo de abandono.
- Hook de latência com fallback assinatura antiga.
- Header `X-Wizard-Correlation-Id` via `dispatch`.
- Snapshot inclui `latency_by_outcome`, `time_to_abandon`, `last_finish_correlation_id`.
- Settings opcionais: `WIZARD_MAX_LATENCIES`, `WIZARD_MAX_ERRORS`, `WIZARD_MAX_ABANDON_LATENCIES`, `WIZARD_ABANDON_THRESHOLD_SECONDS`, `WIZARD_LATENCY_WARN_THRESHOLD`.
- Probe `save(commit=False)` registra falhas sem abortar finish.
- Backward compatibility preservada em métricas e hook.

Fim do documento.
# Wizard de Criação/Edição de Tenant (Core)

Documento completamente reescrito (substituição integral). Nenhuma regra de negócio foi alterada; apenas consolidada e clarificada. Esta versão elimina redundâncias entre a descrição inicial e a auditoria anterior.

## Sumário
1. Visão Geral
2. Objetivos e Escopo
3. Fluxo de Steps
4. Estrutura de Sessão
5. Navegação Livre vs Finalização
6. Regras de Negócio (Autoritativas)
7. Validação de Subdomínio
8. Consolidação e Persistência
9. Normalização de Módulos (`enabled_modules`)
10. Administradores (Step 6)
11. Endereços
12. Contatos & Redes Sociais
13. Draft vs Dado Limpo
14. Logging & Observabilidade
15. Tratamento de Erros & Transações
16. Segurança & Limites
17. Riscos Aceitos
18. Melhorias Futuras (não implementadas)
19. Testes e Cobertura
20. Scripts Úteis
21. Checklist Pré-Deploy
22. Histórico de Alterações
23. Notas de Implementação Avançadas

---
## 1. Visão Geral
Wizard multi-step unificado para criação e edição de Tenants. Usa sessão como armazenamento temporário; só persiste em banco após validação integral na etapa final.

## 2. Objetivos e Escopo
Objetivos:
- Guiar criação/edição de Tenant com consistência mínima garantida.
- Centralizar validação de subdomínio e regras essenciais.
- Permitir navegação livre exploratória sem perda de esboços.

Fora de Escopo (atualmente):
- Validação rígida em cada step antes de avançar.
- Persistência parcial antes da conclusão.
- Controle transacional sobre criação de todos relacionamentos (admins ficam parcialmente fora em caso de erro posterior).

## 3. Fluxo de Steps
1. Identificação (PJ/PF)
2. Endereços
3. Contatos
4. Documentos
5. Configurações (subdomínio, status, planos, módulos)
6. Administradores iniciais (opcional)
7. Confirmação & Finalização

Características:
- Steps podem ser acessados fora de ordem (navegação livre).
- Step 7 monta visão normalizada (preview) a partir de dados dispersos.

## 4. Estrutura de Sessão
Chaves:
```
tenant_wizard_step         -> int (step atual)
tenant_wizard_editing_pk   -> pk do Tenant se edição
tenant_wizard_data         -> {
  'step_1': {'pj': {...}, 'pf': {...}, 'main': {...}},
  'step_2': {'main': {...}},
  'step_3': {'main': {...}},
  'step_4': {'main': {}},
  'step_5': {'main': {...}},
  'step_6': {'main': {...}},
  'step_7': {'main': {}}
}
```
Skeleton: ao pular diretamente para um step > 1 cria-se `step_1.main.tipo_pessoa = 'PJ'` apenas para suportar preview (não satisfaz validação final).

## 5. Navegação Livre vs Finalização
| Aspecto | Navegação Livre | Finalização |
|---------|-----------------|-------------|
| Validação integral | Não | Sim (mínimos obrigatórios) |
| Bloqueio por erro de form | Não | Sim (step corrente e integridade) |
| Aceita skeleton Step 1 | Sim | Não |
| Persiste em banco | Não | Sim |
| Gera relacionamentos | Não | Sim |

## 6. Regras de Negócio (Autoritativas)
1. `tipo_pessoa` obrigatório (PJ ou PF) na finalização.
2. PJ exige `cnpj`; PF exige `cpf`.
3. Campos mínimos: `name`, `tipo_pessoa`, identificador (CNPJ/CPF) válidos.
4. Subdomínio obrigatório, único (case-insensitive), minúsculo, não reservado e aderente ao regex.
5. Se `portal_ativo = True` força presença de `portal_cliente` em `enabled_modules`; senão remove-o se inconsistente.
6. Administradores opcionais; qualquer linha parcialmente preenchida exige e-mail válido único dentro do lote.
7. Somente a finalização pode criar/atualizar dados em banco.

## 7. Validação de Subdomínio
Implementação: `core/validators.py`.
Regex: `^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$` (1–63 caracteres, não inicia/termina com hífen, hífens só internos).
Reservados: `www`, `admin`, `static`, `media`, `api`.
Processo:
- Capturado no Step 5 (rascunho).
- Validado AJAX opcionalmente antes (cheque disponibilidade).
- Revalidado integralmente no finish (fonte de verdade).

Endpoint AJAX:
`GET /core/tenants/check-subdomain/?subdomain=<valor>` (`core:check_subdomain`)
Resposta:
```
{"available": bool, "reason": "required|invalid_format|reserved|exists|ok", "normalized": "valor"}
```
Recomendação: debounce 300–500ms + cache simples no front.

## 8. Consolidação e Persistência
O método `finish_wizard`:
1. Recompõe `main_data` agregando todos forms cujo model é `Tenant`.
2. Valida integridade mínima (`validate_wizard_data_integrity`).
3. Salva/atualiza Tenant principal.
4. Aplica subdomínio e status pós-save se não originados do form principal.
5. Processa relacionamentos (endereços, contatos, módulos, admins) em sequência.
6. Usa `transaction.atomic()` para garantir consistência do Tenant base; admins podem ficar parcialmente criados se erro após essa fase (risco aceito).

## 9. Normalização de Módulos (`enabled_modules`)
Entrada aceita: lista Python, JSON, CSV simples, ou dict legado.
Pipeline de normalização:
1. Converte para lista.
2. Remove duplicatas preservando ordem da primeira ocorrência.
3. Ordena (comportamento atual para previsibilidade de logs) – pode ser revisitado.
4. Ajusta coerência com `portal_ativo`.

## 10. Administradores (Step 6)
Fonte de dados: JSON (`admins_json`) ou formato legado (campos individuais).
Para cada admin:
- Valida e-mail; ignora linhas totalmente vazias.
- Gera username incremental se conflito.
- Gera senha robusta se ausente/inválida (ou divergente de confirmação).
- Evita duplicação por `email` ou `user_id` na mesma execução.
- Garante associação a Role "Administrador" (cria se inexistente no Tenant).

## 11. Endereços
- Principal via `update_or_create` (tipo `PRINCIPAL`).
- Adicionais: substituição total (delete + recreate) – limite prático ~50.
- CEP normalizado: se 8 dígitos → formata `00000-000`.

## 12. Contatos & Redes Sociais
- Campos principais diretamente no Tenant.
- Adicionais: JSON (`contacts_json`) – replace completo.
- Redes sociais: preferencial JSON flexível; fallback em campos legados (`linkedin`, `instagram`, `facebook`).

## 13. Draft vs Dado Limpo
| Aspecto | Draft (Rascunho) | Dado Limpo |
|---------|------------------|------------|
| Origem | POST bruto | `form.cleaned_data` |
| Uso | Repreencher forms ao voltar | Persistência final |
| Armazenamento | Sessão (mescla incremental) | Sessão (estrutura consolidada) |
| Pode conter inválidos | Sim | Não |

## 14. Logging & Observabilidade
Níveis usados:
- info: eventos de fluxo (entrada/saída de step, finalização ok)
- debug: detalhes operacionais (normalizações, contagens)
- warning: entradas inconsistentes não bloqueantes (JSON malformado)
- error: falhas de integridade / exceções antes de abortar finish
Sugestão futura: flag `settings.WIZARD_DEBUG` para modular verbosidade.

### 14.1 Correlation ID Global do Wizard
- Cada requisição do Wizard recebe um `X-Wizard-Correlation-Id` gerado no `dispatch` da `TenantCreationWizardView`.
- O ID fica disponível em `request._wizard_cid` e é anexado a toda resposta HTTP da view (incluindo redirects).
- O `finish_wizard` reutiliza o mesmo ID para logs/metrics via `set_last_finish_correlation_id`.
- Objetivo: rastrear facilmente um fluxo de finalização específico entre cliente, logs e métricas sem alterar regras de negócio.

## 15. Tratamento de Erros & Transações
- `transaction.atomic()` protege criação/atualização do Tenant base e relacionamentos críticos iniciais.
- Parsing JSON falho gera warning e ignora bloco em vez de abortar.
- Falhas após criação de admins podem deixar usuários válidos sem relação perfeita adicional (aceito).

## 16. Segurança & Limites
- Limites tácitos (endereços adicionais ~50, admins ~50, contatos ~100). Centralizar futuramente em `wizard_limits.py`.
- Subdomínio validado antes (AJAX) e no finish (autoridade final).
- Sanitização leve (ex: CEP). Restante depende das validações de forms.

## 17. Riscos Aceitos
| Risco | Impacto | Justificativa |
|-------|---------|---------------|
| Navegação sem Step 1 real | Usuário chega adiante sem base | Liberdade de exploração; finish bloqueia inconsistências |
| Sessão volumosa | Mais bytes em backend | Baixo volume de uso simultâneo esperado |
| Replace total em listas | Perda acidental se draft incompleto | Simplicidade > diffs incrementais |
| Admins criados antes de erro final | Usuários "órfãos" | Frequência baixa + auditoria possível |
| Logs ruidosos em prod | Ruído operacional | Ajustável via configuração futura |

## 18. Melhorias Futuras (Não Implementadas)
1. Validação incremental por step (opt-in).
2. Hash por step para reprocessamento seletivo.
3. Sanitização e truncagem centralizada de strings longas.
4. Extração para serviços puros: `WizardStateService`, `TenantAssembler`.
5. Bulk create otimizado para admins quando possível.
6. Badge visual “Rascunho incompleto” se skeleton ativo.
7. Métricas: taxa sucesso/falha de finalização.
8. Flag para exigir Step 1 antes de steps posteriores.

## 19. Testes e Cobertura
Arquivos principais:
- `core/tests/test_views.py` (fluxos gerais do wizard)
- `core/tests/test_wizard_subdomain_edges.py` (edge cases de subdomínio)
- `core/tests/wizard_test_utils.py` (helpers reutilizáveis)
Cobertura validada:
- Obrigatoriedade e unicidade de subdomínio.
- Regex (comprimento, hífens inválidos, case normalizado).
- Reservados e duplicados case-insensitive.

## 20. Scripts Úteis
Executar somente testes de subdomínio:
```
pytest -q core/tests/test_wizard_subdomain_edges.py
```
Executar suíte completa:
```
pytest -q
```

## 21. Checklist Pré-Deploy
- [ ] Criar PJ básica com subdomínio válido + `portal_cliente` ativo.
- [ ] Criar PF sem admins e finalizar.
- [ ] Saltar para Step 5, voltar e preencher Step 1, finalizar.
- [ ] Tentar subdomínio duplicado em edição (permanece em Step 5).
- [ ] Admin com senha curta (gera automática conforme regra atual).
- [ ] Testar módulos: nenhum → adicionar → finalizar.
- [ ] JSON inválido (admins / socials) não quebra fluxo (gera warning).
- [ ] Simular perda de sessão entre Step 5 e 7 (refazer sem inconsistência residual).

## 22. Histórico de Alterações
| Data | Alteração | Autor | Código Modificado? |
|------|-----------|-------|--------------------|
| 2025-09-19 | Reescrita integral consolidada | Assistente | Não |
| 2025-09-19 | Versão anterior (auditoria adicionada ao fim) | Assistente | Não |
| 2025-09-19 | Auditoria e consolidação observabilidade (renumeração 23.x) | Assistente | Não |

---
Garantia: Documento reflete estado atual do código sem criar novas regras. Solicite “gerar refatoração X” para implementar melhorias específicas.

## 23. Notas de Implementação Avançadas
Esta seção adiciona detalhes operacionais e de observabilidade. Nenhuma nova regra de negócio é criada aqui.

### 23.1 Salvamento Parcial de Step (Edição)
- Método: `save_current_step_only` permite persistir apenas o step atual em modo edição.
- Uso: Botão/ação que envia `wizard_save_step` no POST.
- Escopo: Aplica transação isolada; não revalida integridade global.

### 23.2 Reaplicação de Subdomínio/Status
- Mesmo que `subdomain` e `status` não façam parte dos forms PJ/PF, `finish_wizard` reaplica valores capturados do Step 5 após `form.save()`.
- Objetivo: garantir coerência mesmo sem validação prévia daquele form durante navegação livre.

### 23.3 Captura Manual de Módulos (Step 5)
- Campo real de checkboxes: `enabled_modules` (sem prefixo) → não mapeado automaticamente pelo prefix `main` do form.
- Solução: captura manual em `process_step_data` unificando rascunho + limpos.

### 23.4 Ordem de Processamento de Relacionados
Sequência em `_process_wizard_related_data`: Endereços → Contatos → Configuração → Admins.
Motivo: dependências fracas (nenhuma ordem estrita necessária), mas mantida consistência de logging.

### 23.5 Step 4 (Documentos)
- Persistência real delegada para `documentos.services.consolidate_wizard_temp_to_documents` chamada ao final.
- Sessão mantém apenas placeholder vazio (`step_4.main = {}`) para manter coesão estrutural.

### 23.6 Retorno Específico ao Step 5
- Caso subdomínio duplicado seja detectado na finalização, o fluxo força `current_step=5` para correção direta.

### 23.7 Senha em Lote para Admins
- Campo opcional: `bulk_admin_password` → usado quando admins individuais não fornecem senha válida.
- Senhas individuais curtas (<8) ou divergentes de confirmação são descartadas e substituídas.

### 23.8 Wrapper `WizardContext`
- Introduzido como camada de conveniência (`core/services/wizard_context.py`).
- Não altera regras de negócio: apenas encapsula o dict de sessão e oferece helpers (`get_step`, `step_main`, `detect_tipo_pessoa`).
- Utilizado em `finish_wizard`, `validate_wizard_data_integrity` e `consolidate_wizard_data` para clareza interna.

### 23.9 Unificação de Parsing de Redes Sociais
- `_process_complete_contacts_data` agora usa `parse_socials_json` do service `wizard_normalizers`.
- Remove duplicação de lógica de iteração/validação antes espalhada no método.
- Fallback legado (campos individuais) preservado quando JSON vazio ou inválido.

### 23.10 Normalização de Módulos no Review (Step 7)
- A montagem de `enabled_modules_flat` no preview passou a delegar a `normalize_enabled_modules` (service) em vez de lógica manual inline.
- Benefícios: redução de divergências, menor chance de edge cases silenciosos (dicts legados, CSV, JSON híbrido).

### 23.11 Rebalanceamento de Logs
- Diversos `logger.info` de alta frequência (salvamentos intermediários, consolidações, criação de esqueleto) foram rebaixados para `debug`.
- Eventos de negócio mantidos em `info`: criação/atualização final, salvamento de Step 1 válido, resumo de admins, consolidação de documentos.
- Objetivo: diminuir ruído operacional sem perder fatos auditáveis.

### 23.12 Garantias Pós-Refatoração
- Nenhum campo removido ou renomeado.
- Fluxo de validação final intacto.
- Navegação livre permanece funcional (skeleton preservado).
- Services introduzidos são internos (não quebram templates / forms existentes).

### 23.13 Limites Centralizados
- Introduzido `core/services/wizard_limits.py` consolidando constantes: `MAX_ADDITIONAL_ADDRESSES=50`, `MAX_ADMINS=50`, `MAX_CONTACTS=100`, `MAX_SOCIALS=50`.
- Substituídos números mágicos no código para facilitar ajuste futuro sem alterar regras.

### 23.14 Flag de Debug
- `core/services/wizard_logging.py` expõe `is_wizard_debug_enabled()` lendo `settings.WIZARD_DEBUG` (por enquanto não ativa switch dinâmico, apenas preparada). 
- Possível evolução: condicionar logs debug a esta flag.

### 23.15 Métricas Internas
- `core/services/wizard_metrics.py` armazena contadores em memória (thread-safe) para: `finish_success`, `finish_subdomain_duplicate`, `finish_exception`.
- Integrado a `finish_wizard` de forma try/except silenciosa (sem impacto funcional se indisponível).

### 23.16 Testes Adicionais
- `test_wizard_context.py`: cobre `WizardContext.detect_tipo_pessoa` inclusive skeleton incompleto.
- `test_wizard_e2e.py`: fluxo completo simulando finalização com módulos, endereço, socials JSON, admin e verificação de métricas.

### 23.17 Atualização de Admin Existente
- Se user já existe (por `user_id` ou `email`): atualiza nome, telefone, ativo e cargo; evita duplicação.
- Role "Administrador" garantida via `get_or_create`.

### 23.18 Geração Determinística de Username
- Base: antes do `@` do e-mail ou campo explícito.
- De-duplicação incremental por sufixos numéricos preservando limite de 30 chars.

### 23.19 Redundância de Normalização de Redes Sociais
- Ocorre no momento de processar o form e novamente na consolidação final (camadas defensivas). Refatoração futura pode unificar.

### 23.20 Skeleton de Navegação Livre
- Define apenas `step_1.main.tipo_pessoa = 'PJ'` para permitir preview; não popula blocos `pj` ou `pf`.
- Validação final exige dados reais PF/PJ; skeleton isoladamente não permite finalizar.

### 23.21 Contatos e Redes Sociais
- Serialização de existentes para edição: `serialize_existing_contacts` / `serialize_existing_socials`.
- Replace total: evita merge complexo; risco de perda mitigado por navegação livre (usuário pode revisar antes do finish).

### 23.22 Riscos Técnicos Operacionais
- Race de subdomínio: validado apenas no finish – baixa probabilidade sem alta concorrência.
- Admins "órfãos": se exceção após criação de usuários (aceito como risco mínimo).
- Crescimento de sessão: mitigado pelo limite de listas e natureza temporária.

### 23.23 Importações Limpáveis (Pendentes até refatoração)
- `re`: não utilizado diretamente (regex migrado para validators).
- `traceback`: pode ser substituído por `logger.exception`.
- Tipagem duplicada com aliases pode ser simplificada.

### 23.24 Aderência ao README
- Todos os pontos acima reforçam implementação; nenhum altera regra descrita.

Fim das notas avançadas.

---

<!-- Bloco original 23.17–23.34 removido para evitar duplicação. Ver 23.25+ (Observabilidade Consolidada). -->

### 23.35 Gauges Prometheus (Sessões)
- Adicionados gauges opcionais (se `prometheus_client` disponível):
  - `wizard_active_sessions`
  - `wizard_abandoned_sessions`
- Atualizados em `register_active_session`, `unregister_active_session` e no `snapshot_metrics` (abandono detectado).
- Fallback silencioso quando Prometheus não instalado.

### 23.36 Histogramas por Outcome
- Além do histogram geral (`wizard_finish_latency_seconds`), criados histogramas separados:
  - `wizard_finish_latency_success_seconds`
  - `wizard_finish_latency_duplicate_seconds`
  - `wizard_finish_latency_exception_seconds`
- Evita labels dinâmicas para manter cardinalidade controlada.
- Campo novo `latency_by_outcome` no snapshot JSON.

### 23.37 Hook de Latência com Outcome
- `record_finish_latency(seconds, outcome)` agora tenta chamar `settings.WIZARD_LATENCY_SINK` com assinatura `(seconds, correlation_id, outcome)`.
- Retrocompatibilidade: se ocorrer `TypeError`, reexecuta com `(seconds, correlation_id)`.
- Outcome possível: `success|duplicate|exception`.

### 23.38 Correlation ID em Respostas
- Redirecionamentos finais (sucesso, erro e duplicidade) agora incluem header HTTP `X-Wizard-Correlation-Id`.
- Facilita correlacionar uma finalização no browser com logs/metrics sem depender do snapshot.

### 23.39 Tempo até Abandono (Heurístico)
- Armazenado timestamp inicial da sessão na primeira atividade (`_session_start`).
- Ao detectar abandono, calcula duração e armazena em `_abandon_durations` (janela rotacionada).
- Snapshot inclui bloco `time_to_abandon` com estatísticas: `count,p50,p90,p95,p99,max,avg`.
- Não há persistência histórica longa; apenas janela in-memory.

### 23.40 Estrutura do Snapshot (Atualizada)
```json
{
  "wizard_metrics": {
    "counters": {"finish_success": 3, "finish_subdomain_duplicate": 1, "finish_exception": 0},
    "latency": {"count": 3, "p50": 0.12, "p90": 0.20, "p95": 0.20, "p99": 0.20, "max": 0.20},
    "latency_by_outcome": {"success": {"count": 2, "p50": 0.10}, "duplicate": {"count": 1, "p50": 0.20}},
    "last_errors": [],
    "active_sessions": 0,
    "abandoned_sessions": 2,
    "time_to_abandon": {"count": 2, "p50": 120.0, "avg": 118.0},
    "last_finish_correlation_id": "a1b2c3d4e5f6",
    "prometheus_enabled": true
  }
}
```

### 23.41 Settings Configuráveis
- Novos parâmetros (opcionais; fallback para defaults hardcoded):
  - `WIZARD_MAX_LATENCIES` (janela rotacionada de latência – padrão 200)
  - `WIZARD_MAX_ERRORS` (tamanho de `_last_errors` – padrão 25)
  - `WIZARD_MAX_ABANDON_LATENCIES` (janela de `time_to_abandon` – padrão 200)
  - `WIZARD_ABANDON_THRESHOLD_SECONDS` (já existente; documentação reafirmada)

### 23.42 Backward Compatibility
- Campos antigos preservados.
- Novos campos são opcionais no consumo; não alteram semântica de finalização.
- Hook antigo com assinatura `(seconds, correlation_id)` continua funcional.

### 23.43 Testes Adicionados
- Cobertura para:
  - `latency_by_outcome`
  - Hook com outcome retrocompatível
  - `time_to_abandon` (mock de tempo)
  - Abandono sem duplicar contagem em chamadas subsequentes.

### 23.44 Roadmap Pós-Expansão
1. Persistir série temporal externa (ex: exporter dedicado) para `time_to_abandon`.
2. Expor métricas críticas via painel administrativo simplificado.
3. Alerta (logger warning) se p95 de latência > threshold configurável.
4. Limpeza manual de estado via management command (`wizard_metrics_reset`).

---
Nenhuma regra de negócio foi alterada; todas as mudanças permanecem restritas à observabilidade e inspeção operativa.

### 23.45 Backlog Colaborativo (Sessão de Trabalho)
Espaço vivo para registrar, priorizar e acompanhar sugestões antes de virarem itens formais de roadmap. Itens daqui podem ser consolidados em subseções futuras ou descartados após avaliação.

Formato sugerido de atualização:
| ID | Categoria | Descrição Breve | Valor Esperado | Complexidade (baixa/média/alta) | Status | Observações |
|----|-----------|-----------------|----------------|----------------------------------|--------|-------------|
| B1 | Métricas | `wizard_metrics_reset` management command | Facilitar troubleshooting e testes limpos | baixa | proposto | Resetar estruturas in-memory sob lock |
| B2 | Alertas | Warn se p95 latência > X ms consecutivos N snapshots | Detecção precoce de regressão | média | proposto | Threshold via setting `WIZARD_LATENCY_WARN_THRESHOLD` |
| B3 | Export | Exportador periódico para TSDB (Influx/OTel) | Retenção histórica longa | alta | em análise | Usar thread/lightweight scheduler opcional |
| B4 | UI | Mini dashboard staff no Django Admin | Observabilidade rápida sem curl | média | proposto | Reutilizar `snapshot_metrics()` serializado |
| B5 | Funil | Métrica "tempo até primeiro step real" | Medir atrito inicial | média | proposto | Requer timestamp de criação inicial separado |
| B6 | Qualidade | Detectar "flapping" de subdomínio (trocas repetidas) | Sinal de abuso ou indecisão | média | proposto | Contador incremental por sessão |
| B7 | Segurança | Limitar tentativas de subdomínio por IP por hora | Evitar enumeração massiva | média | proposto | Integrar com cache rate limit existente |
| B8 | DevEx | Fixture de teste para snapshot sintético | Acelerar testes focados | baixa | proposto | Gera estruturas internas pré-preenchidas |

Legenda rápida de Status: `proposto` (não analisado), `em análise` (em refinamento), `planejado` (aprovado para execução), `em execução`, `concluído`, `descartado`.

Procedimento de Evolução:
1. Adicionar linha (Status=proposto).
2. Discutir viabilidade → mover para `em análise`.
3. Definir aceitação → atualizar Status para `planejado` e criar tarefa interna.
4. Após merge de implementação → marcar `concluído` e (opcional) mover resumo para subseção formal.

Critérios de Priorização (heurístico):
- Alto impacto + baixa complexidade → priorizar.
- Dependência externa (TSDB, dashboards complexos) → postergar até estabilizar métricas básicas.
- Itens de segurança e potencial abuso (`B7`) ganham prioridade se tráfego aumentar.

Este bloco pode ser limpo periodicamente removendo itens `concluído` já documentados em seções permanentes.




