# Lista de Testes do Projeto

Este documento lista os arquivos de teste existentes no repositório, com caminho relativo, nome do arquivo e uma breve descrição inferida a partir do diretório e do nome do arquivo.

Observações:
- As descrições são concisas e inferidas de forma conservadora; refine conforme necessário.
- Colunas apresentadas em bloco monoespaçado com separadores para facilitar a leitura.

```
Caminho Relativo                                                                                          | Arquivo                                       | Descrição
----------------------------------------------------------------------------------------------------------|-----------------------------------------------|--------------------------------------------------------------------------------------
user_management/tests/test_portal_module_whitelist.py                                                     | test_portal_module_whitelist.py               | User Management – whitelist de módulos do portal
user_management/tests/test_logging_service_ip_fallback.py                                                 | test_logging_service_ip_fallback.py           | User Management – fallback de IP no serviço de logging
user_management/tests/__init__.py                                                                         | __init__.py                                   | Pacote de testes de user_management
user_management/tests/test_services_logging_profile.py                                                    | test_services_logging_profile.py              | User Management – serviços de logging de perfil
shared/tests/test_permission_resolver_expiration_resource.py                                              | test_permission_resolver_expiration_resource.py| Shared – resolver de permissões: expiração por recurso
shared/tests/test_permission_resolver_deny_global_vs_allow_scoped.py                                      | test_permission_resolver_deny_global_vs_allow_scoped.py | Shared – resolver de permissões: negação global vs escopo
shared/tests/test_permission_resolver_decision_api.py                                                     | test_permission_resolver_decision_api.py      | Shared – API de decisão do resolver de permissões
shared/tests/test_permission_resolver_cache_version.py                                                    | test_permission_resolver_cache_version.py     | Shared – versão de cache do resolver de permissões
shared/tests/test_permission_resolver_basic_user.py                                                       | test_permission_resolver_basic_user.py        | Shared – resolver de permissões para usuário básico
shared/tests/test_permission_resolver_advanced.py                                                         | test_permission_resolver_advanced.py          | Shared – cenários avançados do resolver de permissões
shared/tests/test_permission_resolver_additional.py                                                       | test_permission_resolver_additional.py        | Shared – casos adicionais do resolver de permissões
shared/tests/test_ui_permissions_module_key_prod_serv.py                                                  | test_ui_permissions_module_key_prod_serv.py   | Shared – chaves de módulo de UI (produção/serviço)
shared/tests/test_ui_permissions_module_key.py                                                            | test_ui_permissions_module_key.py             | Shared – chaves de módulo de UI
shared/tests/test_shared_permission_resolver.py                                                           | test_shared_permission_resolver.py            | Shared – testes gerais do resolver de permissões
shared/tests/test_permission_resolver_precedence_variants.py                                              | test_permission_resolver_precedence_variants.py| Shared – variantes de precedência no resolver
shared/tests/test_permission_resolver_pipeline_cache.py                                                   | test_permission_resolver_pipeline_cache.py    | Shared – pipeline do resolver e cache
shared/tests/test_permission_resolver_performance.py                                                      | test_permission_resolver_performance.py       | Shared – performance do resolver de permissões

tests/__init__.py                                                                                         | __init__.py                                   | Inicialização da suíte raiz de testes
tests/test_repo_higiene.py                                                                                | test_repo_higiene.py                          | Higiene do repositório (estrutura e padrões)
tests/test_docs_hygiene.py                                                                                | test_docs_hygiene.py                          | Higiene de documentação

# Auxiliares multi-tenant e permissões (raiz tests/shared e helpers)

tests/helpers_multi_tenant.py                                                                             | helpers_multi_tenant.py                       | Utilitários de teste para multi-tenant
tests/shared/test_permission_resolver_warmup.py                                                           | test_permission_resolver_warmup.py            | Shared – warmup do resolver de permissões
tests/shared/test_permission_resolver_pipeline.py                                                         | test_permission_resolver_pipeline.py          | Shared – pipeline do resolver de permissões
tests/shared/test_permission_resolver_explain.py                                                          | test_permission_resolver_explain.py           | Shared – explicabilidade do resolver
tests/shared/test_permission_resolver_cache_ttl_metric.py                                                 | test_permission_resolver_cache_ttl_metric.py  | Shared – métricas de TTL de cache
tests/shared/test_permission_resolver_cache_hit.py                                                        | test_permission_resolver_cache_hit.py         | Shared – acertos de cache no resolver
tests/shared/test_permissions_servicos_metrics.py                                                         | test_permissions_servicos_metrics.py          | Shared – métricas de permissões por serviços
tests/shared/permissions/test_permission_resolver_role_admin_flag.py                                      | test_permission_resolver_role_admin_flag.py   | Shared/Permissions – flag de admin no resolver
tests/shared/permissions/test_permission_resolver_personalizadas.py                                       | test_permission_resolver_personalizadas.py    | Shared/Permissions – permissões personalizadas
tests/shared/permissions/test_permission_resolver_missing_membership.py                                   | test_permission_resolver_missing_membership.py| Shared/Permissions – ausência de vínculo
tests/shared/permissions/test_permission_resolver_implicit.py                                             | test_permission_resolver_implicit.py          | Shared/Permissions – permissões implícitas
tests/shared/permissions/test_permission_resolver_cache_edgecases.py                                      | test_permission_resolver_cache_edgecases.py   | Shared/Permissions – casos limite de cache
tests/shared/permissions/test_permission_resolver_cache_and_precedence.py                                 | test_permission_resolver_cache_and_precedence.py | Shared/Permissions – cache e precedência
tests/shared/permissions/test_permission_resolver_cache.py                                                | test_permission_resolver_cache.py             | Shared/Permissions – cache do resolver
tests/shared/test_permissions_servicos.py                                                                 | test_permissions_servicos.py                  | Shared – permissões por serviços

# Prontuários (raiz tests/prontuarios)

tests/prontuarios/helpers.py                                                                              | helpers.py                                    | Prontuários – utilitários de teste
tests/prontuarios/test_foto_evolucao_api.py                                                               | test_foto_evolucao_api.py                     | Prontuários – API de fotos de evolução
tests/prontuarios/test_api_scopes.py                                                                      | test_api_scopes.py                            | Prontuários – escopos de API
tests/prontuarios/test_video_poster_task.py                                                               | test_video_poster_task.py                     | Prontuários – tarefa de poster de vídeo
tests/prontuarios/test_tasks_media.py                                                                     | test_tasks_media.py                           | Prontuários – tarefas de mídia
tests/prontuarios/test_slots_none.py                                                                      | test_slots_none.py                            | Prontuários – casos com slots None
tests/prontuarios/test_slots_date_filter.py                                                               | test_slots_date_filter.py                     | Prontuários – filtro por data de slots
tests/prontuarios/test_select2_pagination.py                                                              | test_select2_pagination.py                    | Prontuários – paginação em Select2
tests/prontuarios/test_select2_endpoints.py                                                               | test_select2_endpoints.py                     | Prontuários – endpoints de Select2
tests/prontuarios/test_quick_create_endpoints.py                                                          | test_quick_create_endpoints.py                | Prontuários – criação rápida via endpoints

# Segurança (raiz tests/security e subpastas login/twofa)

tests/security/test_security_headers.py                                                                   | test_security_headers.py                      | Segurança – cabeçalhos de segurança
tests/repo/test_sitecustomize_optional.py                                                                 | test_sitecustomize_optional.py                | Repositório – sitecustomize opcional

# 2FA

tests/security/twofa/test_twofa_regenerate.py                                                             | test_twofa_regenerate.py                      | Segurança/2FA – regeneração
tests/security/twofa/test_twofa_metrics_reset_and_ipblocks.py                                             | test_twofa_metrics_reset_and_ipblocks.py      | Segurança/2FA – reset de métricas e bloqueios de IP
tests/security/twofa/test_twofa_metrics_json.py                                                           | test_twofa_metrics_json.py                    | Segurança/2FA – métricas em JSON
tests/security/twofa/test_twofa_lockout.py                                                                | test_twofa_lockout.py                         | Segurança/2FA – lockout
tests/security/twofa/test_twofa_global_ip_rate_limit.py                                                   | test_twofa_global_ip_rate_limit.py            | Segurança/2FA – rate limit global por IP
tests/security/twofa/test_twofa_global_ip_limit_new.py                                                    | test_twofa_global_ip_limit_new.py             | Segurança/2FA – novo limite global de IP
tests/security/twofa/test_twofa_flow.py                                                                   | test_twofa_flow.py                            | Segurança/2FA – fluxo completo
tests/security/twofa/test_twofa_extra.py                                                                  | test_twofa_extra.py                           | Segurança/2FA – casos extras
tests/security/twofa/test_twofa_enforcement.py                                                            | test_twofa_enforcement.py                     | Segurança/2FA – enforcement
tests/security/twofa/test_twofa_crypto_fallback_and_cachefail.py                                          | test_twofa_crypto_fallback_and_cachefail.py   | Segurança/2FA – fallback criptográfico e falhas de cache
tests/security/twofa/test_twofa_crypto_and_rate.py                                                        | test_twofa_crypto_and_rate.py                 | Segurança/2FA – criptografia e rate limit
tests/security/twofa/test_twofa_core.py                                                                   | test_twofa_core.py                            | Segurança/2FA – núcleo
tests/security/twofa/test_twofa_commands.py                                                               | test_twofa_commands.py                        | Segurança/2FA – comandos
tests/security/twofa/test_sessions_2fa.py                                                                 | test_sessions_2fa.py                          | Segurança/2FA – sessões 2FA

# Login

tests/security/login/test_auth_backend.py                                                                 | test_auth_backend.py                          | Segurança/Login – backend de autenticação
tests/security/login/test_login_threshold_settings.py                                                     | test_login_threshold_settings.py              | Segurança/Login – thresholds de login
tests/security/login/test_login_rate_limit.py                                                             | test_login_rate_limit.py                      | Segurança/Login – rate limit de login
tests/security/login/test_login_block_bloqueio.py                                                         | test_login_block_bloqueio.py                  | Segurança/Login – bloqueios de login
tests/security/login/test_logging_service_ip_fallback.py                                                  | test_logging_service_ip_fallback.py           | Segurança/Login – fallback de IP em logging
tests/security/login/test_auth_blocking.py                                                                | test_auth_blocking.py                         | Segurança/Login – bloqueios gerais

# Estoque

tests/estoque/__init__.py                                                                                 | __init__.py                                   | Estoque – pacote de testes
tests/estoque/test_views_itens.py                                                                         | test_views_itens.py                           | Estoque – views de itens
tests/estoque/test_picking_reservas_descartes.py                                                          | test_picking_reservas_descartes.py            | Estoque – picking, reservas e descartes
tests/estoque/test_perdas_aprovacao_anexo.py                                                              | test_perdas_aprovacao_anexo.py                | Estoque – perdas, aprovação e anexos
tests/estoque/test_movimentos_lote_serie.py                                                               | test_movimentos_lote_serie.py                 | Estoque – movimentos por lote/série
tests/estoque/test_legacy_unit.py                                                                         | test_legacy_unit.py                           | Estoque – unidade legada
tests/estoque/test_fifo_bom_permissoes.py                                                                 | test_fifo_bom_permissoes.py                   | Estoque – FIFO/BOM e permissões
tests/estoque/test_api_kpis.py                                                                            | test_api_kpis.py                              | Estoque – KPIs de API
tests/estoque/test_api_basics.py                                                                          | test_api_basics.py                            | Estoque – fundamentos da API
tests/estoque/helpers.py                                                                                  | helpers.py                                    | Estoque – utilitários de teste

# User Management (raiz tests/user_management)

tests/user_management/test_twofa_service.py                                                                | test_twofa_service.py                         | User Management – serviço 2FA
tests/user_management/test_twofa_reencrypt_command.py                                                      | test_twofa_reencrypt_command.py               | User Management – comando de recriptografia 2FA
tests/user_management/test_twofa_rate_limits_edge.py                                                       | test_twofa_rate_limits_edge.py                | User Management – limites de taxa 2FA (bordas)
tests/user_management/test_twofa_basic.py                                                                  | test_twofa_basic.py                           | User Management – 2FA básico
tests/user_management/test_prune_expired_permissions.py                                                    | test_prune_expired_permissions.py             | User Management – limpeza de permissões expiradas
tests/user_management/test_logging_extra_json.py                                                           | test_logging_extra_json.py                    | User Management – logging extra em JSON
tests/user_management/test_audit_orphan_permissions.py                                                     | test_audit_orphan_permissions.py              | User Management – auditoria de permissões órfãs

# User Management (subpastas)

tests/user_management/sync/test_sync_status.py                                                             | test_sync_status.py                           | User Management/Sync – status de sincronização
tests/user_management/sync/test_sync_profiles_command.py                                                   | test_sync_profiles_command.py                 | User Management/Sync – comando de sync de perfis
tests/user_management/sync/test_reverse_sync.py                                                            | test_reverse_sync.py                          | User Management/Sync – sync reverso
tests/user_management/sync/test_cleanup_sessions_logs_command.py                                           | test_cleanup_sessions_logs_command.py         | User Management/Sync – limpeza de sessões/logs (comando)
tests/user_management/tasks/test_tasks_wrappers.py                                                         | test_tasks_wrappers.py                        | User Management/Tasks – wrappers de tasks
tests/user_management/sessions/test_lockout_expiration.py                                                  | test_lockout_expiration.py                    | User Management/Sessions – expiração de lockout

# Serviços

tests/servicos/test_servico_clinico_form.py                                                                | test_servico_clinico_form.py                  | Serviços – formulário de serviço clínico

# Agenda

tests/agenda/test_agenda_evento_tipo_cleanup.py                                                            | test_agenda_evento_tipo_cleanup.py            | Agenda – limpeza de tipos de evento

# Core (pasta core/tests)

core/tests/test_tenant_subdomain_concurrency.py                                                            | test_tenant_subdomain_concurrency.py          | Core – concorrência de subdomínio de tenant
core/tests/test_utils_and_inactivity.py                                                                    | test_utils_and_inactivity.py                  | Core – utilidades e inatividade
core/tests/test_utils_formatting_json.py                                                                   | test_utils_formatting_json.py                 | Core – utilidades de formatação JSON
core/tests/test_tenant_auto_select.py                                                                      | test_tenant_auto_select.py                    | Core – auto seleção de tenant
core/tests/test_subdomain_constants_sync.py                                                                | test_subdomain_constants_sync.py              | Core – sincronização de constantes de subdomínio
core/tests/test_subdomain_ajax.py                                                                          | test_subdomain_ajax.py                        | Core – AJAX de subdomínio
core/tests/test_smoke_chatbot_home.py                                                                      | test_smoke_chatbot_home.py                    | Core – smoke test da home do chatbot
core/tests/test_no_legacy_tenant_views.py                                                                  | test_no_legacy_tenant_views.py                | Core – views sem tenant legado
core/tests/test_legacy_core_suite.py                                                                       | test_legacy_core_suite.py                     | Core – suíte legada
core/tests/test_latency_middleware.py                                                                      | test_latency_middleware.py                    | Core – middleware de latência
core/tests/test_enabled_modules_normalization.py                                                           | test_enabled_modules_normalization.py         | Core – normalização de módulos habilitados
core/tests/test_departments_api.py                                                                         | test_departments_api.py                       | Core – API de departamentos
core/tests/test_dashboard_widgets_smoke.py                                                                 | test_dashboard_widgets_smoke.py               | Core – widgets do dashboard (smoke)
core/tests/test_views.py                                                                                   | test_views.py                                 | Core – views principais e fluxos básicos
core/tests/test_wizard_metrics_endpoint.py                                                                 | test_wizard_metrics_endpoint.py               | Core – endpoint de métricas do wizard
core/tests/test_wizard_metrics_abandon_and_sink.py                                                         | test_wizard_metrics_abandon_and_sink.py       | Core – abandono e sumidouro de métricas do wizard
core/tests/wizard_test_utils.py                                                                            | wizard_test_utils.py                          | Core – utilitários para testes do wizard de tenant
core/tests/test_wizard_update_flow.py                                                                      | test_wizard_update_flow.py                    | Core – fluxo de atualização do wizard
core/tests/test_wizard_subdomain_edges.py                                                                  | test_wizard_subdomain_edges.py                | Core – arestas de subdomínio no wizard
core/tests/test_wizard_services.py                                                                         | test_wizard_services.py                       | Core – serviços integrados ao wizard
core/tests/test_wizard_metrics_reset_command.py                                                            | test_wizard_metrics_reset_command.py          | Core – comando de reset de métricas do wizard
core/tests/test_wizard_metrics_no_tenant.py                                                                | test_wizard_metrics_no_tenant.py              | Core – métricas do wizard sem tenant
core/tests/test_wizard_finish_exception.py                                                                 | test_wizard_finish_exception.py               | Core – exceções no finish do wizard
core/tests/test_wizard_e2e.py                                                                              | test_wizard_e2e.py                            | Core – fluxo E2E do wizard
core/tests/test_wizard_duplicate_subdomain.py                                                              | test_wizard_duplicate_subdomain.py            | Core – subdomínio duplicado no wizard
core/tests/test_wizard_correlation_header.py                                                               | test_wizard_correlation_header.py             | Core – header de correlação no wizard
core/tests/test_wizard_context.py                                                                          | test_wizard_context.py                        | Core – contexto do wizard (dados por etapa)
core/tests/__init__.py                                                                                     | __init__.py                                   | Core – pacote de testes

# Tests – Core/Menu Middleware (pasta tests/core/menu_middleware)

tests/core/menu_middleware/__init__.py                                                                    | __init__.py                                   | Menu Middleware – pacote de testes
tests/core/menu_middleware/test_views.py                                                                  | test_views.py                                 | Menu Middleware – views e fluxo de criação de tenant
tests/core/menu_middleware/test_subdomain_constants_sync.py                                               | test_subdomain_constants_sync.py              | Menu Middleware – sincronização de constantes de subdomínio
tests/core/menu_middleware/test_subdomain_ajax.py                                                         | test_subdomain_ajax.py                        | Menu Middleware – AJAX de subdomínio
tests/core/menu_middleware/test_no_legacy_tenant_views.py                                                 | test_no_legacy_tenant_views.py                | Menu Middleware – sem views legadas de tenant
tests/core/menu_middleware/test_no_legacy_tenant_form.py                                                  | test_no_legacy_tenant_form.py                 | Menu Middleware – formulário sem legado de tenant
tests/core/menu_middleware/test_module_diagnostics_endpoint.py                                            | test_module_diagnostics_endpoint.py           | Menu Middleware – endpoint de diagnóstico de módulo
tests/core/menu_middleware/test_menu_integration.py                                                       | test_menu_integration.py                      | Menu Middleware – integração do menu
tests/core/menu_middleware/test_core_redirects.py                                                         | test_core_redirects.py                        | Menu Middleware – redirecionamentos do core

# Tests – Core/Tenant Wizard (pasta tests/core/tenant_wizard)

tests/core/tenant_wizard/test_wizard_multi_contacts.py                                                     | test_wizard_multi_contacts.py                 | Wizard de Tenant – múltiplos contatos
tests/core/tenant_wizard/test_wizard_snapshot.py                                                           | test_wizard_snapshot.py                       | Wizard de Tenant – snapshot do wizard
tests/core/tenant_wizard/test_wizard_multi_admin.py                                                        | test_wizard_multi_admin.py                    | Wizard de Tenant – múltiplos admins
tests/core/tenant_wizard/test_wizard_update_flow.py                                                        | test_wizard_update_flow.py                    | Wizard de Tenant – fluxo de atualização
tests/core/tenant_wizard/test_wizard_subdomain_edges.py                                                    | test_wizard_subdomain_edges.py                | Wizard de Tenant – arestas de subdomínio
tests/core/tenant_wizard/test_wizard_snapshot_edit.py                                                      | test_wizard_snapshot_edit.py                  | Wizard de Tenant – edição de snapshot
tests/core/tenant_wizard/test_wizard_admin_edit.py                                                         | test_wizard_admin_edit.py                     | Wizard de Tenant – edição por admin
tests/core/tenant_wizard/test_tenant_subdomain_concurrency.py                                              | test_tenant_subdomain_concurrency.py          | Wizard de Tenant – concorrência de subdomínio
tests/core/tenant_wizard/test_tenant_auto_select.py                                                        | test_tenant_auto_select.py                    | Wizard de Tenant – auto seleção de tenant
tests/core/tenant_wizard/test_tenantuser_default_role.py                                                   | test_tenantuser_default_role.py               | Wizard de Tenant – papel padrão de tenantuser
tests/core/tenant_wizard/test_multitenancy.py                                                              | test_multitenancy.py                          | Wizard de Tenant – multitenancy

# Core/Authorization (pasta tests/core/authorization)

tests/core/authorization/test_permission_cache_inspect.py                                                  | test_permission_cache_inspect.py              | Core/Authorization – inspeção de cache de permissões
tests/core/authorization/test_portal_whitelist.py                                                          | test_portal_whitelist.py                      | Core/Authorization – whitelist de portal
tests/core/authorization/test_permission_resolver_extended.py                                              | test_permission_resolver_extended.py          | Core/Authorization – resolver estendido de permissões
tests/core/authorization/test_permission_resolver_errors.py                                                | test_permission_resolver_errors.py            | Core/Authorization – erros do resolver
tests/core/authorization/test_module_deny_metrics_coexist.py                                               | test_module_deny_metrics_coexist.py           | Core/Authorization – métricas de negação de módulo (coexistência)
tests/core/authorization/test_module_deny_403_headers.py                                                   | test_module_deny_403_headers.py               | Core/Authorization – cabeçalhos 403 em negação de módulo
tests/core/authorization/test_middleware_unmapped_path.py                                                  | test_middleware_unmapped_path.py              | Core/Authorization – path não mapeado no middleware
tests/core/authorization/test_authorization_strict.py                                                      | test_authorization_strict.py                  | Core/Authorization – modo estrito
tests/core/authorization/test_authorization_logging.py                                                     | test_authorization_logging.py                 | Core/Authorization – logging de autorização
tests/core/authorization/test_authorization.py                                                             | test_authorization.py                         | Core/Authorization – autorização básica

# Core/Management (pasta tests/core/management)

tests/core/management/test_metrics_dump_command.py                                                         | test_metrics_dump_command.py                  | Core/Management – comando de dump de métricas
tests/core/management/test_management_commands_clear_system_cache.py                                       | test_management_commands_clear_system_cache.py| Core/Management – limpar cache do sistema
tests/core/management/test_management_commands_audit_multitenant.py                                        | test_management_commands_audit_multitenant.py | Core/Management – auditoria multitenant
tests/core/management/test_management_commands_audit_enabled_modules.py                                    | test_management_commands_audit_enabled_modules.py | Core/Management – auditoria de módulos habilitados
tests/core/management/test_management_commands_audit_auth_limit_and_reset.py                               | test_management_commands_audit_auth_limit_and_reset.py | Core/Management – auditoria de limites de auth e reset
tests/core/management/test_management_commands_audit_auth.py                                               | test_management_commands_audit_auth.py        | Core/Management – auditoria de autenticação

# Core/Legacy (pasta tests/core/legacy)

tests/core/legacy/test_urls.py                                                                             | test_urls.py                                  | Core/Legacy – URLs
tests/core/legacy/test_models.py                                                                           | test_models.py                                | Core/Legacy – modelos
tests/core/legacy/test_legacy_core_suite.py                                                                | test_legacy_core_suite.py                     | Core/Legacy – suíte legada
tests/core/legacy/test_cargo_normalization.py                                                              | test_cargo_normalization.py                   | Core/Legacy – normalização de cargo
tests/core/legacy/test_api.py                                                                              | test_api.py                                   | Core/Legacy – API legada

# Apps com testes próprios

prontuarios/tests/__init__.py                                                                              | __init__.py                                   | Prontuários – pacote de testes
prontuarios/tests/test_legacy_models_utils.py                                                              | test_legacy_models_utils.py                   | Prontuários – utilidades de modelos legados
notifications/tests/__init__.py                                                                            | __init__.py                                   | Notificações – pacote de testes
notifications/tests/test_realtime_flow.py                                                                  | test_realtime_flow.py                         | Notificações – fluxo em tempo real
notifications/tests/test_models_basic.py                                                                   | test_models_basic.py                          | Notificações – modelos básicos
notifications/tests/test_management_commands.py                                                            | test_management_commands.py                   | Notificações – comandos de management
notifications/tests/test_ajax_endpoints.py                                                                 | test_ajax_endpoints.py                        | Notificações – endpoints AJAX
documentos/tests/test_bulk_setup_api.py                                                                    | test_bulk_setup_api.py                        | Documentos – API de configuração em massa
estoque/tests/__init__.py                                                                                  | __init__.py                                   | Estoque – pacote de testes
estoque/tests/test_command_finalizar_setup.py                                                              | test_command_finalizar_setup.py               | Estoque – comando de finalizar setup
cotacoes/tests/test_portal_inline_update.py                                                                | test_portal_inline_update.py                  | Cotações – atualização inline no portal
cotacoes/tests/test_portal_fornecedor.py                                                                   | test_portal_fornecedor.py                     | Cotações – portal do fornecedor
agendamentos/tests/test_views.py                                                                           | test_views.py                                 | Agendamentos – views
admin/tests/__init__.py                                                                                    | __init__.py                                   | Admin – pacote de testes
admin/tests/test_admin_dashboard.py                                                                        | test_admin_dashboard.py                       | Admin – dashboard
admin/tests/test_admin.py                                                                                  | test_admin.py                                 | Admin – funcionalidades administrativas
```

Notas de manutenção:
- Se novos testes forem adicionados, inclua uma linha seguindo o mesmo formato.
- Para descrições mais precisas, consulte o conteúdo do arquivo e ajuste a frase.
- Caso deseje automatizar a geração desta lista, podemos adicionar um script de inventário em Python para varrer o diretório e produzir esta tabela.
