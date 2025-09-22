# Índice de Documentação

Atualizado: 2025-09-09

Este índice lista os documentos canônicos por tema e aponta potenciais duplicidades a tratar.

## Guias essenciais
- Gestão de Usuários (consolidado): `docs/USER_MANAGEMENT.md`
- Two-Factor (2FA) – operação e troubleshooting: `docs/TWOFA_SERVICE.md`
- 2FA – visão geral de endpoints: `docs/2FA.md`
- Permission Resolver – guia consolidado: `docs/PERMISSION_RESOLVER.md` (inclui formato de ACTION, precedência, Decision API e notas técnicas)
- Permissões Agendamentos (clínico): `docs/AGENDAMENTOS_PERMISSOES.md`

## Módulos
- Agendamentos (resumo): `docs/MODULE_AGENDAMENTOS.md`
- Agendamentos (proposta detalhada): `docs/MODULO_AGENDAMENTOS.md`
- Prontuários (resumo): `docs/MODULE_PRONTUARIOS.md`
- Prontuários – arquitetura (com status feito x faltante): `docs/PRONTUARIOS_ARQUITETURA.md`
- Prontuários – plano de modernização (legacy): `docs/legacy/PRONTUARIOS_MODERNIZACAO_PLAN.md`
- Estoque – plano de modernização: `docs/PLANO_MODERNIZACAO_ESTOQUE.md`
- Serviços – perfil clínico (validação): `docs/CLINICO_PERFIL_FORM_VALIDACAO.md`

## Wizards e Portais
- Wizard Clientes – implementação: `docs/WIZARD_CLIENTES_IMPLEMENTACAO.md`
- Wizard – configurações avançadas (backlog): `docs/WIZARD_CONFIGURACOES_AVANCADAS_BACKLOG.md`
- Wizard Tenant – handoff: `docs/WIZARD_TENANT_HANDOFF.md`
- Portal Cliente – Fase 1 (completo): `docs/PORTAL_CLIENTE_FASE1_COMPLETO.md`
- Portal Fornecedores/Clientes – Cotações: `docs/PORTAL_FORNECEDORES_CLIENTES_COTACOES.md`
- Portal Serviços (UI clínica): `docs/FRONTEND_PORTAL_SERVICOS.md`

## Operação, Status e Higiene
- Organização de testes: `docs/TESTES_ORGANIZACAO.md`
- Auditoria técnica avançada: `docs/AUDITORIA_TECNICA_AVANCADA.md`
- Preparação de Admin Dashboard: `docs/PREPARACAO_ADMIN_DASHBOARD.md`
- Status – Documentos: `docs/STATUS_MODULO_DOCUMENTOS.md`
- Status – Integração Funcionários x Estoque: `docs/STATUS_INTEGRACAO_FUNCIONARIOS_ESTOQUE_FINAL.md`
- Higiene do repositório: `docs/REPO_HYGIENE.md`
- Handoff para próximo agente de IA: `docs/AI_AGENT_HANDOFF.md`

## Histórico e Arquitetura
- Arquitetura geral: `docs/ARCHITECTURE.md`
- Changelog: `docs/CHANGELOG.md`

## Possíveis duplicidades a revisar
- Agendamentos: `MODULE_AGENDAMENTOS.md` x `MODULO_AGENDAMENTOS.md` (manter ambos por enquanto: resumo vs. proposta). Se futuramente quiser unificar, mover o detalhado para uma subpasta `docs/propostas/` e linkar do resumo.

## Pasta legacy
Conteúdos antigos ficam em `docs/legacy/` e não devem retornar para a raiz sem revisão.
