# Plano Integrado de Modernização dos Módulos de Estoque e Produtos (Padrão Ultra Moderno – Visão Completa)

Versão: 3.0 (Inclui especificação detalhada de Frontend, Templates, Eventos em Tempo Real, Permissões e Padrões de UI)

## 1. Objetivos Estratégicos Unificados
1. Unificar domínio Produtos + Estoque sob um modelo consistente orientado a eventos, evitando divergências de disponibilidade, custos e atributos.
2. Prover rastreabilidade ponta a ponta: criação do produto -> movimentação -> consumo/reserva -> custo -> auditoria.
3. Elevar maturidade de catálogo (atributos dinâmicos, variantes, pacotes, BOM / estrutura de materiais) suportando evolução industrial / comercial.
4. Entregar UX ultra moderna: navegação contextual, métricas em tempo real (WebSocket), modais de ação rápida, dashboards multi-seção, dark-mode-ready (respeitando design system).
5. Preparar base técnica para recursos avançados: forecasting, otimização de reposição, análise de giro por segmento, simuladores de custo e cenários.
6. Garantir segurança: permissões granuladas, trilha de auditoria imutável, prevenção de inconsistências concorrenciais com locking transacional.

## 2. Princípios Arquiteturais
- Domain Driven Approach (Bounded Contexts: CatalogoProdutos, OperacoesEstoque, Valuation, Reposicao, AuditoriaLogistica).
- Service Layer + Regras encapsuladas (nenhuma view grava direto nos modelos críticos).
- Eventos internos (Domain Events) publicados em Channel Layer -> consumidores para notificações, projeções (dashboards), e integração futura BI.
- Consistência forte para saldos (transação atômica) + consistência eventual para projeções (widgets / analytics cacheados).
- Extensibilidade: cada feature avançada (lotes, séries, forecasting) plugável sem refators massivos.

## 3. Visão Macro de Fases (Replanejado – Sem MVP “básico”, já estruturado completo nas camadas core)
Fase | Foco | Entregáveis Chave
-----|------|------------------
F1 Núcleo Consolidado | Catálogo robusto + Saldos multi-depósito + Movimentos tipificados + Service Layer + Auditoria | Novos modelos, APIs unificadas, dashboard v1 completo
F2 Operações Avançadas | Reservas, transferências, inventário cíclico, valuation médio + início FIFO, regras alerta mínimo | Serviços adicionais, WebSocket granular, modais rápidos
F3 Rastreabilidade Profunda | Lotes, números de série, BOM, ordens simples de consumo (produção / obra), ajustes inteligentes | Expansão modelo + UI detalhada
F4 Otimização & Forecast | Previsão demanda, políticas reabastecimento automáticas, aging, giro multi-dimensão | Engine de cálculo, relatórios avançados
F5 Analytics & Open API | Data Lake events, API pública versionada, painéis avançados multi-tenant | Exportações, streaming externo

## 4. Lacunas Atuais (Produtos + Estoque)
Área | Estado Atual | Lacuna | Consequência
----|--------------|--------|-------------
Produto (modelo) | Simples: nome, possivelmente categoria | Sem SKU global, variantes, atributos flexíveis | Dificulta escalabilidade catálogo
Unidades | Choices isolados | Sem tabela de unidades + conversões | Erros de conversão e redundância
Estoque | ItemEstoque separado de Produto | Duplicidade sem fonte única | Risco de divergência
Movimento | Sem custo snapshot / sem reversão formal | Auditoria fraca | Custo e compliance frágeis
Depósitos | Ausente | Sem segregação física | Baixa visibilidade logística
Reservas | Inexistente | Over-selling | Falhas de planejamento
Valuation | Não calculado | Sem custo médio/ FIFO | Margem e CMV imprecisos
Auditoria | Limitada | Sem trilha detalhada | Dificuldade forense
Lotes/Série | Não suportado | Sem rastreio | Limitação regulatória
Performance | Queries diretas em listas | Sem cache / índices planejados | Escalabilidade reduzida
UX | CRUDs horizontais | Falta ação rápida, métricas streaming | Produtividade menor

## 5. Novo Modelo de Dados (Consolidado)
Entidade | Propósito | Campos Chave | Observações
---------|----------|--------------|------------
Produto (refatorado) | Catálogo principal | sku(unique), nome, categoria(FK), tipo(enum: simples, variante_pai, variante), unidade_base(FK Unidade), ativo, barcode, origem, status_ciclo (ativo, suspenso, descontinuado) | SKU canônico, slug
ProdutoAtributoDef | Definição de atributo dinâmico | nome, tipo(valor_texto|num|bool|lista|json), unidade(FK opc), obrigatorio | Permite schema flexível
ProdutoAtributoValor | Valor por produto | produto, atributo_def, valor_textual, valor_num, valor_json | Index (produto, atributo_def)
ProdutoVariacao | Relaciona variante ao pai | produto_pai, produto_filho | Controla herança
Unidade | Unidade de medida | codigo, descricao, fator_base (Decimal) | Conversões
CategoriaProduto | Árvore | nome, parent | Materialized path / nested set
Deposito | Local físico | codigo, nome, tipo (ALMOX, TRANSITO, OBRA), obra(FK opc), ativo | Multi-tenant
EstoqueSaldo | Saldo por produto + depósito | produto, deposito, quantidade(Decimal 14,4), reservado, custo_medio(Decimal), atualizado_em | UNIQUE(produto, deposito)
MovimentoEstoque | Evento de alteração | produto, deposito_origem, deposito_destino, tipo(enum), quantidade, custo_unitario_snapshot, usuario, ref_externa, motivo, metadata(JSON), reverso_de(FK self) | Tipo: ENTRADA, SAIDA, AJUSTE_POS, AJUSTE_NEG, TRANSFER, RESERVA, LIB_RESERVA, CONSUMO_BOM
CamadaCusto (FIFO opc) | Layer de custo FIFO | produto, deposito, quantidade_restante, custo_unitario, ordem | Ativado F2+
ReservaEstoque | Reserva lógica | produto, deposito, quantidade, origem_tipo (PEDIDO, ORDEM, MANUAL), origem_id, status(ATIVA, CONSUMIDA, CANCELADA), expira_em | Indexs por produto
InventarioCiclico | Planejamento contagens | produto, deposito, periodicidade_dias, ultima_contagem, proxima_contagem | Geração automática de tarefas
Lote | Rastreio por lote | produto, codigo, validade, quantidade_atual | Integrado a movimentações
NumeroSerie | Rastreio unitário | produto, codigo, status, deposito_atual | Movimentado por linha
RegraReabastecimento | Política | produto, deposito, estoque_min, estoque_max, lote_economico, lead_time_dias, estrategia (FIXO, MEDIA_CONSUMO, FORECAST) | Usado em alertas
Bom (BillOfMaterials) | Estrutura produto composto | produto_pai, componente (produto), quantidade, perda_perc | Para consumo automático
LogAuditoriaEstoque | Log imutável | movimento(FK), snapshot_antes(JSON), snapshot_depois(JSON), usuario, criado_em | Guardar invariantes

