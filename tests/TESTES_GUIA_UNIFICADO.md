<!--
DOCUMENTO ÚNICO CANÔNICO – NÃO FRAGMENTAR.
Todos os conteúdos anteriores (README_TESTS_REORGANIZACAO.md, TESTES_ORGANIZACAO.md, lista_de_testes.md) foram incorporados.
-->

# Guia Unificado Completo da Suíte de Testes

## Índice
1. Objetivos Estratégicos
2. Filosofia & Escopo
3. Ambiente / Runner (`pytest.ini` completo)
4. Estrutura e Taxonomia (Migração Opção A + Tabela de Progresso)
5. Regras Gerais (Higiene & Criação)
6. Nomeação (Arquivos & Funções)
7. Estilos Aceitos / Quando usar Classes
8. Fixtures Globais & Critérios de Promoção
9. Helpers Multi‑Tenant (Checklist Operacional)
10. Markers Oficiais
11. Permission Resolver (Arquitetura de Testes)
12. Execução de Subconjuntos – Receitas Comuns
13. Cobertura (Metas, Geração, Artefatos)
14. Boas Práticas de Conteúdo & Performance
15. Anti‑Padrões (Tabela de Substituição)
16. Política de Legacy, Aliases e Deprecações
17. Roadmap Técnico da Suíte
18. Checklist PR que Adiciona/Modifica Testes
19. Logging Service – Escopo de Validação
20. Inventário Atual de Testes (Instantâneo Integrado)
21. Geração Dinâmica do Inventário / Automação Futuras
22. Rotinas de Higiene & Fails Rápidos
23. Scripts Auxiliares & Execuções Locais
24. Dicas para Diagnóstico de Falhas Intermitentes
25. Estratégia de Evolução de Cobertura Incremental
26. FAQ Curta
27. Histórico de Migração

---
## 1. Objetivos Estratégicos
1. Descoberta única e determinística (`pytest -q`).
2. Domínios separados por intenção (ex: `core/subdomain`, `security/login`).
3. Eliminar drift: um único documento vivo.
4. Minimizar tempo de decisão para criar novo teste (checklist explícito).
5. Facilitar refactors transversais (permission resolver, 2FA, wizard multi‑tenant) sem caça a arquivos dispersos.

## 2. Filosofia & Escopo
- Testes servem como documentação executável das regras de negócio críticas.
- Latência: preferir granularidade média (evitar testes mega‑integração que validam 10 conceitos ao mesmo tempo).
- Falhas devem apontar causa (assertions específicos, mensagens ricas).

## 3. Ambiente / Runner
Conteúdo efetivo de `pytest.ini` (resumido):
```
[pytest]
DJANGO_SETTINGS_MODULE = pandora_erp.settings
python_files = tests.py test_*.py *_tests.py
addopts = --cov=core --cov=user_management --cov=shared --cov-report=term-missing
testpaths = tests
markers =
    slow: testes lentos (>1s)
    permission: resolver de permissões / precedência
    security: segurança geral (login, headers)
    login: autenticação primária
    twofa: segunda etapa 2FA
    hygiene: verificações estruturais do repositório
    repo_hygiene: (LEGADO – será removido após unificação)
```

