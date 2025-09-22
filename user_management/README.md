# user_management – Guia Interno

## Objetivo
Gerenciar ciclo de vida de perfis, convites, sessões, bloqueios e permissões personalizadas multi-tenant.

## Componentes
- Modelo `PerfilUsuarioEstendido`: status, bloqueio, tentativas, 2FA flag.
- Modelo `PermissaoPersonalizada`: modulo/acao/recurso/(scope_tenant) concedida True/False.
- Modelos de sessão & log: `SessaoUsuario`, `LogAtividadeUsuario`.
- Signals centralizados: criação idempotente de perfil, logging de login/logout/falha, invalidadores de cache de permissão.
- Backend `PerfilStatusAuthenticationBackend`: bloqueia login por status/bloqueado_ate + reseta tentativas.
- Serviços:
  - `profile_service.ensure_profile(user)` / `sync_status(user)`
  - `logging_service.log_activity(user, action, domain, message, **ctx)`
  - Permission resolver global em `shared.services.permission_resolver`.

## Fluxo de Criação de Usuário
1. Cria user.
2. Signal `perfil_estendido_handler` chama `ensure_profile` (get_or_create) e depois `sync_status`.
3. `TenantUser` criado separadamente (fora deste pacote) aplica role default.

## Autenticação
Ordem backends (settings): PerfilStatusAuthenticationBackend, Guardian.
Regras backend:
- Rejeita status INATIVO / BLOQUEADO / SUSPENSO.
- Rejeita se `bloqueado_ate` futuro.
- Zera tentativas a cada login bem-sucedido.
Falhas incrementam tentativas e aplicam bloqueio temporário (>=5 → 30 min + status BLOQUEADO).

## Permissões
Resolver unificado (`permission_resolver.resolve(user, tenant, ACTION, resource)`) ou API estruturada (`permission_resolver.resolve_decision(...)`) que retorna `PermissionDecision` (documentação consolidada em `docs/PERMISSION_RESOLVER.md`; lá também existe `explain_permission` para depuração):
1. Bloqueios conta.
2. Permissões personalizadas ordenadas por score (deny > allow; scoped+resource > scoped > global+resource > global).
3. Role do tenant.
4. Papéis implícitos (fornecedor, cliente placeholder).
5. Defaults.
Cache: versão por user/tenant; signals de save/delete incrementam versão.

## Portal vs Interno
Definição portal: `user.user_type == 'PORTAL'` OU grupo PortalUser.
Whitelist: `settings.PORTAL_ALLOWED_MODULES`.
`can_access_module` aplica whitelist antes de chamar resolver.

## Sessões
`SessaoUsuario` criado/atualizado em login, marcado inativo em logout ou limpeza (`limpar_sessoes_expiradas`).
`SESSION_MAX_INACTIVITY_MINUTES` define inatividade lógica (integração futura com job periódico).

## Invariantes
- Sempre um `PerfilUsuarioEstendido` por usuário ativo.
- Permissões personalizadas com escopo incoerente (tenant inexistente) devem ser ignoradas pelo resolver.
- Version bump de cache sempre que `PermissaoPersonalizada` salva ou remove.
- Bloqueio temporário exige reset manual de status após expirar (tarefa futura pode automatizar via `desbloquear_usuarios`).

## Testes Essenciais
- auth blocking (`test_auth_blocking.py`)
- permission resolver precedence
- cache version invalidation
- sessão & 2FA

## Próximas Melhorias
- Automação desbloqueio pós `bloqueado_ate`.
- Enriquecer métricas (contadores de deny agregados).
- Middleware caching de perfil no request.
- Remover qualquer signal residual duplicado (já consolidado).