### 5.1.1 Atores de Movimentação (Solicitante / Executante)
Requisito: Toda movimentação deve registrar QUEM solicitou e QUEM executou fisicamente (podem ser a mesma pessoa).

Tipos de ator suportados (polimórfico):
- Funcionário interno (app funcionarios)
- Terceirizado vinculado a Fornecedor (perfil cadastrado dentro de fornecedores)
- Cliente (retirada por cliente em alguns cenários de empreiteira / consignação)

Modelo Proposto:
- Campos em MovimentoEstoque: executante_user(FK auth.User), solicitante_tipo (enum: FUNCIONARIO, TERCEIRIZADO_FORNECEDOR, CLIENTE), solicitante_id (UUID/int), solicitante_nome_cache (para histórico imutável).
- Optional: relacionamento genérico via ContentType (flexível) OU tabela unificada PessoaOperacional (normalização futura). Nesta fase: usar (solicitante_tipo + solicitante_id + nome_cache) para simplicidade e audit trail.

Regras:
- Saída para cliente exige vínculo com pedido/OS (ref_externa obrigatória).
- Saída para terceirizado exige registro prévio de habilitação ativa (flag fornecedor_terceirizado_ativo).
- Tentativa com ator inativo -> bloqueio (NegocioError).
- Campos persistidos mesmo após exclusão lógica do ator (nome_cache preserva histórico).

Indices Adicionais:
- (solicitante_tipo, solicitante_id, data) para auditoria de retiradas.

### 5.1.2 Novos Tipos de Movimento para Descarte / Perdas
Adicionar ao enum de tipo (MovimentoEstoque.tipo):
- DESCARTE (descarte controlado de material vencido / impróprio)
- PERDA (quebra, avaria, furto confirmado)
- VENCIMENTO (baixa automática ou manual por vencimento de lote)
- DEVOLUCAO_CLIENTE (entrada por devolução)
- DEVOLUCAO_FORNECEDOR (saída retornando material defeituoso)

Campos Extras (quando tipo em [DESCARTE, PERDA, VENCIMENTO]):
- justificativa_obrigatoria (UI exige campo motivo detalhado)
- evidencias (campo FileField múltiplo em tabela separada MovimentoEvidencia: movimento, arquivo, descricao)
- aprovacao_status (PENDENTE, APROVADO, REJEITADO) – Workflow opcional (feature flag) para perdas acima de threshold.

Lógica:
- Movimento só afeta custo_medio se DEVOLUCAO_CLIENTE (entrada) ou DEVOLUCAO_FORNECEDOR (saída) seguindo valuation normal.
- DESCARTE / PERDA / VENCIMENTO reduzem saldo sem alterar custo_medio histórico (tratado como write-off para relatórios financeiros; custo médio permanece para estoque restante).
- Registrar perda financeira estimada: valor_perda = quantidade * custo_unitario_snapshot armazenado em metadata para BI.

Alertas:
- Descarte acima de limite diário gera evento estoque.alerta_descarte_anormal.
- Repetição de PERDA de mesmo produto em >3 ocorrências últimos 14 dias -> evento estoque.alerta_perda_reincidente.

Relatórios Futuros:
- KPI Shrinkage (% perdas + descartes sobre valor total movimentado).
- Aging de descartes por categoria.

### 5.1.3 Pedido de Separação de Materiais & Mensageria Operacional
Necessidade: Qualquer solicitante (funcionário, terceirizado fornecedor, cliente) deve poder pedir que determinados materiais sejam separados antes da retirada física, adicionando mensagens (chat) para orientações específicas (ex: "se possível separar caixas fechadas" ou "priorizar validade mais longa").

Novas Entidades:
1. PedidoSeparacao
	- Fields: codigo (slug/seq), solicitante_tipo, solicitante_id, solicitante_nome_cache, prioridade (BAIXA, NORMAL, ALTA, URGENTE), status (ABERTO, EM_PREPARACAO, PRONTO, RETIRADO, CANCELADO, EXPIRADO), data_criacao, data_limite(opc), criado_por_user, atualizado_em, canal_origem (PORTAL, MOBILE, API), motivo_cancelamento(opc), metadata(JSON).
2. PedidoSeparacaoItem
	- pedido(FK), produto(FK), quantidade_solicitada, quantidade_separada, unidade(FK), observacao(opc), reserva(FK ReservaEstoque opc), status_item (PENDENTE, SEPARADO, INDISPONIVEL, PARCIAL, CANCELADO).
3. PedidoSeparacaoMensagem
	- pedido(FK), autor_user(FK opc), autor_tipo (mesma enum solicitante_tipo), autor_id, texto (RichText simples / markdown restrito), criado_em, anexos_count (cache), importante (bool), metadata(JSON).
4. PedidoSeparacaoAnexo
	- mensagem(FK), arquivo(File), nome_original, tamanho_bytes, tipo_mime, criado_em.

