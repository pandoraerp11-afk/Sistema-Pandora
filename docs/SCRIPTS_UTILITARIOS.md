# Scripts Utilitários

Localização padronizada: `scripts/dev/` (ambiente de desenvolvimento) ou `scripts/ops/` (operações futuras).

## Ativos

| Script | Caminho | Descrição |
|--------|---------|-----------|
| clean_caches.py | scripts/dev/clean_caches.py | Remove caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage`). |
| finalizar_setup_estoque (command) | estoque/management/commands/finalizar_setup_estoque.py | Aplica migrations (opcional), cria permissões e seeds básicos do módulo estoque. |

### Uso rápido
```
python manage.py finalizar_setup_estoque --skip-migrate --skip-permissions --skip-seed  # smoke
python manage.py finalizar_setup_estoque  # fluxo completo

# Compat (legado - será removido): --no-permissoes / --no-seed
```

## Removidos / Obsoletos

| Antigo | Motivo |
|--------|--------|
| `_clean_caches.py` (raiz) | Realocado para `scripts/dev/clean_caches.py`. |
| `limpar_migracoes.py` | Operação destrutiva em `django_migrations`; não versionar. Use squash/fake migrations oficialmente. |
| `parse_ci.py` | Debug ad-hoc de workflow CI; não necessário contínuo. |
| `tmp_list_tu.py`, `tmp_lookup_bella.py` | Scripts temporários de inspeção de banco; substitua por queries via `manage.py dbshell` ou fixtures de testes. |

## Boas Práticas

1. Evitar scripts que executem testes automaticamente como parte de "setup" sem flag explícita.
2. Qualquer script que altere dados (DELETE/UPDATE direto) deve virar management command auditável ou ser documentado em playbooks internos.
3. Prefira management commands (`app/management/commands/*.py`) quando a ação envolver modelo/ORM e possa ser útil em produção.
4. Scripts de migração manual de dados devem incluir dry-run.

Atualize este documento sempre que adicionar ou remover scripts.