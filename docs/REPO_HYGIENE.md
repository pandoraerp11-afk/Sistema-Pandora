# Guia de Higiene do Repositório

Objetivo: manter a raiz e árvore de código sem artefatos temporários, arquivos vazios ou scripts obsoletos.

## Sentinelas Automatizados

1. Testes `repo_hygiene` (pytest marker):
   - `test_no_stray_root_files`
   - `test_removed_scripts_not_reintroduced`
   - `test_no_unexpected_large_files`
   - `test_no_legacy_flake8_artifacts`
   - `test_sitecustomize_pending_removal_documented`
   - `test_no_empty_docs_or_tests` (novo)
2. Hook pre-commit `forbid-legacy-scripts` (remove vazios, falha para arquivos com conteúdo).

## Lista de Arquivos Bloqueados
```
parse_ci.py
limpar_migracoes.py
_clean_caches.py
tmp_list_tu.py
sitecustomize.py
```

## Política para Arquivos Markdown
- Nenhum `.md` vazio deve ser versionado.
- Se um documento ainda será escrito, adicionar cabeçalho com contexto mínimo.

## Política para Testes
- Arquivos de teste não podem ser vazios; se placeholder, incluir comentário `# placeholder test` ou teste mínimo marcando futuro conteúdo.

## Como Extender
Adicionar novos nomes ao array `LEGACY` em `scripts/dev/check_no_legacy.py` e criar teste complementar se necessário.

## Fluxo ao Encontrar Arquivo Irregular
1. Hook tenta remover se for vazio e bloqueado.
2. Caso não seja vazio: commit falha; remover manualmente ou justificar (renomear e documentar).

## Justificativa Remoções
- `sitecustomize.py`: supressão de warning DRF tornou-se desnecessária.
- Scripts `parse_ci`, `tmp_list_tu`, etc.: eram inspeções ad-hoc não repetíveis.
- Flake8 config: substituído por ruff (unifica lint + format).

## Futuro
- Possível inclusão de verificação de tamanho máximo por extensão.
- Integração do resultado de higiene em badge (pass/fail) via GitHub Actions.