Relação com Reservas e Movimentos:
- Ao mudar item para SEPARADO, cria (ou associa) ReservaEstoque (quantidade separada) prendendo saldo.
- Ao entregar (status pedido -> RETIRADO), gera Movimentos de SAIDA correspondentes consumindo reservas.
- Cancelamento reverte reservas ativas.

Eventos WebSocket:
- pedido_separacao.criado
- pedido_separacao.atualizado (status / prioridade)
- pedido_separacao.mensagem
- pedido_separacao.item_atualizado

Fila & Prioridade:
- Ordenação dinâmica: URGENTE > ALTA > NORMAL > BAIXA, tie-break por SLA (data_limite mais próxima) e data_criacao.
- SLA expirando (< 15 min) dispara evento pedido_separacao.alerta_sla.

Regras de Negócio:
- Pedido não pode ir para PRONTO se existir item PENDENTE sem justificativa INDISPONIVEL.
- Itens INDISPONIVEIS exigem campo observacao >= 10 caracteres.
- Mudança para RETIRADO exige que quantidade_separada == quantidade_solicitada para todos (ou PARCIAL explicitamente permitido com flag permitir_retirada_parcial).
- URGENTE requer justificativa e aprovação automática de usuário com permissão ESTOQUE_OPER ou superior.

Mensageria (Chat Operacional):
- Mensagens ordenadas por criado_em ASC.
- Mencionar operadores via @username (gera notificação PandoraNotif + WS).
- Flag importante destaca mensagem (ex: instruções de segurança).
- Anexos limitados por tamanho configurável (ex: 5MB cada).

Auditoria:
- Toda alteração de status do pedido gera entrada em LogAuditoriaEstoque (contexto operacional) vinculando snapshot relevante.

Performance / Escalabilidade:
- Contadores derivados (itens_totais, itens_pendentes, itens_separados) armazenados no PedidoSeparacao para dashboards.
- Índices: (status, prioridade), (data_limite), (solicitante_tipo, solicitante_id).

UX / Dashboard Picking:
- Colunas Kanban: ABERTO, EM PREPARAÇÃO, PRONTO.
- Atalhos de ação rápida (Iniciar, Concluir, Marcar Indisponível, Adicionar Mensagem).
- Visual micro timeline: criação -> início -> pronto -> retirado.

KPIs Futuros:
- tempo_medio_preparacao
- taxa_pedidos_parciais
- taxa_reabertura (pedidos reabertos após cancelamento parcial)
- volume_por_prioridade

Segurança:
- Solicitante só pode ver seus próprios pedidos (escopo por tipo/id).
- Operadores (ESTOQUE_OPER) veem todos (por tenant) e podem filtrar por prioridade.

Mobile / Offline (Roadmap):
- API simplificada para coleta via dispositivo móvel (scan barcode -> confirmar separação).

Backlog Complementar (relativo a Pedidos de Separação) será adicionado na seção 21.

### 5.1 Normalizações / Remoções
- ItemEstoque: será descontinuado após migração (fonte única será EstoqueSaldo + Produto).
- Campo unidade_medida direto removido em favor de FK Unidade.

## 6. Migração Estruturada (Produtos + Estoque)
Passo | Ação | Observações
-----|------|------------
1 | Criar novas tabelas (produtos extensões + estoque) | Sem tocar legados ainda
2 | Backfill Produtos: gerar SKU se ausente (algoritmo: PREFIXO + ID zero-pad) | Tabela auxiliar de mapeamento
3 | Mapear ItemEstoque -> EstoqueSaldo (criando depósito padrão se necessário) | Registro origem_legacy
4 | Congelar criação de novos ItemEstoque (read-only admin) | Banner técnico
5 | Introduzir Service Layer e redirecionar operações de views para serviços | Flag FEATURE_NEW_STOCK
6 | Migrar Movimentos antigos para MovimentoEstoque (se útil p/ histórico) | Preserva data
7 | Ativar WebSocket para novos eventos | Consumers registrados
8 | Retirar dependências diretas de ItemEstoque no código | Pesquisa + refactor
9 | Remover modelos legados após 2 ciclos estáveis | Backup + script export

## 7. Service Layer (arquivos)
Arquivo | Conteúdo | Funções
-------|----------|---------
estoque/services/saldos.py | Atualização de saldos | obter_saldo_lock(), aplicar_movimento()
estoque/services/movimentos.py | Orquestra movimentos | registrar_entrada(), registrar_saida(), ajustar(), transferir(), registrar_consumo_bom()
estoque/services/reservas.py | Reservas e liberações | criar_reserva(), consumir_reserva(), cancelar_reserva(), expirar_reservas()
estoque/services/valuation.py | Custo médio / FIFO | atualizar_custo_medio(), consumir_fifo()
produtos/services/catalogo.py | Criação/edição produtos + atributos | criar_produto(), atualizar_produto(), aplicar_variantes()
produtos/services/bom.py | Gestão BOM | adicionar_componente(), recalcular_custos_teoricos()
shared/exceptions.py | Exceções domínio | NegocioError, SaldoInsuficienteError, ReservaInvalidaError

Regras aplicadas centralmente; nenhum save() direto em views/forms.

## 8. Valuation (Design Completo)
Fase Inicial: Custo Médio Ponderado (atômico).
Extensão FIFO: Camadas criadas a cada ENTRADA; saída consome ordem crescente; fallback para custo médio se camadas inconsistentes.
Consumo BOM: custo acumulado = Σ (qtd_component * custo_medio_component) -> grava MovimentoEstoque tipo CONSUMO_BOM com custo_unitario_snapshot agregado.
Reprocessamento: comando management `recalcular_valuation --produto=x --desde=YYYY-MM-DD` reconstruindo custos para auditoria.