## 4. Estrutura e Taxonomia (Migração Opção A)
Tabela de progresso da migração original (referência histórica, concluída):
| Domínio | Origem Antiga | Novo Destino | Status |
|---------|---------------|--------------|--------|
| Permission Resolver | shared/tests/*.py | tests/shared/permission_resolver/ | OK |
| Core Wizard / Tenant | core/tests/test_wizard_*.py | tests/core/tenant_wizard/ | OK |
| Core Geral (latency, menu, utils) | core/tests/*.py | tests/core/* (subdirs) | OK |
| Chatbot & Home | core/tests/test_smoke_chatbot_home.py | tests/core/chatbot/ | OK |
| User Management | user_management/tests/*.py | tests/user_management/ | OK |
| Segurança (login + 2FA) | já em tests/security/* | Mantido | OK |
| Estoque | tests/estoque/ | Mantido | OK |
| Prontuários | tests/prontuarios/ | Mantido | OK |

Diretórios ativos principais (exemplos):
| Diretório | Intenção |
|-----------|----------|
| tests/core/subdomain | Disponibilidade, normalização & concorrência de subdomínios |
| tests/core/tenant_wizard | Fluxos e arestas do wizard multi‑tenant |
| tests/core/authorization | Middleware / autorização / precedência cross‑módulo |
| tests/core/utils | Utilidades isoladas (formatting, inatividade) |
| tests/security/login | Login, rate limit, headers de bloqueio |
| tests/security/twofa | Fluxos completos e limites 2FA |
| tests/shared/permission_resolver | Todas as variantes do resolver de permissões |
| tests/user_management | Auditoria, limpeza, sessões, logging extra |
| tests/estoque | Domínio de estoque (operações, KPIs, comandos) |
| tests/prontuarios | APIs clínicas, slots, mídia |

## 5. Regras Gerais (Higiene & Criação)
1. PROIBIDO criar `*/tests` dentro de apps (usar somente árvore raiz `tests/`).
2. Tocou teste legado? Mover antes de alterar.
3. Imports sempre absolutos (`from core.models import Tenant`).
4. Cada arquivo deve focar um conceito primário; se crescer > ~400 linhas, avaliar fatiar.
5. Evitar duplicação de nomes de arquivo em domínios diferentes (vamos automatizar verificação – ver Roadmap).

## 6. Nomeação
Arquivo: `test_<contexto>_<foco>.py`.
Função: `test_<condicao>_<resultado>`.
Preferir intenção sobre implementação interna (ex: `test_login_rate_limit_blocks_after_threshold`).

## 7. Estilos Aceitos
- Funções pytest simples (preferencial).
- Classes só para agrupar cenário parametrizado comum OU usar `django.test.TestCase` quando `setUpTestData` reduz custo.
- Evitar heranças múltiplas.

## 8. Fixtures Globais
Critérios de promoção: usada em ≥2 domínios + reduz boilerplate significativo.
Exemplos típicos: `tenant_with_all_modules`, `auto_enable_modules` (autouse), helpers multi‑tenant.
Não promover fixação de dados gigantes se somente 1 teste consome.

## 9. Helpers Multi‑Tenant – Checklist
Antes de chamar endpoint multi‑tenant:
1. `client.force_login(user)` executado?
2. Sessão tem `tenant_id` ou fluxo que o atribui? (fixtures cuidam se usar helper)
3. Módulos habilitados? (fixture autouse; senão usar helper de bootstrap)
4. `reverse()` sempre com namespace.
5. Validar subdomínio normalizado se participar de decisão.

## 10. Markers Oficiais
| Marker | Uso |
|--------|-----|
| slow | Cenários >1s ou IO considerável |
| permission | Resolver de permissões, precedência/caching |
| security | Cabeçalhos, enforcement de segurança geral |
| login | Foco em autenticação primária |
| twofa | Fluxos / limites 2FA |
| hygiene | Estrutura, proibição de diretórios ou arquivos ilegais |
| repo_hygiene | (LEGADO) será removido – migrar para `hygiene` |

## 11. Permission Resolver
Abrange precedência (deny vs allow), cache versionado, TTL, trace, expirations por recurso, métricas. Testes de performance rodados somente opt‑in (`PANDORA_PERF=1`). Não mockar camada de persistência nas rotas críticas de decisão.

## 12. Execução de Subconjuntos
```
pytest -m "not slow" -q
pytest tests/core/subdomain -q
pytest -k permission_resolver -q
pytest -m permission -q
pytest tests/security/login/test_login_rate_limit.py -q
pytest tests/shared/permission_resolver/test_permission_resolver_pipeline.py -q
```

## 13. Cobertura
Metas atuais (soft): core 80%, user_management 85%, shared 80%.
Roadmap: global ≥90% pós estabilização 2FA avançado + resolver.
Gerar HTML local:
```
pytest --cov=core --cov=user_management --cov=shared --cov-report=html -q
```
Artefatos esperados: `htmlcov/index.html`.

## 14. Boas Práticas
1. Independente de ordem.
2. Criar só dados necessários.
3. Assertions específicos (status, campo, fragmento semântico) – evitar apenas `assert 200`.
4. Usar monkeypatch / clock fake em vez de `time.sleep`.
5. Após mutação ORM: `obj.refresh_from_db()`.
6. Não logar segredos.
7. Parametrizar quando variações são puramente dados.

## 15. Anti‑Padrões
| Anti‑Padrão | Substituir Por | Motivo |
|-------------|----------------|--------|
| `print` debug | `-vv` / asserts claros | Ruído |
| `time.sleep(5)` | monkeypatch / espera lógica | Lento / frágil |
| Reutilizar instâncias sem refresh | `refresh_from_db()` | Estado stale |
| Encadear testes dependentes | Independentes | Fragilidade |

## 16. Legacy & Deprecações
Aliases (ex: `tenant_subdomain_check`) mantidos somente até todos os testes usarem rota canônica (`check_subdomain`). Auditoria semestral remove alias vencido. Diretório `legacy/` deve encolher até remoção total.

## 17. Roadmap Técnico
- Remover marker `repo_hygiene` -> unificar em `hygiene`.
- Script inventário dinâmico.
- Verificação automática de duplicidade de basename.
- Aumentar escopo de cobertura incremental baseada em diffs.
- Adicionar testes de latência leve para fluxos login + 2FA.

## 18. Checklist PR com Testes
- [ ] Nome de arquivo e função seguem convenção
- [ ] Sem dependência de ordem / dados isolados
- [ ] Assertions focam comportamento, não implementação interna acidental
- [ ] Marker aplicado (se slow / permission / security / twofa / login)
- [ ] Cobertura de novo caminho de código
- [ ] Sem prints / sleeps desnecessários
- [ ] Não criou pasta `*/tests` em app

## 19. Logging Service – Escopo
Validar: fallback IP (`0.0.0.0`), user_agent (`N/A`), truncamentos (acao<=100, modulo<=50, descricao<=255), ignorar `user=None` sem erro. Extensões (JSON extra) só entram após implementação real.

## 20. Inventário Atual de Testes (Snapshot)
Lista integrada (anteriormente `lista_de_testes.md`). Mantida para visibilidade rápida; geração futura será automática.
```
[INICIO INVENTARIO]
<COLUNAS> Caminho Relativo | Arquivo | Descrição
user_management/tests/test_portal_module_whitelist.py | test_portal_module_whitelist.py | User Management – whitelist de módulos do portal
user_management/tests/test_logging_service_ip_fallback.py | test_logging_service_ip_fallback.py | User Management – fallback de IP no serviço de logging
user_management/tests/__init__.py | __init__.py | Pacote de testes de user_management
user_management/tests/test_services_logging_profile.py | test_services_logging_profile.py | User Management – serviços de logging de perfil
shared/tests/test_permission_resolver_expiration_resource.py | test_permission_resolver_expiration_resource.py | Shared – resolver expiração recurso
shared/tests/test_permission_resolver_deny_global_vs_allow_scoped.py | test_permission_resolver_deny_global_vs_allow_scoped.py | Shared – deny global vs allow scoped
shared/tests/test_permission_resolver_decision_api.py | test_permission_resolver_decision_api.py | Shared – decisão API resolver
shared/tests/test_permission_resolver_cache_version.py | test_permission_resolver_cache_version.py | Shared – versão cache
shared/tests/test_permission_resolver_basic_user.py | test_permission_resolver_basic_user.py | Shared – usuário básico
shared/tests/test_permission_resolver_advanced.py | test_permission_resolver_advanced.py | Shared – cenários avançados
shared/tests/test_permission_resolver_additional.py | test_permission_resolver_additional.py | Shared – casos adicionais
shared/tests/test_ui_permissions_module_key_prod_serv.py | test_ui_permissions_module_key_prod_serv.py | Shared – chaves módulo prod/serv
shared/tests/test_ui_permissions_module_key.py | test_ui_permissions_module_key.py | Shared – chaves módulo UI
shared/tests/test_shared_permission_resolver.py | test_shared_permission_resolver.py | Shared – geral resolver
shared/tests/test_permission_resolver_precedence_variants.py | test_permission_resolver_precedence_variants.py | Shared – variantes precedência
shared/tests/test_permission_resolver_pipeline_cache.py | test_permission_resolver_pipeline_cache.py | Shared – pipeline cache
shared/tests/test_permission_resolver_performance.py | test_permission_resolver_performance.py | Shared – performance (opt‑in)
tests/test_repo_higiene.py | test_repo_higiene.py | Higiene estrutura
tests/test_docs_hygiene.py | test_docs_hygiene.py | Higiene docs
tests/helpers_multi_tenant.py | helpers_multi_tenant.py | Helpers multi‑tenant
tests/shared/test_permission_resolver_warmup.py | test_permission_resolver_warmup.py | Warmup resolver
tests/shared/test_permission_resolver_pipeline.py | test_permission_resolver_pipeline.py | Pipeline resolver
tests/shared/test_permission_resolver_explain.py | test_permission_resolver_explain.py | Explain resolver
tests/shared/test_permission_resolver_cache_ttl_metric.py | test_permission_resolver_cache_ttl_metric.py | Métricas TTL
tests/shared/test_permission_resolver_cache_hit.py | test_permission_resolver_cache_hit.py | Cache hits
tests/shared/test_permissions_servicos_metrics.py | test_permissions_servicos_metrics.py | Métricas serviços
tests/shared/permissions/test_permission_resolver_role_admin_flag.py | test_permission_resolver_role_admin_flag.py | Flag admin
tests/shared/permissions/test_permission_resolver_personalizadas.py | test_permission_resolver_personalizadas.py | Permissões personalizadas
tests/shared/permissions/test_permission_resolver_missing_membership.py | test_permission_resolver_missing_membership.py | Falta membership
tests/shared/permissions/test_permission_resolver_implicit.py | test_permission_resolver_implicit.py | Permissões implícitas
tests/shared/permissions/test_permission_resolver_cache_edgecases.py | test_permission_resolver_cache_edgecases.py | Edge cache
tests/shared/permissions/test_permission_resolver_cache_and_precedence.py | test_permission_resolver_cache_and_precedence.py | Cache + precedência
tests/shared/permissions/test_permission_resolver_cache.py | test_permission_resolver_cache.py | Cache resolver
tests/shared/test_permissions_servicos.py | test_permissions_servicos.py | Permissões por serviço
tests/prontuarios/helpers.py | helpers.py | Prontuários helpers
tests/prontuarios/test_foto_evolucao_api.py | test_foto_evolucao_api.py | Foto evolução API
tests/prontuarios/test_api_scopes.py | test_api_scopes.py | Escopos API
tests/prontuarios/test_video_poster_task.py | test_video_poster_task.py | Poster vídeo task
tests/prontuarios/test_tasks_media.py | test_tasks_media.py | Tarefas mídia
tests/prontuarios/test_slots_none.py | test_slots_none.py | Slots None
tests/prontuarios/test_slots_date_filter.py | test_slots_date_filter.py | Filtro data slots
tests/prontuarios/test_select2_pagination.py | test_select2_pagination.py | Paginação Select2
tests/prontuarios/test_select2_endpoints.py | test_select2_endpoints.py | Endpoints Select2
tests/prontuarios/test_quick_create_endpoints.py | test_quick_create_endpoints.py | Criação rápida
tests/security/test_security_headers.py | test_security_headers.py | Cabeçalhos segurança
tests/repo/test_sitecustomize_optional.py | test_sitecustomize_optional.py | sitecustomize opcional
tests/security/twofa/test_twofa_regenerate.py | test_twofa_regenerate.py | Regeneração 2FA
tests/security/twofa/test_twofa_metrics_reset_and_ipblocks.py | test_twofa_metrics_reset_and_ipblocks.py | Reset métricas/IP blocks
tests/security/twofa/test_twofa_metrics_json.py | test_twofa_metrics_json.py | Métricas JSON
tests/security/twofa/test_twofa_lockout.py | test_twofa_lockout.py | Lockout
tests/security/twofa/test_twofa_global_ip_rate_limit.py | test_twofa_global_ip_rate_limit.py | Rate global IP
tests/security/twofa/test_twofa_global_ip_limit_new.py | test_twofa_global_ip_limit_new.py | Novo limite IP
tests/security/twofa/test_twofa_flow.py | test_twofa_flow.py | Fluxo completo
tests/security/twofa/test_twofa_extra.py | test_twofa_extra.py | Extras 2FA
tests/security/twofa/test_twofa_enforcement.py | test_twofa_enforcement.py | Enforcement 2FA
tests/security/twofa/test_twofa_crypto_fallback_and_cachefail.py | test_twofa_crypto_fallback_and_cachefail.py | Fallback crypto / cachefail
tests/security/twofa/test_twofa_crypto_and_rate.py | test_twofa_crypto_and_rate.py | Crypto + rate
tests/security/twofa/test_twofa_core.py | test_twofa_core.py | Núcleo 2FA
tests/security/twofa/test_twofa_commands.py | test_twofa_commands.py | Comandos 2FA
tests/security/twofa/test_sessions_2fa.py | test_sessions_2fa.py | Sessões 2FA
tests/security/login/test_auth_backend.py | test_auth_backend.py | Backend auth
tests/security/login/test_login_threshold_settings.py | test_login_threshold_settings.py | Threshold login
tests/security/login/test_login_rate_limit.py | test_login_rate_limit.py | Rate limit login
tests/security/login/test_login_block_bloqueio.py | test_login_block_bloqueio.py | Bloqueios login
tests/security/login/test_logging_service_ip_fallback.py | test_logging_service_ip_fallback.py | Fallback IP logging
tests/security/login/test_auth_blocking.py | test_auth_blocking.py | Auth blocking
tests/estoque/test_views_itens.py | test_views_itens.py | Views itens
tests/estoque/test_picking_reservas_descartes.py | test_picking_reservas_descartes.py | Picking / reservas / descartes
tests/estoque/test_perdas_aprovacao_anexo.py | test_perdas_aprovacao_anexo.py | Perdas / anexos
tests/estoque/test_movimentos_lote_serie.py | test_movimentos_lote_serie.py | Movimentos lote/série
tests/estoque/test_legacy_unit.py | test_legacy_unit.py | Unidade legacy
tests/estoque/test_fifo_bom_permissoes.py | test_fifo_bom_permissoes.py | FIFO/BOM permissões
tests/estoque/test_api_kpis.py | test_api_kpis.py | KPIs API
tests/estoque/test_api_basics.py | test_api_basics.py | API básica
tests/estoque/helpers.py | helpers.py | Helpers estoque
tests/user_management/test_twofa_service.py | test_twofa_service.py | Serviço 2FA
tests/user_management/test_twofa_reencrypt_command.py | test_twofa_reencrypt_command.py | Reencrypt comando
tests/user_management/test_twofa_rate_limits_edge.py | test_twofa_rate_limits_edge.py | Bordas rate 2FA
tests/user_management/test_twofa_basic.py | test_twofa_basic.py | 2FA básico
tests/user_management/test_prune_expired_permissions.py | test_prune_expired_permissions.py | Prune permissões expiradas
tests/user_management/test_logging_extra_json.py | test_logging_extra_json.py | Logging extra JSON
tests/user_management/test_audit_orphan_permissions.py | test_audit_orphan_permissions.py | Auditoria permissões órfãs
tests/user_management/sync/test_sync_status.py | test_sync_status.py | Status sync
tests/user_management/sync/test_sync_profiles_command.py | test_sync_profiles_command.py | Sync perfis comando
tests/user_management/sync/test_reverse_sync.py | test_reverse_sync.py | Sync reverso
tests/user_management/sync/test_cleanup_sessions_logs_command.py | test_cleanup_sessions_logs_command.py | Cleanup sessões/logs
tests/user_management/tasks/test_tasks_wrappers.py | test_tasks_wrappers.py | Wrappers tasks
tests/user_management/sessions/test_lockout_expiration.py | test_lockout_expiration.py | Expiração lockout
tests/servicos/test_servico_clinico_form.py | test_servico_clinico_form.py | Form serviço clínico
tests/agenda/test_agenda_evento_tipo_cleanup.py | test_agenda_evento_tipo_cleanup.py | Limpeza tipo evento
tests/core/utils/test_utils_and_inactivity.py | test_utils_and_inactivity.py | Utils / inatividade
tests/core/utils/test_utils_formatting_json.py | test_utils_formatting_json.py | Formatting JSON
tests/core/subdomain/test_tenant_subdomain_concurrency.py | test_tenant_subdomain_concurrency.py | Concorrência subdomínio
tests/core/subdomain/test_tenant_auto_select.py | test_tenant_auto_select.py | Auto select tenant
tests/core/subdomain/test_subdomain_constants_sync.py | test_subdomain_constants_sync.py | Sync constantes
tests/core/subdomain/test_subdomain_ajax.py | test_subdomain_ajax.py | AJAX subdomínio
tests/core/subdomain/test_no_legacy_tenant_views.py | test_no_legacy_tenant_views.py | Sem legacy views
tests/core/dashboard/test_dashboard_widgets_smoke.py | test_dashboard_widgets_smoke.py | Smoke widgets
tests/core/departments/test_departments_api.py | test_departments_api.py | API departamentos
tests/core/enabled_modules/test_enabled_modules_normalization.py | test_enabled_modules_normalization.py | Normalização módulos
tests/core/latency/test_latency_middleware.py | test_latency_middleware.py | Middleware latência
tests/core/menu_middleware/test_views.py | test_views.py | Views wizard fluxo
tests/core/menu_middleware/test_subdomain_constants_sync.py | test_subdomain_constants_sync.py | Constantes subdomínio (menu)
tests/core/menu_middleware/test_subdomain_ajax.py | test_subdomain_ajax.py | AJAX subdomínio (menu)
tests/core/menu_middleware/test_no_legacy_tenant_views.py | test_no_legacy_tenant_views.py | Sem legacy (menu)
tests/core/menu_middleware/test_no_legacy_tenant_form.py | test_no_legacy_tenant_form.py | Form sem legacy
tests/core/menu_middleware/test_module_diagnostics_endpoint.py | test_module_diagnostics_endpoint.py | Diagnostics módulo
tests/core/menu_middleware/test_menu_integration.py | test_menu_integration.py | Integração menu
tests/core/menu_middleware/test_core_redirects.py | test_core_redirects.py | Redirects core
tests/core/tenant_wizard/test_wizard_multi_contacts.py | test_wizard_multi_contacts.py | Múltiplos contatos
tests/core/tenant_wizard/test_wizard_snapshot.py | test_wizard_snapshot.py | Snapshot wizard
tests/core/tenant_wizard/test_wizard_multi_admin.py | test_wizard_multi_admin.py | Múltiplos admins
tests/core/tenant_wizard/test_wizard_update_flow.py | test_wizard_update_flow.py | Update flow
tests/core/tenant_wizard/test_wizard_subdomain_edges.py | test_wizard_subdomain_edges.py | Arestas subdomínio
tests/core/tenant_wizard/test_wizard_snapshot_edit.py | test_wizard_snapshot_edit.py | Edit snapshot
tests/core/tenant_wizard/test_wizard_admin_edit.py | test_wizard_admin_edit.py | Admin edit
tests/core/tenant_wizard/test_tenant_subdomain_concurrency.py | test_tenant_subdomain_concurrency.py | Concorrência subdomínio wizard
tests/core/tenant_wizard/test_tenant_auto_select.py | test_tenant_auto_select.py | Auto select tenant wizard
tests/core/tenant_wizard/test_tenantuser_default_role.py | test_tenantuser_default_role.py | Papel default tenantuser
tests/core/tenant_wizard/test_multitenancy.py | test_multitenancy.py | Multitenancy
tests/core/authorization/test_permission_cache_inspect.py | test_permission_cache_inspect.py | Cache inspect
tests/core/authorization/test_portal_whitelist.py | test_portal_whitelist.py | Portal whitelist
tests/core/authorization/test_permission_resolver_extended.py | test_permission_resolver_extended.py | Resolver extended
tests/core/authorization/test_permission_resolver_errors.py | test_permission_resolver_errors.py | Errors resolver
tests/core/authorization/test_module_deny_metrics_coexist.py | test_module_deny_metrics_coexist.py | Métricas deny coexist
tests/core/authorization/test_module_deny_403_headers.py | test_module_deny_403_headers.py | Headers 403
tests/core/authorization/test_middleware_unmapped_path.py | test_middleware_unmapped_path.py | Path não mapeado
tests/core/authorization/test_authorization_strict.py | test_authorization_strict.py | Strict mode
tests/core/authorization/test_authorization_logging.py | test_authorization_logging.py | Logging autorização
tests/core/authorization/test_authorization.py | test_authorization.py | Autorização básica
tests/core/management/test_metrics_dump_command.py | test_metrics_dump_command.py | Dump métricas
tests/core/management/test_management_commands_clear_system_cache.py | test_management_commands_clear_system_cache.py | Clear system cache
tests/core/management/test_management_commands_audit_multitenant.py | test_management_commands_audit_multitenant.py | Audit multitenant
tests/core/management/test_management_commands_audit_enabled_modules.py | test_management_commands_audit_enabled_modules.py | Audit módulos habilitados
tests/core/management/test_management_commands_audit_auth_limit_and_reset.py | test_management_commands_audit_auth_limit_and_reset.py | Audit auth limit/reset
tests/core/management/test_management_commands_audit_auth.py | test_management_commands_audit_auth.py | Audit auth
tests/core/legacy/test_urls.py | test_urls.py | Legacy URLs
tests/core/legacy/test_models.py | test_models.py | Legacy modelos
tests/core/legacy/test_legacy_core_suite.py | test_legacy_core_suite.py | Legacy suite
tests/core/legacy/test_cargo_normalization.py | test_cargo_normalization.py | Cargo normalization
tests/core/legacy/test_api.py | test_api.py | Legacy API
[FIM INVENTARIO]
```

## 21. Inventário Dinâmico Futuro
Planejado script Python para gerar snapshot substituindo bloco estático (mantido por ora para onboarding rápido).

## 22. Rotinas de Higiene
Arquivos como `test_repo_higiene.py` e `test_docs_hygiene.py` falham build se:
- Aparecer diretório `*/tests` interno.
- Documentos fragmentados forem recriados.
Próximo passo: detectar basenames duplicados automaticamente.

## 23. Scripts Auxiliares
| Script | Função |
|--------|--------|
| run_tests.bat | Execução rápida local (subset default) |
| run_fast.bat | Execução enxuta sem cobertura pesada |
| run_audit_locmem_check.py | Auditoria (futuro / placeholder) |

## 24. Diagnóstico de Flakes
1. Repetir teste isolado 5x: `pytest path::test_func -q -k nome`.
2. Ativar verbose logging se disponível (variável de ambiente dedicada quando implementada).
3. Verificar dependência em ordem (state leakage) – fixture escopo indevido.

## 25. Evolução de Cobertura
Aplicar estratégia de incremento: PR que reduz cobertura crítica exige justificativa ou novos testes. Quando todos os domínios estáveis atingirem meta soft, elevar threshold global.

## 26. FAQ (Curta)
Q: Posso criar um novo marker? A: Abrir PR primeiro – evitar poluição.
Q: Teste super lento imprescindível? A: Marcar `slow` e considerar cenário reduzido.
Q: Posso usar assert genérico? A: Só se falha já for autoexplicativa; preferir mensagem clara.

## 27. Histórico de Migração
Migração “Opção A” concluída em 2025-09 centralizando todos os testes sob `tests/`. Documentos anteriores consolidados neste arquivo único.

---
Documento canônico: qualquer mudança em padrões DEVE ocorrer aqui.
