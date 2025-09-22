# Modernização do Módulo de Estoque

Este documento resume as mudanças de modernização aplicadas ao módulo `estoque`.

## Principais Objetivos
- Padronizar templates utilizando a família `pandora_*_ultra_modern`.
- Extrair CSS e JavaScript inline para arquivos estáticos versionados.
- Introduzir endpoints de apoio para páginas dinâmicas (saldo disponível, histórico de reserva, KPIs, dashboard home).
- Melhorar acessibilidade (ARIA roles/labels em componentes interativos e Kanban).
- Reduzir código duplicado (mixin de dashboard) e preparar base para otimizações de performance.

## Templates Modernizados
- Lista de itens: `estoque_list.html` -> base moderna e links acessíveis.
- Detalhe de item: `estoque_detail.html` com `detail.css` + `item_detail.js`.
- Detalhe de reserva: `reserva_detail.html` usando `reservas_detail.js`.
- Kanban de picking: `picking/kanban.html` agora referencia `kanban.css` + `picking.js`.

## Arquivos Estáticos Chave
- `static/estoque/detail.css`
- `static/estoque/item_detail.js`
- `static/estoque/reservas_detail.js`
- `static/estoque/picking.js`
- `static/estoque/kanban.css` (novo, extraído do inline).

## Endpoints & URLs
Namespace `estoque_api`:
- `dashboard/home/` -> `HomeEstoqueView` (payload consolidado de dashboard).
- `dashboard/kpis/` -> `KPIsEstoqueView` (KPIs diversos com cache 60s).
- `saldo-disponivel/<produto_id>/<deposito_id>/` -> Saldo imediato.
- `historico-reserva/<reserva_id>/` -> Últimos movimentos relacionados.
- ViewSets REST já existentes (`depositos`, `saldos`, `movimentos`, etc.).

## Refatorações
- `EstoqueDashboardDataMixin` centraliza geração de estatísticas (home + futuros dashboards).
- Removida duplicação de `KPIsEstoqueView` (permanece apenas em `home.py`).
- Introduzido cache de 60s nos KPIs para evitar recomputo intenso em alta frequência.

## Testes Adicionados
- `test_api_basics.py` (saldo-disponivel, historico-reserva)
- `test_views_itens.py` (lista e detalhe de itens)
- `test_api_kpis.py` (estrutura básica, período customizado, fallback de período)

## Acessibilidade
- ARIA labels em filtros do Kanban e colunas (`role="group"`, `aria-label` descritivos).
- Botões de ação com `aria-label` ou texto explícito.

## Próximos Passos Potenciais
- Cobrir dashboard/home completo em testes (validar chaves do payload).
- Cache seletivo adicional (e.g. `grafico_movimentacao` separado com chave por tenant).
- Introduzir parametrização de limiares (estoque baixo) via configuração de sistema.
- Otimizar consultas de KPIs (prefetch/select_related onde aplicável).
- Adicionar endpoint para exportação (CSV/Excel) de saldos e movimentações.

## Convenções
- Não inserir JS inline: sempre criar arquivo em `static/estoque/`.
- Estilos específicos de página em arquivo dedicado; componentes compartilhados migrar para biblioteca comum futura.
- Decorar endpoints intensivos com cache curto (30–120s) quando seguro.

## Contato
Este documento deve ser atualizado conforme novas etapas de modernização forem concluídas.