## 9. Concurrency & Integridade
- SELECT FOR UPDATE em EstoqueSaldo e, se FIFO ativo, também CamadaCusto.
- Idempotência de requisições críticas via header Idempotency-Key (tabela request_lock opcional Fase 2).
- Reversão: gerar movimento inverso, jamais deletar; LogAuditoria persiste delta.
- Invariantes validadas após cada commit (hook signal post_commit) disparando alerta se quebradas.

## 10. Integração Produtos ↔ Estoque
Integração Direta:
- Produto salvo -> se unidade alterada recalcular fator conversão dependente.
- Produto desativado -> bloqueia movimentações exceto saídas para zerar saldo.
- Endpoint agregador /api/catalogo/produtos/{id}/resumo -> {atributos, saldos_por_deposito, custo_medio, reservas, rupturas_ultimos_30d}.

Eventos Internos (Channel Layer / redis):
Evento | Quando | Consumidores
produto.atualizado | Alteração campos críticos | Cache invalidation, broadcast UI
estoque.movimento_criado | Novo MovimentoEstoque | Dashboard, notificações
estoque.alerta_minimo | Saldo < estoque_min | PandoraNotif + e-mail opcional
estoque.reserva_criada/liberada | Reserva lifecycle | Atualização disponibilidade

## 11. API (REST + futura GraphQL)
REST (DRF v1):
- /api/produtos/ (CRUD + filtros categoria, ativo, busca texto)
- /api/produtos/{id}/atributos/
- /api/produtos/{id}/saldos/
- /api/estoque/movimentos/ (POST tipificado; GET filtros: produto, deposito, tipo, data_ini/fim)
- /api/estoque/transferencias/ (POST high-level -> cria dupla)
- /api/estoque/reservas/ (CRUD parcial)
- /api/estoque/kpis/ (cards + séries temporais)
- /api/estoque/inventarios/ciclicos/ (planejamento)

GraphQL (fase futura): schema unificado para consultas agregadas (evitar N+1 em dashboards complexos).

## 12. WebSocket Streams
Canal Principal: ws/stream/estoque
Mensagens JSON padronizadas: {event, ts, payload_version, data}
Tipos: movimento, saldo_atualizado, alerta, reserva_evento.
Fallback polling incremental ETag /api/estoque/movimentos/?since=<cursor>.

## 13. UX / Telas Principais (Produtos + Estoque)
Página | Seções | Destaques
------|--------|----------
Dashboard Estoque | KPI cards, gráfico entradas x saídas, timeline, alert drawer, top rupturas | Live updates
Visão Produto | Header com status, tabs: Detalhes, Atributos, Saldos, Movimentos, Reservas, BOM | Tabela saldos inline
Gestão Movimentos | Lista filtra rápida, badges tipo, modal ação rápida | Bulk export CSV
Transferências | Wizard origem/destino + pré-validação | Indicador de latência
Reservas | Grid com origem (pedido / obra), SLA expiração | Botão liberar em massa
Inventário Cíclico | Calendário + fila pendente | Ação “contar agora”
BOM / Composição | Árvore componentes + custos acumulados | Simulação de custo

Guidelines Visuais: usar tokens, ZERO CSS inline, componentes reutilizáveis (partial stat_card, timeline_item, action_modal).

## 14. Fluxos Críticos (Exemplos Detalhados)
1. Entrada: modal -> validar produto ativo -> registrar_entrada -> recalcular custo -> emitir eventos -> atualizar UI via WS.
2. Saída: checar reservas -> saldo suficiente -> registrar_saida -> consumir FIFO se ativo -> eventos.
3. Transferência: lock origem + destino -> saída + entrada atômicas (logical_group_id) -> saldo destino atualizado.
4. Reserva: criar_reserva -> incrementa reservado -> saldo.disponivel recalculado -> emitir evento.
5. Consumo BOM: expandir componentes -> validar saldos -> criar movimentos SAIDA por componente + movimento CONSUMO_BOM no pai.
 6. Saída Terceirizado: usuário operador seleciona terceirizado (autocomplete fornecedores) -> valida ativo -> registrar_saida com solicitante_tipo=TERCEIRIZADO_FORNECEDOR -> evento auditoria.
 7. Saída Cliente: vincular a pedido/ordem -> registrar_saida (solicitante_tipo=CLIENTE) -> atualizar reservas (se existiam) liberando / consumindo.
 8. Descarte Vencimento: job verifica lotes vencidos -> gera movimentos VENCIMENTO batelados (aprovacao_status automático APROVADO) -> eventos de alerta.
 9. Descarte Manual (Avaria): operador abre modal DESCARTE/PERDA -> anexa evidências -> estado PENDENTE se > threshold -> aprovador revisa -> ao aprovar movimento efetiva saldo.
10. Pedido Separação: solicitante cria pedido (itens) -> operadores movem para EM_PREPARACAO -> marcam itens SEPARADO (criam reservas) -> todos separados -> status PRONTO -> retirada -> gera movimentos SAIDA.
11. Mensagem Pedido: autor posta mensagem -> persistência -> broadcast WS -> notificação interessados (operadores + solicitante).
12. Ajuste Parcial: parte dos itens indisponível -> marcar INDISPONIVEL com observação -> pedido pode concluir parcial se flag permitir_retirada_parcial ativa.

### 14.1 Workflow de Aprovação (Perdas / Descartes)
Critérios:
- Threshold configurável por tenant (ex: valor_perda > R$ X ou quantidade > Y) exige aprovação.
- Estados: PENDENTE -> (APROVADO|REJEITADO). Rejeição não altera saldo.
- Reprocessamento: se rejeitado, pode reenviar com complemento (nova linha justificativa armazenada em tabela MovimentoRevisao: movimento, usuario, comentario, data).

Eventos Workflow:
- estoque.perda_pendente -> notifica grupo ESTOQUE_ADMIN.
- estoque.perda_aprovada / estoque.perda_rejeitada -> atualiza dashboards e remove highlight.

UI Indicações:
- Badges de status nas linhas.
- Filtros rápidos: status:pendente.

