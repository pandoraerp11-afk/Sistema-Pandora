# Notas sobre Monkeypatches Temporários

Este arquivo documenta os monkeypatches centralizados em `core/monkeypatches.py`.

## Objetivos
1. Remover `RemovedInDjango60Warning` relativo a `URLField` sem depender do flag transitório `FORMS_URLFIELD_ASSUME_HTTPS`.
2. Eliminar `DeprecationWarning` do Python 3.13 emitido por `widget_tweaks` ao usar `re.split` com argumento posicional para `maxsplit`.

## Implementação
- `URLField.formfield`: wrapper injeta `assume_scheme='https'` apenas quando não fornecido explicitamente. Impacto mínimo e facilmente removível após Django 6 (quando a mudança de padrão já estiver consolidada ou a lib ajustada).
- Patch de `widget_tweaks`: em vez de sobrescrever `re.split` globalmente, localizamos o módulo `widget_tweaks.templatetags.widget_tweaks` e substituímos apenas a referência interna usada lá por um shim que passa `maxsplit` como keyword.

## Plano de Remoção
| Patch | Critério de remoção | Ação futura |
|-------|---------------------|-------------|
| URLField assume_scheme | Após migração para Django >= 6 e revisão se warnings não retornam sem o wrapper | Remover função `_urlfield_formfield` e restauração implícita ao comportamento nativo |
| widget_tweaks shim | Quando a lib publicar versão compatível (ou se for removida do projeto) | Remover bloco try/except correspondente |

## Riscos & Mitigações
- Risco: comportamento inesperado em forms que explicitamente desejam `assume_scheme=None`. Mitigação: podem sobrescrever passando `assume_scheme` manualmente no form field.
- Risco: módulo de template tags mudar nome interno de `re`. Mitigação: try/except silencioso; teste visual de warnings indica necessidade de ajuste.

## Testes Associados
- `core/tests/test_wizard_update_flow.py::WizardUpdateFlowTest::test_update_change_subdomain_case_insensitive_normalization` garante normalização de subdomínio (relacionado ao fluxo onde patch foi inicialmente validado).
- Ausência de warnings monitorada via execução de `pytest -q` (baseline esperado: zero warnings de depreciação relevantes desses dois casos).

## Verificação Rápida
```
pytest -q core/tests/test_wizard_update_flow.py::WizardUpdateFlowTest::test_update_change_subdomain_case_insensitive_normalization
```

Se não houver warnings referentes a URLField ou widget_tweaks, patches continuam válidos. Caso warnings retornem, reavaliar se houve atualização de dependências.

---
Documento temporário – remover quando ambos os patches forem eliminados.
