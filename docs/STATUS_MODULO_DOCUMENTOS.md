# Status do Módulo "documentos" – Pandora ERP

Data: 12/08/2025
Autor: GitHub Copilot

## TL;DR
- Django atualizado para 5.2.5 (compatível com Python 3.13) e erro de ImportError (AND/OR) resolvido.
- Home de Documentos alinhada ao layout ultra-moderno e com percentuais corretos na "Distribuição de Exigência".
- Regras: criado fluxo para criar regra global via home (rota dedicada) e por entidade via página da entidade.
- Resolução robusta de ContentType para apps com múltiplos models.
- Migrações aplicadas; sem pendências no app `documentos` no momento.

## O que foi feito
1. Compatibilidade/ambiente
   - Atualização do Django para 5.2.5 para suportar Python 3.13 (corrige ImportError em `django.db.models.sql.where`).
2. Backend – models/forms/views
   - `RegraDocumento`: suporte a escopos (app, filtro, entidade), campos `app_label`, `filtro_tipo_fornecimento`, `data_base` e cálculo de periodicidade efetiva.
   - `Documento`: campo `periodicidade_aplicada` (aplica override de regra quando presente).
   - Resolver de ContentType mais robusto: `_get_content_type_or_404(app_label, object_id, model_hint)`.
   - Views de regras: criação global (`regra_create_global`), por entidade (`regra_create`), edição (`regra_edit`) e exclusão (`regra_delete`) com redirecionamentos seguros.
   - Views passam `page_title`/`page_subtitle` ao template base para evitar erros.
3. Frontend – templates
   - `documentos_home.html`: cards, ações rápidas, link para criar regra global (removido modal placeholder), lista de regras recentes, percentuais de exigência corretos.
   - `regra_form.html`: campos e UX para escopos (app/filtro/entidade), sugestões de `app_label`, campos auxiliares `model_hint` e `entidade_object_id` quando criação global.
   - Sidebar/menu: item “Gestão de Documentos” aponta para a nova home.
4. Rotas
   - `documentos/urls.py`: adicionada rota `regras/nova/` (global), mantidas rotas por entidade e edição/exclusão.
5. Admin
   - `RegraDocumento` registrado com colunas e filtros úteis (já existente/ajustado).

## Arquivos alterados principais
- `documentos/models.py`
- `documentos/forms.py`
- `documentos/views.py`
- `documentos/urls.py`
- `documentos/templates/documentos/documentos_home.html`
- `documentos/templates/documentos/regra_form.html`
- `fornecedores/templates/fornecedores/fornecedores_detail.html` (botão para regras por entidade)
- `templates/pandora_ultra_modern_base.html` (menu)

## Estado atual
- Checks: `manage.py check` PASS.
- Migrações: sem alterações pendentes para `documentos`.
- Home documentos exibe totais, regras recentes e percentuais corretos.
- Criação de regras:
  - Global: via `documentos/regras/nova/`.
  - Por entidade: via botão “Regras de Documentos” na página do fornecedor (e demais entidades, quando integradas).

## Como testar rapidamente
- Abrir “Gestão de Documentos” no menu lateral.
- Criar regra global (app/filtro ou entidade) via “Nova Regra”.
- Em um fornecedor, usar “Regras de Documentos” para criar regra específica e verificar a lista.

## Itens pendentes (para retomar depois)
- Autocomplete (AJAX) para tipos e entidades no formulário global.
- Job/rotina para materializar/aplicar regras em lote e marcar documentos “vencidos”.
- Relatórios/compliance dashboards para regras/documentos.
- Melhorias de UX: filtros na home (por app/entidade), paginação em “Regras Recentes”.

## Observações
- `requirements.txt` já aceitava Django >= 5.1; o ambiente foi ajustado para 5.2.5.
- Removido modal de “Nova Regra” na home; agora é página dedicada (mais estável e validável).

## Ponto de retomada sugerido
- Implementar autocomplete e validações assíncronas no formulário global de regras.
- Criar management command para revisar vencimentos com base em `validade_dias`/`data_base` e periodicidade.
- Integrar regra de “filtro por atributos” com Fornecedores (Produtos/Serviços/Ambos) ao aplicar documentos automaticamente.