## 15. Regras de Negócio Adicionais
- Estouro estoque negativo: bloqueado por padrão; flag de configuração por tenant permite exceção controlada (gera alerta crítico).
- Expiração de reservas: job periódico (celery/cron) -> libera e gera movimento LIB_RESERVA.
- Estoque mínimo: avaliação pós-movimento; se repetido > 3 dias gera recomendação reabastecimento.
- Produto variante herda atributos do pai se não sobrescrito.
- Saídas a terceiros (cliente / terceirizado): sempre exigem registro de solicitante e motivo (campo padrão). Falta de vínculo obrigatório bloqueia operação.
- Descartes / perdas: exigem justificativa detalhada (>= 15 caracteres) + pelo menos 1 evidência se valor_perda > threshold.
- Movimentos de devolução (cliente / fornecedor) ajustam custo médio conforme tipo (entrada aumenta, saída não recalcula histórico da origem).
- Job de reconciliação diária compara perdas declaradas vs valor total saída -> gera métrica shrinkage.
 - Pedido de separação não pode ser CANCELADO se já houver item SEPARADO sem desfazer reserva.
 - Mensagens não editáveis após 5 minutos (apenas nova mensagem de correção). Exclusão lógica somente moderadores.
 - Prioridade URGENTE limitada a N pedidos simultâneos (config tenant) para evitar abuso.

### 15.2 Invariantes Pedidos de Separação
- soma(quantidade_separada) ≤ quantidade_solicitada por item.
- Pedido.status = PRONTO implica zero itens status PENDENTE.
- Reserva associada a item SEPARADO deve existir e refletir quantidade_separada.
- Cancelamento libera todas reservas associadas.

### 15.1 Invariantes Específicos a Descartes / Perdas
- Não pode existir movimento DESCARTE sem justificativa.
- Um movimento PERDA aprovado não pode ser revertido diretamente: deve gerar DEVOLUCAO_FORNECEDOR ou AJUSTE_POS (caso achado material) como compensação auditada.
- Lote vencido não pode ser movimentado para SAÍDA comercial; somente VENCIMENTO ou DESCARTE.

## 16. Permissões (Matriz Expandida)
Papel | Escopo | Descrição
------|--------|----------
CATALOGO_VIEW | Produtos | Consultar catálogo
CATALOGO_EDIT | Produtos | Criar/editar produto, atributos, variantes
ESTOQUE_VIEW | Estoque | Consultar saldos/movimentos
ESTOQUE_OPER | Estoque | Entradas/saídas/transferências/ajustes
ESTOQUE_RESERVA | Reservas | Criar/cancelar reservas
ESTOQUE_ADMIN | Global | Depósitos, valuation config, reversões
ESTOQUE_AUDIT | Auditoria | Acessar logs e reprocessos valuation
ESTOQUE_DESCARTE_APROV | Workflow | Aprovar/rejeitar perdas/descartes
ESTOQUE_PICK | Picking | Operar pedidos de separação (mudar status itens/pedidos)
ESTOQUE_PICK_ADMIN | Picking | Gerenciar prioridades, cancelar pedidos, alterar SLA

Regra: usuários sem ESTOQUE_OPER não podem iniciar movimentos; usuários sem ESTOQUE_DESCARTE_APROV não veem fila de aprovação.

Políticas Atores Terceiros:
- Retiradas cliente: requer permissão ESTOQUE_OPER + vínculo pedido.
- Retiradas terceirizado: requer ESTOQUE_OPER e verificação de fornecedor ativo.

Logs guardam: executante_user_id, solicitante_tipo, solicitante_id, solicitante_nome_cache.
Pedidos de separação: adicionalmente guardam operador_responsavel_id (se atribuído) e timestamps transicionais (inicio_preparo, pronto_em, retirado_em).

## 17. Auditoria & Log Imutável
- LogAuditoriaEstoque com snapshots JSON (antes/depois) + hash encadeado (hash_previo + payload) para detecção de adulteração (cadeia simplificada).
- Endpoint somente leitura auditável.
- Exportador CSV/JSON e webhook (fase futura) para Data Lake.
- Campos adicionais auditados: solicitante, aprovacao_status, tipo_especial (DESCARTE | PERDA | VENCIMENTO), evidencias_ids.
- Geração de hash inclui estes campos para proteção contra manipulação posterior.

## 18. Observabilidade & Performance
Métricas: movimentos_count, movimentos_latency_ms, saldo_lock_wait_ms, eventos_ws_enviados, reservas_ativas, custo_reprocess_ms.
Picking Métricas: pedidos_abertos, pedidos_em_preparacao, pedidos_prontos_na_fila, tempo_medio_preparacao, backlog_prioridade (histograma). Alarmes se tempo_medio_preparacao > SLA.
Indices Planejados: (produto, deposito) em EstoqueSaldo; (produto, data) e (deposito, data) em MovimentoEstoque; (produto, atributo_def) em ProdutoAtributoValor.
Caching: kpis agregados em Redis (TTL 30s); bust por evento movimento.
Search: Campo SKU + nome indexado (pg_trgm) para busca rápida; fallback LIKE quando ausente.

## 19. Testes (Ampliação)
Camada | Tipo | Foco
-------|------|-----
Unit | Services | Invariantes saldo, custo médio, FIFO consumo
Unit | Valuation | Reprocessamento idempotente
Integration | API | Autorização, filtros, WebSocket handshake
Integration | Migração | Backfill e reconciliação saldos
Property-based | Sequência movimentos random | Garantir invariantes
Performance | Carga movimentos (batch) | Latência < alvo definido

Invariantes monitoradas automaticamente (teste property nightly).

## 20. Segurança & Compliance
- Limitar campos mutáveis em reversão (somente via serviço). 
- Sanitização de metadata JSON (whitelist de chaves). 
- Rate limiting endpoints críticos (reservas / movimentos) – throttle DRF custom.
- Logs de acesso sensível (consulta auditoria).

