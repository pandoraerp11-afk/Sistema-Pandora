# Guia Rápido de Setup de Ambiente

## 1. Pré-requisitos
- Python 3.13.x instalado (PATH configurado).
- Git, Docker (opcional para Redis/Postgres externos).

## 2. Criar / Ativar Virtualenv
```bat
python -m venv venv
venv\Scripts\activate
```
(PowerShell: `venv\Scripts\Activate.ps1`)

## 3. Instalar Dependências
```bat
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Variáveis de Ambiente Úteis (opcionais em desenvolvimento)
Colocar em `.env` (já ignorado):
```
DJANGO_SETTINGS_MODULE=pandora_erp.settings
DEBUG=1
PANDORA_PERF=0
```

## 5. Banco Local
Por padrão usa `db.sqlite3`. Para Postgres + Redis, usar `docker-compose up -d` e ajustar settings próprios (não obrigatório para rodar testes básicos).

## 6. Rodar Migrações
```bat
python manage.py migrate
```

## 7. Rodar Testes Rápidos
```bat
pytest -m "not slow" -q
```
Permission resolver:
```bat
pytest -m permission -q
```

## 8. Cobertura
```bat
pytest --cov=shared --cov=core --cov=user_management --cov-report=term-missing -m "not slow"
```
Relatório HTML:
```bat
pytest --cov --cov-report=html
```
Saída gera diretório `htmlcov/` (já ignorado).

## 9. Limpeza de Caches
```bat
python scripts/dev/clean_caches.py
```
Remove `.pytest_cache`, `.mypy_cache`, `.coverage`, etc.

## 10. Troubleshooting Rápido
| Sintoma | Ação |
|--------|------|
| ImportError pacote | Verificar se venv está ativado (`where python`) |
| 302 inesperado em teste | Garantir helper multi-tenant (ver `tests/estoque/helpers.py`) |
| Permissão divergente | Habilitar trace: `settings.PERMISSION_RESOLVER_TRACE = True` em teste |
| Cache de permissão sem refletir mudança | Chamar `permission_resolver.invalidate_cache(user_id, tenant_id)` |

## 11. Próximos Passos
- Pre-commit já configurado com ruff (lint+format) + mypy + hooks genéricos.
- Integrar badge de cobertura (Codecov ou shields.io) no README.

## 12. Pre-commit Hooks (Qualidade Rápida)
Framework:
```bat
pip install pre-commit
pre-commit install
```
Arquivo `.pre-commit-config.yaml` já inclui ruff; exemplo mínimo moderno:
```yaml
repos:
	- repo: https://github.com/astral-sh/ruff-pre-commit
		rev: v0.6.9
		hooks:
			- id: ruff
			- id: ruff-format
	- repo: https://github.com/pre-commit/mirrors-mypy
		rev: v1.10.0
		hooks:
			- id: mypy
	- repo: https://github.com/pre-commit/pre-commit-hooks
		rev: v4.6.0
		hooks:
			- id: end-of-file-fixer
			- id: trailing-whitespace
			- id: mixed-line-ending
```

Execução manual para todos os arquivos:
```bat
pre-commit run --all-files
```

Opcional: rodar testes rápidos antes do commit adicionando hook local:
```yaml
	- repo: local
		hooks:
			- id: pytest-fast
				name: pytest-fast
				entry: pytest -m "not slow" -q
				language: system
				pass_filenames: false
```

Evite rodar a suíte completa no hook para não torná-lo lento.

---
Atualizado automaticamente (set/2025).
