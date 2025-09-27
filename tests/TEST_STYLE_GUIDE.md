## Guia de Estilo dos Testes

Objetivo: manter a suíte de testes clara, idiomática e sustentável.

### 1. Asserts
Usamos `assert` nativo do Pytest para introspecção rica. Qualquer ferramenta de segurança que marque `assert` em testes é configurada para ignorar (vide `pyproject.toml` per-file-ignores). Não substituir por wrappers desnecessários.

### 2. Nomeação
- Funções de teste: `test_<escopo>_<comportamento>`
- Variáveis temporárias legíveis (`client`, `response`, `tenant`).

### 3. Mensagens de Falha
Sempre que útil, adicionar mensagem após a vírgula: `assert cond, "explicação clara"`.

### 4. Limpeza de Estado
Evitar threads pesadas em SQLite. Onde concorrência for testada, reduzir threads e implementar retry leve (vide subdomínio).

### 5. Constantes em Settings
Testes de sincronização de constantes conferem apenas presença e coerência — não duplicar lógica de validação.

### 6. Lint
Regra S101 (uso de assert) ignorada em `tests/**`. Outras regras permanecem para evitar código morto ou complexidade desnecessária.

### 7. Evitar Abstrações Prematuras
Não criar camadas de helpers sem ganhos claros. Primeiro duplicar de forma simples, depois extrair se houver repetição significativa.

---
Atualizado automaticamente como parte da padronização de estilo de testes.