## 21. Backlog Detalhado Replanejado (Fase 1 Reforçada)
Ordem | Tarefa | Categoria | Estimativa
------|--------|----------|-----------
1 | Modelos catálogo (Produto refatorado, Unidade, Categoria, Atributos) | BE | 5pts
2 | Modelos estoque (Deposito, EstoqueSaldo, MovimentoEstoque) | BE | 5pts
3 | Service Layer núcleo (movimentos + saldos) | BE | 4pts
4 | Backfill SKU + saldos legado | Data/BE | 4pts
5 | API Produtos + atributos + saldos | BE | 4pts
6 | API Movimentos / Transferências | BE | 3pts
7 | Dashboard Estoque v1 completo | FE/BE | 4pts
8 | WebSocket eventos estoque | BE | 2pts
9 | Auditoria (log + endpoint) | BE | 3pts
10 | Testes unidade + integração núcleo | QA/BE | 4pts
11 | Otimizações índice + caching KPIs | BE | 2pts
12 | UI Produto (tabs integradas) | FE | 3pts
13 | Reversão de movimentos | BE | 2pts
14 | Hardening & limpeza ItemEstoque | BE | 2pts
15 | Modelo PedidoSeparacao + itens + mensagens | BE | 5pts
16 | API Pedidos + endpoints mensagens | BE | 4pts
17 | UI Kanban Picking + modais item | FE | 4pts
18 | WebSocket eventos pedidos/mensagens | BE | 2pts
19 | Integração reserva automática ao separar item | BE | 2pts
20 | KPIs picking + métricas | BE | 2pts
21 | Permissões picking + testes | BE/QA | 2pts
22 | Notificações @mention pedidos | BE/FE | 2pts

## 22. Status de Implementação (Consolidado)
Bloco | Situação | Observações
------|----------|------------
Modelos núcleo (Deposito, EstoqueSaldo, MovimentoEstoque, ReservaEstoque, Lote, NumeroSerie, CamadaCusto, PedidoSeparacao* etc.) | Implementado | Multi-tenant e índices base criados
Valuation (Médio + FIFO) | Implementado | Camadas FIFO com merge + reprocessamento custo_medio
Service Layer (movimentos, reservas, picking, descartes, BOM) | Implementado | Regras encapsuladas, validações e exceções
Workflow perdas / descarte | Implementado | Aprovação, evidências, sinais, permissões
Picking / Mensagens / Anexos | Implementado | Reservas automáticas + limitações URGENTE
Eventos / Sinais domínio | Implementado | movimento_registrado, pedido_picking_status, reserva_criada/consumida
WebSocket Consumers | Implementado | Estoque e Picking multi-tenant groups
Permissões expandidas | Implementado | Migration 0011 garante criação
KPIs + Cache | Implementado | Invalidação por sinais
Testes (core + novos fluxos) | Implementado | Cobrem FIFO, perdas, picking, reservas
Auditoria hash-chain (baseline) | Parcial | Hash chain implementada para movimentos; expandir para novos campos
Documentação Frontend | Agora detalhada nesta versão 3.0 | Ver seção 24+ 

## 23. Diretrizes de Templates & Design System
Princípio: TODOS os templates do módulo de estoque devem herdar de um template base já existente para garantir consistência visual (fontes, espaçamentos, cores, componentes). Referências primárias:
- `core/templates/base.html` (ou equivalente do módulo core) para páginas gerais
- `admin/base_site.html` para páginas administrativas internas quando fizer sentido
- Nenhum CSS inline: usar classes utilitárias ou blocks definidos (ex: `content`, `page_header`, `extra_js`).
- Fontes: reutilizar as mesmas importadas no core (NUNCA redefinir @font-face local sem necessidade).
- Ícones: usar o mesmo pack (ex: Heroicons / FontAwesome) importado em base; novos ícones devem seguir semântica existente.
- Estilo de componentes (cards, estatísticas, badges) deve buscar partials similares nos módulos `core` e `admin` antes de criar novos.
- Novos partials devem residir em `templates/estoque/partials/` com prefixo `_` e documentados (ver seção 25.2).

Estrutura de diretórios sugerida:
```
templates/
	estoque/
		dashboard.html
		movimentos/list.html
		movimentos/_filtro_form.html
		movimentos/_linha.html
		movimentos/modal_entrada.html
		movimentos/modal_saida.html
		movimentos/modal_transferencia.html
		reservas/list.html
		reservas/_linha.html
		picking/kanban.html
		picking/_coluna.html
		picking/_card_pedido.html
		picking/modal_item.html
		picking/modal_mensagem.html
		bom/gerenciar.html
		bom/_linha_componente.html
		inventario/ciclico.html
		inventario/modal_agendar.html
		atributos/produto_atributos.html
		auditoria/logs.html
		valuation/camadas.html
		partials/_kpi_cards.html
		partials/_stat_card.html
		partials/_timeline_movimentos.html
		partials/_alertas.html
```

Blocos Django a padronizar em cada template:
- `{% extends 'base.html' %}` ou `admin/base_site.html`
- `{% block title %}`Título – Estoque`{% endblock %}`
- `{% block content %}` wrapper principal com grid/layout
- `{% block extra_js %}` scripts específicos modulares (import de bundle tipo `estoque-dashboard.js`)
- Evitar lógica pesada no template – usar `context processors` ou `view models`.

## 24. Especificação de Páginas & Componentes (Frontend)
Cada página define: propósito, endpoints consumidos, principais componentes, eventos WebSocket assinados, interações JS e variáveis de contexto.

