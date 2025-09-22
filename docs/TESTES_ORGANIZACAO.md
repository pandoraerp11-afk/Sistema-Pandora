# Guia Unificado de Organização e Padronização de Testes

![Coverage Badge](https://codecov.io/gh/example-org/pandora-erp/branch/main/graph/badge.svg)

Fonte única de verdade para convenções, estrutura, execução e metas de cobertura da suíte de testes do Pandora. Substitui os antigos `TESTES_ORGANIZACAO.md` e `TEST_GUIDELINES.md` (agora legado proibido).

## Sumário
1. [Objetivo & Escopo](#1-objetivo--escopo)
2. [Runner & Descoberta](#2-runner--descoberta)
3. [Estrutura de Diretórios](#3-estrutura-de-diretórios-domínios)
4. [Nomeação](#4-nomeação)
5. [Estilos Aceitos](#5-estilos-aceitos)
6. [Fixtures Globais](#6-fixtures-globais)
7. [Helpers Multi‑Tenant](#7-helpers-multi-tenant--padrões)
8. [Markers](#8-markers)
9. [Permission Resolver](#9-permission-resolver--arquivos-consolidados)
10. [Execução de Subconjuntos](#10-execução-de-subconjuntos)
11. [Cobertura & Metas](#11-cobertura--metas)
12. [Boas Práticas](#12-boas-práticas-de-conteúdo--performance)
13. [Anti‑Padrões](#13-anti-padrões)
14. [Refatoração & Legacy](#14-política-de-refatoração--remoção-legacy)
15. [Roadmap](#15-próximos-passos-roadmap)
16. [Checklist](#16-checklist-novo-teste)
17. [Logging Service](#17-logging-service)
---
## 17. Logging Service
Diretório: `tests/user_management/logging`.
Escopo: validar comportamento de `log_activity` (serviço central de auditoria de ações de usuário):
- Fallback de IP vazio/None para `0.0.0.0`.
- Fallback de user_agent vazio/None para `N/A`.
- Truncamento defensivo: `acao<=100`, `modulo<=50`, `descricao<=255`.
- Chamada com `user=None` deve ser silenciosamente ignorada (nenhum log criado, não levantar exceção).
Boas práticas: não mockar o modelo; usar asserts de persistência mínima. Extensões futuras (JSON extra) só entram após implementação real.

Unificar regras de escrita, organização, execução, performance e evolução incremental da suíte.

## 2. Runner & Descoberta
Configuração principal em `pytest.ini`:
```
[pytest]
DJANGO_SETTINGS_MODULE = pandora_erp.settings
python_files = tests.py test_*.py *_tests.py
addopts = --cov=core --cov=user_management --cov=shared --cov-report=term-missing
```
Todos os novos apps devem adicionar diretórios de testes seguindo a taxonomia abaixo. (Futuro: mover inclusão de módulos de domínio para `addopts` conforme forem priorizados.)

## 3. Estrutura de Diretórios (Domínios)
Cada subpasta representa um recorte semântico com objetivo claro. Evitar criação de pastas ambíguas.

## Estrutura por Domínio

| Diretório | Foco | Exemplos |
|-----------|------|---------|
| `tests/core/authorization` | Autorização modular (portal, headers 403, cache) | `test_authorization*.py` |
| `tests/core/tenant_wizard` | Multi-tenant & wizard de criação | `test_wizard_*`, `test_tenant_*` |
| `tests/core/menu_middleware` | Menu, middleware de módulos, subdomínios | `test_menu_integration.py` |
| `tests/core/legacy` | Casos antigos em transição | `test_legacy_core_suite.py` |
| `tests/security/login` | Autenticação primária | `test_login_*`, `test_auth_*` |
| `tests/security/twofa` | Fluxos 2FA | `test_twofa_*` |
| `tests/user_management/profile` | Perfil, cache, desbloqueio | `test_profile_*` |
| `tests/user_management/sync` | Sincronização & comandos | `test_sync_*` |
| `tests/estoque` | Operações de estoque | `test_api_*`, `test_movimentos_*` |
| `tests/prontuarios` | Prontuários clínicos | `test_slots_*` |
| `shared/tests` | Serviços reutilizáveis / perm resolver | `test_permission_resolver_*` |
| `user_management/tests` | Autenticação & 2FA integradas | `test_sessions_2fa.py` |
| `notifications/tests` | (REMOVIDO legacy) | — |

## 4. Nomeação
Arquivos: `test_<contexto>_<foco>.py`. Funções: `test_<condicao>_<resultado>` quando descreve claramente o comportamento. Evitar nomes genéricos (`test_basic`, `test_ok`).

## 5. Estilos Aceitos
- Preferir funções simples + fixtures.
- Usar `django.test.TestCase` somente quando `setUpTestData` ou transações otimizam custo.
- Evitar heranças profundas ou `unittest.TestCase` puro sem necessidade.

## 6. Fixtures Globais
Listadas em `conftest.py` (exemplo):
- `tenant_with_all_modules` – tenant completo.
- `auto_enable_modules` (autouse) – garante módulos habilitados para novos testes.
Adicionar novas fixtures com nomes curtos e claros; promover a globais somente após uso em ≥2 apps.

## 7. Helpers Multi‑Tenant & Padrões
Helper `tests/estoque/helpers.py`:
- `bootstrap_user_tenant(client, username='x', password='pass')` – cria usuário, tenant, vínculo e injeta `tenant_id` na sessão.
Checklist para evitar 302 inesperado:
1. Usuário autenticado? (`client.login` / `force_login`).
2. Sessão tem `tenant_id`?
3. `enabled_modules` populado? (fixture autouse cuida, senão chamar helper apropriado).
4. `reverse()` com namespace correto?

## 8. Markers
Declarados em `pytest.ini` (manter sincronizado para evitar warnings):
- `slow` – >1s ou recurso pesado.
- `permission` – precedência/cache de permissões.
- `security` – rate limit / 2FA / bloqueios.
- `login` – autenticação primária.
- `twofa` – segunda etapa 2FA.

## 9. Permission Resolver – Arquivos Consolidados
Os testes relacionados ao algoritmo de resolução de permissões foram consolidados sob `shared/tests`:

- `test_permission_resolver_basic_user.py` – casos básicos (allow/deny, precedence global vs scoped).
- `test_permission_resolver_expiration_resource.py` – expiração e granularidade de recursos.
- `test_permission_resolver_cache_version.py` – versionamento de cache e invalidação reativa via signals.
- `test_permission_resolver_deny_global_vs_allow_scoped.py` – cenários de precedência específicos adicionais.
- `test_permission_resolver_precedence_variants.py` – (mantido se já existir variantes de precedência complexa; criar se necessário futuramente).
- `test_permission_resolver_performance.py` – baseline de desempenho (executado somente quando `PANDORA_PERF=1`).

## 10. Execução de Subconjuntos
Exemplos (Windows `cmd` na raiz `backand`):
```bat
pytest -m "not slow" -q
pytest -k permission_resolver -q
pytest -m permission -q
set PANDORA_PERF=1 & pytest shared/tests/test_permission_resolver_performance.py -q
pytest -m security -q
pytest -m twofa -q
pytest tests/core/authorization -q
pytest tests/estoque -q
```

## 11. Cobertura & Metas
Status atual: Gate global (stage 3) em 70% no CI (relatório combinado + HTML artifact). Próximo alvo planejado: 80% após ampliar cobertura de permission resolver avançado, 2FA e middleware.
Metas focais:
- `user_management`: 85% (subir para 90% após estabilização)
- `core`: 80%
- Demais módulos: elevar quando tocados (regra: PR que altera módulo deve adicionar/ajustar testes relevantes)
Relatórios: XML por versão + combinado + HTML (matriz primária e combinado) enviados como artefatos.

## 12. Boas Práticas de Conteúdo & Performance
1. Sem dependência de ordem.
2. Dados criados próximos ao teste (evitar mega fixtures globais).
3. URLs via `reverse()`.
4. Evitar `time.sleep` >0.2s – preferir monkeypatch.
5. Assertions específicas (status, campos, fragmentos semânticos).
6. Após mutações, usar `.refresh_from_db()`.
7. Não logar secrets reais em testes de segurança.
8. Hash de senha ajustado (rápido), emails em memória, Celery eager.

## 13. Anti‑Padrões
| Padrão | Substituir Por | Motivo |
|--------|----------------|--------|
| `print` para debug | `pytest -vv`, asserts claros | Poluição de saída |
| `time.sleep(5)` | monkeypatch / janela pequena | Build lento |
| Reutilizar instâncias ORM sem refresh | `.refresh_from_db()` | Estado stale |
| Teste dependente de outro | Dados independentes | Fragilidade |

## 14. Política de Refatoração & Remoção Legacy
Remover testes legacy somente após garantir cobertura equivalente em local organizado. `notifications/tests/test_notifications.py` foi removido por não agregar valor (modelos obsoletos). Pastas `legacy` devem encolher ao longo do tempo.

## 15. Próximos Passos (Roadmap)
- Gate de cobertura incremental (planejado elevar gradualmente até 90%).
- Relatório HTML de cobertura como artefato.
- Testes de carga leve (login + 2FA) com métricas de latência.
- Parametrização consolidada de precedência no resolver.
- Helpers adicionais para `prontuarios` e outros domínios.

## 16. Checklist Novo Teste
- [ ] Nome descreve intenção
- [ ] Independente de ordem
- [ ] Usa fixtures adequadas
- [ ] Assertions focadas
- [ ] Atualiza métricas/cobertura se crítico
- [ ] Marker aplicado (security/slow/permission/login/twofa)

---

Histórico: unificação concluída (set/2025) substituindo documentos separados.
Foi removido o placeholder legacy `notifications/tests/test_notifications.py` (marcado previamente com `@pytest.mark.skip`). Justificativa: modelos referenciados foram renomeados/removidos e o teste não acrescentava cobertura real.

