# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.

## [0.1.4] - 2025-09-12
### Added
- Métrica simples de negações clínicas (`metric:clinical_schedule_denials`) incrementada em `can_schedule_clinical_service` + helper `get_clinical_denials_count()`.
- Inline errors para sub-form clínico em `partials/servico_form_tab_dados_principais.html`.
- Documento `FRONTEND_PORTAL_SERVICOS.md` (parâmetros e comportamento UI de serviços clínicos).
- Documento atualizado `CLINICO_PERFIL_FORM_VALIDACAO.md` marcando inline errors como concluído.

### Changed
- Permissão `IsClientePortal` ajustada para inferir tenant via slot antes de negar, garantindo mensagem unificada.
- Mensagens de negação clínica agora usam constante central traduzível `CLINICAL_SCHEDULING_DENIED_MESSAGE` em todos os endpoints.

### Observability
- Preparação para futura exportação Prometheus (métrica ainda apenas em cache local, expiração 1h).

### Notes
- Nenhuma regra de negócio (ServicoClinico) alterada; mudanças estritamente de UX (erros inline), i18n e telemetria leve.

## [0.1.3] - 2025-09-11
### Documented
- `docs/MODULO_SERVICOS.md`: adicionada seção "Regras de Negócio IMUTÁVEIS (ServicoClinico)" deixando explícita a proibição de alterar semântica/validações/defaults/cálculos sem aprovação.
- `docs/AI_AGENT_HANDOFF.md`: incluída política específica para futuros agentes sobre não alterar regras do `ServicoClinico` e referência ao documento canônico.

### Changed
- Limpeza textual: comentários/docstrings atualizados para usar "serviço/servico_id" onde aplicável (sem alteração de comportamento).

### Notes
- Regras de negócio do `ServicoClinico` preservadas integralmente; apenas documentação e comentários foram atualizados.

## [0.1.2] - 2025-09-10
### Added
- Template ponte `generic_list.html` permitindo que listas legadas (ex: agendamentos) usem o layout `pandora_list_ultra_modern.html` sem alterar blocos `list_*` existentes.
- Registro inicial de status da API v2 de Agendamentos (scaffold `AgendamentoV2ViewSet`).
- Serializers dedicados v2 (`AgendamentoV2ListSerializer`, `AgendamentoV2DetailSerializer`, `AgendamentoV2CreateSerializer`).
- Testes v2: list shape, detail auditoria, create manual, create via slot, validação erro sem slot/datas.

### Changed
- `agendamentos/agendamento_list.html` passou a herdar apenas de `generic_list.html` (removida duplicidade de `{% extends %}`) mantendo integralmente colunas e lógica de exibição.
- Endpoint create da API v2 agora retorna payload detalhado (detail serializer) incluindo `id` e auditoria (lista inicial vazia).

### Documented
- Marcado no roadmap que Fase 2 (FK em prontuários) permanece congelada até decisão explícita de ativação.
- Clarificado no documento `MODULO_AGENDAMENTOS.md` o status "scaffold" da API v2 (retorna vazio se flag `USE_NOVO_AGENDAMENTO` desativada).

### Integrity
- Teste `AgendamentoViewsTest::test_agendamento_list_view` passando após ajustes de herança; garante não regressão de conteúdo (cliente visível na listagem).

### Notes
- Nenhuma regra de negócio alterada; mudanças exclusivamente estruturais/templating e documentação.

## [0.1.1] - 2025-09-09
### Added
- Documento de handoff para próximo agente de IA: `docs/AI_AGENT_HANDOFF.md`.
- Índice canônico de documentação: `docs/INDEX.md`.
- Teste de higiene de documentação: `tests/test_docs_hygiene.py`.

### Changed
- Consolidação de documentação de Gestão de Usuários em `docs/USER_MANAGEMENT.md`.
- Consolidação de Permission Resolver em `docs/PERMISSION_RESOLVER.md`.
- Plano de modernização de Prontuários movido para `docs/legacy/PRONTUARIOS_MODERNIZACAO_PLAN.md`; visão atual em `docs/PRONTUARIOS_ARQUITETURA.md`.

### Removed
- Remoção de documentos obsoletos consolidados (detalhes em `docs/_DELETION_LOG.md`).

## [0.1.0] - 2025-09-04
### Added
- Estrutura inicial de CHANGELOG com Commitizen.
- Dockerfile multi-stage (builder + runtime + target dev).
- Workflow CI atualizado (matriz Python 3.12/3.13, cobertura, artifacts).
- Workflow de segurança (bandit + pip-audit agendado).
- Pre-commit modernizado com ruff, bandit, pip-audit.
- `pyproject.toml` com configurações centralizadas (ruff, coverage, mypy, black, pytest).
- `.editorconfig` para padronização multi-IDE.
- `requirements-dev.txt` segregando dependências de desenvolvimento.

### Changed
- Substituição de flake8/autopep8 por ruff (lint+format) em pre-commit.

### Security
- Adicionados scanners automáticos (bandit, pip-audit) via workflow dedicado.