### 24.1 Dashboard de Estoque (`estoque/dashboard.html`)
Objetivo: visão resumida operacional + sinais de saúde.
Contexto inicial:
- `kpis` (dict agregado de `/api/estoque/saldos/kpis/`)
- `rupturas_top` (pré-carregado ou lazy via fetch)
- `alertas_iniciais` (lista gerada de eventos recentes)
Endpoints consumidos (AJAX/Fetch):
- GET `/api/estoque/saldos/kpis/` (refresh a cada 60s ou WS push)
- GET `/api/estoque/movimentos/?limit=20`
WebSocket Subscrições:
- Canal `estoque_stream` (eventos: movimento_registrado -> atualizar timeline, reserva_event -> atualizar cartão reservas)
Componentes / Partials:
- `_kpi_cards.html` (cards padrão reutilizáveis – cada card recebe: ícone, título, valor, delta)
- `_timeline_movimentos.html` (lista incremental; item = `_linha_movimento`)
- `_alertas.html`
JS Funções (arquivo `static/estoque/js/dashboard.js`):
- `initKPIAutoRefresh()` – agenda refresh + diff highlight
- `subscribeEstoqueSocket()` – abre WS, roteia eventos
- `appendMovimentoItem(data)` – insere novo movimento no topo mantendo limite
- `updateKpi(data)` – reconcilia valores com animação
- `renderAlert(alert)` – push em lista de alertas (máx N)
Estados & UX:
- Loading skeleton enquanto primeira chamada KPIs
- Fallback offline: se WS cair, exibe badge “Modo degradado” + continua polling

### 24.2 Lista de Movimentos (`estoque/movimentos/list.html`)
Objetivo: pesquisar, filtrar e acionar modais de lançamento.
Filtros suportados: produto (auto-complete), depósito, tipo, data_inicial, data_final, status_aprovacao.
Endpoints:
- GET `/api/estoque/movimentos/` (paginado; cursor ou page=)
- POST `/api/estoque/movimentos/entrada/`
- POST `/api/estoque/movimentos/saida/`
- POST `/api/estoque/movimentos/transferencia/`
- POST `/api/estoque/movimentos/descarte/`
- POST `/api/estoque/movimentos/{id}/aprovar|rejeitar/`
Modais (HTML parcial renderizado server + JS submit via fetch):
- `modal_entrada.html`, `modal_saida.html`, `modal_transferencia.html`, `modal_descarte.html`
WebSocket: recebe `SAIDA`, `ENTRADA`, `PERDA`, `TRANSFER` -> atualiza linha ou insere nova.
JS (`movimentos.js`):
- `openModal(tipo)`
- `submitMovimento(formEl)` -> valida, mostra spinner, trata erros NegocioError
- `applyFilters(params)` -> monta querystring & recarrega tabela via fetch + replace HTML parcial `_linha.html`
- `onSocketMovimento(ev)` -> decide inserção / atualização; highlight cor por tipo.
Context Vars:
- `tipos_movimento` (dict label)
- `permissoes_usuario` (flags booleans para exibir botões)

### 24.3 Reservas (`estoque/reservas/list.html`)
Lista reservas ativas, expiradas, consumidas. Ações: liberar, consumir.
Endpoints: GET `/api/estoque/reservas/`; POST ações (futuro).
WebSocket: eventos `reserva_criada`, `reserva_consumida`, `reserva_liberada` -> atualizam contagens.
JS: `reservas.js` com `bindRowActions()`, `handleSocketReserva()`.

### 24.4 Picking Kanban (`estoque/picking/kanban.html`)
Colunas: ABERTO, EM_PREPARACAO, PRONTO.
Endpoints:
- GET `/api/estoque/pedidoseparacao/?status=...`
- POST `/api/estoque/pedidoseparacao/{id}/iniciar|concluir|retirar/`
- POST `/api/estoque/pedidoseparacao/{id}/mensagem/`
- POST `/api/estoque/pedidoseparacao/{id}/anexar/`
- PATCH item: `/api/estoque/pedidoseparacao/items/{item_id}/` (ação separar / indisponivel)
WebSocket: canal `picking_stream` com eventos `pedido_picking_criado`, `pedido_picking_status`, `movimento_registrado` (quando retirada gera SAIDA)
Partials: `_coluna.html`, `_card_pedido.html`, `modal_item.html`, `modal_mensagem.html`.
JS (`picking.js`):
- `subscribePicking()`
- `renderPedidoCard(p)`
- `moveCardStatus(pedidoId, novoStatus)`
- `abrirModalItem(itemId)` / `submitSepararItem()`
- `abrirModalMensagem()` / `submitMensagem()` / `uploadAnexo()`
- `applyUrgentLimitBadge(count, max)`
Regra visual: cards URGENTE com borda pulsante breve + contador global.

### 24.5 BOM / Composição (`estoque/bom/gerenciar.html`)
Objetivo: manutenção componentes e visualização custo teórico.
Endpoints:
- GET `/api/produtos/{id}/bom/`
- POST/DELETE `/api/produtos/{id}/bom/componentes/`
JS: `bom.js` -> `addComponente()`, `removeComponente()`, `recalcularCustoTeorico()`.
Exibição: tabela componentes; coluna perda_perc; badge se controle lote/serie.

### 24.6 Inventário Cíclico (`estoque/inventario/ciclico.html`)
Exibir lista e agenda (calendário simples). Ações: criar, forçar contagem.
Endpoints: CRUD padrão `/api/estoque/inventarios/ciclicos/` + POST contagem futura.
JS: `inventario_ciclico.js` -> `agendarContagem()`, `executarContagem()`.

### 24.7 Auditoria (`estoque/auditoria/logs.html`)
Lista paginada de logs com filtros (movimento_id, produto, período).
Endpoint: GET `/api/estoque/movimentos/?...` + futuro `/api/estoque/auditoria/`.
Realce: se hash_previo ausente em sequência -> sinalizar quebra (investigação).

### 24.8 Valuation / Camadas FIFO (`estoque/valuation/camadas.html`)
Mostrar camadas ativas por produto/deposito; opções: reprocessar.
Endpoints: GET `/api/estoque/valuation/camadas/?produto_id=&deposito_id=` (futuro); POST `reprocessar`.
JS: `valuation.js` -> `listarCamadas()`, `executarReprocesso()`.

### 24.9 Atributos Dinâmicos (`estoque/atributos/produto_atributos.html`)
Carrega definições e valores via `/api/produtos/atributos/`; inline edit.
JS: `atributos.js` -> `editarValor(produtoId, atributoId)` -> salva PATCH.

## 25. Componentização & Partials
### 25.1 Padrões de Nomenclatura
`_nome_componente.html` para partials. Inclusão via `{% include 'estoque/partials/_stat_card.html' with icon='box' value=total %}`.

### 25.2 Lista de Partials Necessários
Partial | Props Esperados | Uso
--------|-----------------|----
_stat_card.html | icon, titulo, valor, delta(optional) | KPI cards
_kpi_cards.html | kpis(dict) | Wrapper que instancia vários `stat_card`
_timeline_movimentos.html | movimentos(list) | Dashboard timeline
_alertas.html | alertas(list) | Drawer de alertas
_linha.html (movimentos) | movimento | Linha tabela movimentos
_coluna.html (kanban) | status, pedidos(list) | Kanban picking
_card_pedido.html | pedido | Card individual
_linha_componente.html | componente | Linha BOM

## 26. JavaScript Modular (Estratégia)
Cada página principal tem um arquivo JS (ES6) carregado em `block extra_js` após HTML para evitar race conditions.
Namespace global evitado; usar IIFE ou módulos (caso bundler). Exemplo padrão de inicialização:
```
document.addEventListener('DOMContentLoaded', () => {
	EstoqueDashboard.init({ wsUrl: window.ESTOQUE_WS_URL });
});
```
Fallback: se WebSocket falhar -> `EstoqueDashboard.enablePolling()`.

Tratamento de Erros Padrão:
- Resposta 400 -> exibir mensagens field-level (dataset errors-json)
- Resposta 403 -> modal de permissão insuficiente
- Resposta 409 (futuro idempotência) -> mostrar notificação “Operação já processada”.

## 27. WebSocket Especificação Mensagens
Formato Normalizado:
```
{
	"event": "estoque.movimento",
	"ts": "2025-08-14T12:34:56Z",
	"version": 1,
	"data": { ...payload específico... }
}
```
Eventos Correntes Map (origem -> event):
- movimento_registrado(ENTRADA/SAIDA/TRANSFER/PERDA/DESCARTE/VENCIMENTO/CONSUMO_BOM) -> `estoque.movimento`
- reserva_criada/reserva_consumida/liberada -> `estoque.reserva`
- pedido_picking_criado -> `picking.pedido`
- pedido_picking_status -> `picking.status`
- (futuro) perda_aprovada / rejeitada -> `estoque.perda_workflow`

Estratégia de Roteamento JS:
```
switch(evt.event){
	case 'estoque.movimento': MovimentosUI.onNovoMov(evt.data); break;
	case 'estoque.reserva': ReservasUI.onReserva(evt.data); break;
	case 'picking.pedido': PickingUI.onNovoPedido(evt.data); break;
	...
}
```

## 28. Permissões no Frontend (Gating Render)
Variável de contexto `permissoes_usuario` = { pode_operar, pode_aprovar, pode_consumir_bom, pode_gerenciar_picking, pode_gerenciar_reabastecimento }.
Templates usam:
```
{% if permissoes_usuario.pode_operar %}<button id="btnEntrada">Entrada</button>{% endif %}
```
JS reforça (defense in depth) removendo / ocultando botões se flag ausente.

## 29. Testes Frontend Recomendados
Tipo | Ferramenta | Cenários
-----|------------|---------
Smoke WS | pytest + channels testing | Conecta, recebe movimento simulado
E2E | Cypress/Playwright | Fluxos: entrada -> saída -> picking -> retirada
A11y | axe-core (CI) | Dashboard e Kanban sem violações críticas
Performance | Lighthouse | Time-to-interactive < 3s em dashboard com 50 movimentos iniciais

## 30. Checklist de Implementação FE
1. Criar diretórios e partials base
2. Implementar dashboard estático + placeholders
3. Integrar KPIs (fetch) + skeleton
4. Conectar WebSocket estoque -> atualizar timeline
5. Formulários modais (entrada/saida/transfer) com validação
6. Lista movimentos paginada + filtros dinâmicos
7. Kanban picking + drag (futuro) / ações botões imediatos
8. Chat mensagens + upload anexo (progress bar)
9. BOM gerenciar + inline add/remove
10. Inventário cíclico agendar + visualizar próxima contagem
11. Auditoria visualizar logs + verificador de hash
12. Valuation camadas list + ação reprocessar
13. Atributos dinâmicos inline edit
14. Hardening UX (tratamento falhas rede)
15. Testes E2E e acessibilidade

## 31. Padrões de Estilo / Design (Resumo Operacional)
Referenciar tokens existentes (ex: variáveis SCSS ou classes utilitárias). Não redefinir tipografia; usar heading semântico h1-h4 dentro do bloco content. Botões primários reutilizam classe `.btn-primary` do core; botões destrutivos `.btn-danger`. Badges de tipo de movimento: mapear tipo -> cor (SAIDA=--danger, ENTRADA=--success, TRANSFER=--info, PERDA/DESCARTE=--warning).

## 32. Roadmap Próximas Extensões (Pós 3.0)
- Forecast consumo + curva ABC automatizada
- Simulador de custo futuro (cenário de reajuste)
- Recomendação reabastecimento probabilística (Monte Carlo)
- Painel de anomalias (detecção outliers perdas / ruptura)

## 33. Próximos Passos Imediatos (Execução FE)
1. Aprovar especificação 3.0
2. Gerar branch `feature/estoque-frontend` e bootstrap de templates
3. Implementar Dashboard e Movimentos (milestone 1)
4. Implementar Picking Kanban + WS (milestone 2)
5. Implementar BOM + Inventário + Auditoria (milestone 3)
6. Refinar valuation UI e atributos dinâmicos (milestone 4)
7. E2E + A11y + Performance baseline (milestone 5)

---
Documento versão 3.0 – Modernização concluída backend & especificação detalhada frontend pronta para execução. Ajustes incrementais podem ser anexados conforme feedback.
