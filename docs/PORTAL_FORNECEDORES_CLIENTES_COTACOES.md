# Documentação Completa – Portal de Fornecedores, Portal de Clientes e Módulo de Cotações

> Versão: 1.1  
> Data: 2025-08-20  
> Responsável: (preencher)  
> Status: Versão consolidada pós refinamentos (Prontuários, Agenda, Mídia, Funcionários) – pronta para execução faseada.

## CHANGELOG
| Versão | Data | Alterações Principais |
|--------|------|-----------------------|
| 1.0 | 2025-08-18 | Rascunho inicial (fornecedores, clientes, cotações) |
| 1.1 | 2025-08-20 | Inclusão especificação detalhada Portal Cliente (ContaCliente, Dashboard, Fotos low‑res), integração agenda moderna (Slots atômicos), pipeline mídia async (thumbnails, WEBP, vídeo), métricas Prometheus e logging estruturado, filas Celery segmentadas (media/video), circuit breaker transcodificação, plano de permissões com escopo tenant e camadas, modelo de auditoria portal, roadmap estendido e alinhamento multi‑tenant. |

---

## 1. Objetivo
Padronizar e orientar a evolução do sistema para suportar plenamente:
1. Portal de Fornecedores (auto‑cadastro, homologação, participação em cotações, prestação de serviços/solicitação de materiais).  
2. Portal de Clientes (agendamentos, acompanhamento de procedimentos/serviços, consultas de compras/pedidos).  
3. Módulo de Cotações (criação pela empresa, convite a fornecedores, propostas e seleção).  
4. Base unificada de permissões e participação multi‑papéis sem redundância de dados.

Escopo agora inclui alinhamento com:
- Agenda transacional (reservas de slot atômicas / concorrência). 
- Prontuários + Mídia (imagens/vídeos com derivados assíncronos). 
- Observabilidade (Prometheus, logging estruturado, métricas de tasks). 
- Multi‑fila Celery (default, media, video) e limites de carga.
- Padrões multi‑tenant consistentes (chaves de filtragem e isolamento lógico). 

## 2. Escopo
Inclui modelos de dados, fluxos, endpoints, regras de negócio, segurança, roadmap de implantação, plano de migração e testes. Exclui (por ora) integrações externas (ERP terceiro, gateway pagamento) e analytics avançados.

Inclui adicionalmente nesta versão:
- Especificação Portal Cliente (detalhe nível de serviço + UX mínima).
- Estratégia de exposição segura de mídia derivativa (thumbnails / webp / poster vídeo) ao cliente.
- Padrão de métricas e health-checks para portais e cotações.
- Estratégia de evolução permission resolver (precedência e escopo tenant cachável).

## 3. Visão Geral Atual (Resumo do Estado Existente)
| Domínio | Situação Atual | Lacunas |
|---------|----------------|---------|
| Fornecedor | Modelos ricos (empresa/pf, documentos, homologação), sem vínculo usuário | Falta AcessoFornecedor, portal, propostas, solicitações materiais |
| Cliente | `AcessoCliente` existente + documentos | Precisa integração agenda e visão unificada de serviços/compras |
| Funcionário | Completo (HR) opcionalmente linkado ao usuário | Redundância cargo/salário no perfil estendido |
| Cotações | Ausente (apenas comentários em `compras/views.py`) | Necessário modelo completo de cotação e propostas |
| Permissões | TenantUser + Role + PermissaoPersonalizada global | Falta escopo em permissões personalizadas, precedência clara |
| Auditoria | Logs em core + user_management | Unificar abordagem modular (tag modulo) |
| Agenda | Modernizada (Slots atômicos, transações) | Expor subset seguro ao Portal Cliente |
| Mídia (Prontuários) | Pipeline async (thumb, webp, vídeo poster, transcode, validação) | Segmentar acesso derivativos vs original e auditoria consumo |
| Observabilidade | Métricas counters tasks + alguns summaries | Ampliar histogram portal / health / backlog filas |

## 4. Personas e Principais Casos de Uso
| Persona | Objetivos | Casos Principais |
|---------|-----------|------------------|
| Admin Empresa | Reduzir custo de aquisição e controle | Criar cotação, aprovar fornecedor, selecionar proposta |
| Fornecedor (Admin Portal) | Oferecer produtos/serviços, responder cotações | Auto-cadastro, enviar proposta, anexar docs, solicitar liberação material |
| Fornecedor Colaborador | Operacionalizar tarefas | Inserir preços, anexos, registrar entrega/prazo |
| Cliente Final | Consumir serviços, acompanhar histórico | Ver agenda, agendar, ver procedimentos, consultar pedidos |
| Colaborador Interno | Executar processos | Criar cotação, analisar propostas, liberar material |
| Super Admin (SaaS) | Governa plataforma | Monitorar tenants, métricas, suporte |

## 5. Domínio Portal de Fornecedores (Alvo)
### 5.1 Modelos Novos / Alterações
- `AcessoFornecedor(fornecedor, usuario, is_admin_portal, ativo, data_concessao)`
- (Futuro) `FornecedorSubconta` se necessário granularidade maior (adiável)
- `SolicitacaoMaterialExterno(fornecedor, usuario, almoxarifado, itens, status, timestamps)` (Fase 2)
- Campo `portal_ativo` (bool) em `Fornecedor` (Fase 1) 
- Token de auto‑cadastro opcional: `portal_token_autoregistro`, `token_expira_em` (Fase 3)

### 5.2 Estados do Fornecedor
| Campo | Estados | Efeito no Portal |
|-------|---------|------------------|
| status_homologacao | pendente, aprovado, reprovado | Apenas aprovado pode enviar proposta ou solicitar material |
| status | active, inactive, suspended | suspended/inactive bloqueiam login |
| portal_ativo | True/False | False: bloqueia acesso até ativação |

### 5.3 Fluxos Principais
1. Auto‑cadastro fornecedor → cria registro (homologação pendente) + usuário + `AcessoFornecedor` inativo.
2. Homologação aprovada → ativa acesso, envia e‑mail.
3. Convite direto (admin) → aceita → escolhe se associa a CNPJ existente ou cria novo.
4. Receber cotação → preencher proposta → enviar (gera lock de edição).
5. Atualização de documentos → dispara revalidação se documento crítico expira.
6. Solicitação material (serviço terceirizado) → aprova → gera movimentação estoque (Fase 2).

## 6. Domínio Portal de Clientes
### 6.1 Conceitos Fundamentais
Portal focado em autoatendimento seguro e limitado ao conjunto de dados autorizados para o paciente / cliente dentro do tenant.

### 6.2 Modelagem Complementar
Substituir / evoluir `AcessoCliente` ou introduzir `ContaCliente` (nome final a validar) com os campos:
- user (FK auth.User) UNIQUE
- tenant (FK Tenant, index)
- paciente (FK Paciente) – 1:1 típico
- ativo (bool)
- ultimo_login_portal (DateTime)
- preferencias (JSON) – ex: notificacoes_email, idioma
- consentimentos (JSON) – ex: versoes politicas, LGPD
- created_at / updated_at

Índices recomendados: (tenant, paciente), (tenant, user)

### 6.3 Derivados de Mídia Segura
Cliente acessa apenas:
- `imagem_thumbnail`, `imagem_webp`, `video_poster`. 
- Vídeo (se permitido) somente versão transcodificada otimizada (perfil aprovado) – nunca original bruto.
Política: campos originais atrás de permissão staff; serializer portal filtra.

### 6.4 Integração Agenda
- Expor endpoint read‑only de slots disponíveis (fonte: módulo Agenda modernizado) com filtros: serviço, profissional, intervalo.
- Reservas: criação gera registro `Agendamento` com estado inicial `solicitado` | `pendente_confirmacao` conforme política do tenant.
- Atomicidade: reutilizar chamada transacional com lock implementada no core de Agenda (select_for_update nos Slots) via service layer para evitar duplicidade.

### 6.5 Políticas de Cancelamento e Janela Futura
Config por tenant:
- `PORTAL_CLIENTE_CANCELAMENTO_LIMITE_HORAS` (ex: 24)
- `PORTAL_CLIENTE_JANELA_MAXIMA_DIAS` (ex: 60)
Validações aplicadas no service `AgendamentoPortalService` antes de confirmar/cancelar.

### 6.6 Dashboard Cliente (Service `build_dashboard`)
Retorna:
- proximos_agendamentos (limite 5)
- historico_recente (limite 5) – atendimentos anteriores
- documentos_publicados_recentemente (limite 5)
- fotos_recentemente_adicionadas (limite 6, somente meta + thumbs)
- estatisticas agregadas (contagens básicas)

### 6.7 Fluxos Principais
1. Login → redireciona para dashboard.
2. Listar slots → reservar → aguardar confirmação / auto confirmar.
3. Cancelar dentro da janela -> status `cancelado_cliente`.
4. Ver histórico atendimentos (somente campos públicos – anotações sensíveis excluídas).
5. Acessar documentos marcados `publicado_cliente=True` (download via URL assinada curta, futuro).
6. Visualizar galeria de fotos (derivados) com restrição de número por página (`PORTAL_CLIENTE_FOTOS_PAGE_SIZE`).

### 6.8 Segurança de Exposição
- Serializer portal remove campos internos (hash_arquivo, tamanho_arquivo, imagem original).
- Rate limit endpoints criação (agendamento) e cancelamento.
- Auditoria de acesso a mídia (fase 2) grava `AuditLogPortal` evento VIEW_MEDIA.

### 6.9 Métricas Portal Cliente
Counters prefixo `portal_`: dashboard hits, listagens, criação de agendamentos, cancelamentos, erros validação.
Histogram: latência por view.
Gauge: clientes_ativos, agendamentos_pendentes.

### 6.10 Evoluções Futuras
- Mensageria segura (threads) entre cliente e staff.
- Exportação de dados (portabilidade LGPD).
- Payment integration (gateway) e assinatura documental.
- Theming por tenant.

## 7. Módulo de Cotações
### 7.1 Modelos Propostos
- `Cotacao(tenant, codigo, titulo, descricao, status, data_abertura, data_encerramento, criado_por)`
- `CotacaoItem(cotacao, produto|descricao_texto, quantidade, unidade, especificacao)`
- `PropostaFornecedor(cotacao, fornecedor, status, enviado_em, total_estimado, validade_proposta, observacao)`
- `PropostaFornecedorItem(proposta, item_cotacao, preco_unitario, prazo_entrega_dias, observacao)`

### 7.2 Status
| Entidade | Status | Regras |
|----------|--------|--------|
| Cotacao | aberta, aguardando_decisao, encerrada, cancelada | aberta aceita novas propostas |
| PropostaFornecedor | rascunho, enviada, selecionada, recusada | enviada só edita se reaberta |

### 7.3 Regras de Negócio
- Apenas fornecedor homologado + portal_ativo pode enviar proposta.  
- Seleção de proposta marca cotação como `aguardando_decisao` (se múltiplos lotes) ou `encerrada`.  
- Reabrir cotação gera versão incremental (log).  
- Garantir integridade: unique (cotacao, fornecedor) em proposta ativa.  

## 8. Interações Entre Módulos
| De | Para | Uso |
|----|------|-----|
| Cotações | Fornecedores | Consulta homologação/portal_ativo antes de aceitar proposta |
| Agenda | Clientes | Lista slots filtrados por tenant/módulo ativo |
| Estoque | SolicitaçãoMaterialExterno | Liberação/baixa de itens |
| Permissões | Todos | Verifica escopos (tenant + papel + overrides) |

## 9. Modelo de Dados (Descrição Textual)
```
CustomUser 1---1 PerfilUsuarioEstendido
CustomUser N---N Tenant (via TenantUser)
Fornecedor 1---N AcessoFornecedor ---1 CustomUser
Cliente    1---N AcessoCliente    ---1 CustomUser
Cotacao 1---N CotacaoItem
Cotacao 1---N PropostaFornecedor 1---N PropostaFornecedorItem
Fornecedor 1---N PropostaFornecedor
Cliente 1---N Agendamento (proposto)
Fornecedor 1---N SolicitacaoMaterialExterno (Fase 2)
```

## 10. Endpoints / Views Planejados (Resumo)
| Área | Método | Rota | Descrição |
|------|--------|------|-----------|
| Fornecedor Portal | GET | /fornecedor/portal/ | Dashboard fornecedor |
| Fornecedor Portal | GET/POST | /fornecedor/auto-cadastro/ | Auto registro (F3) |
| AcessoFornecedor | POST | /fornecedor/{id}/ativar/ | Admin ativa portal |
| Cotações | GET | /cotacoes/ | Lista cotações abertas |
| Cotações | GET/POST | /cotacoes/{id}/proposta/ | CRUD proposta fornecedor |
| Cotações | POST | /cotacoes/{id}/selecionar-proposta/{pid}/ | Seleção admin |
| Clientes Portal | GET | /cliente/portal/ | Dashboard cliente |
| Agenda | GET/POST | /cliente/agenda/agendar/ | Criar agendamento |
| Agenda | POST | /cliente/agenda/{id}/cancelar/ | Cancelar agendamento |
| Solicitação Material | GET/POST | /fornecedor/solicitacoes/ | (Fase 2) |

## 11. Componentes de UI
| Página | Componentes |
|--------|------------|
| Dashboard Fornecedor | Resumo cotações, documentos pendentes, status homologação |
| Form Proposta | Tabela itens (preço, prazo), total dinâmico, upload anexo opcional |
| Auto-cadastro | Wizard: Dados Básicos → Documentos → Confirmação |
| Dashboard Cliente | Próximos agendamentos, histórico, atalhos serviços |
| Agenda Seleção | Calendário/slots + filtros profissional/serviço |
| Solicitação Material | Lista materiais, quantidades, justificativa |

## 12. Fluxos Detalhados
### 12.1 Auto‑Cadastro Fornecedor
1. Usuário acessa rota pública.  
2. Preenche dados mínimos (CNPJ/CPF, razão/nome, contato principal, e‑mail).  
3. Sistema cria Fornecedor(status_homologacao=pendente, portal_ativo=False) + User + Perfil + AcessoFornecedor(ativo=False).  
4. Email de confirmação + fila para homologação.  

### 12.2 Convite Fornecedor Existente
1. Admin gera convite → email com token.  
2. Fornecedor segue link, autentica/cria senha → vincula a Fornecedor existente via CNPJ.  
3. Cria AcessoFornecedor (ativo se homologado; caso contrário aguardando).  

### 12.3 Envio Proposta Cotação
1. Fornecedor abre cotação aberta.  
2. Preenche preços + prazos → salva rascunho.  
3. Validação de campos obrigatórios → enviar.  
4. Gera snapshot itens, bloqueia edição (salvo reabertura).  

### 12.4 Seleção de Proposta
1. Admin vê ranking (menor preço ou critérios).  
2. Seleciona proposta → altera status + encerra ou transita.  
3. (Futuro) Gera Pedido de Compra.  

### 12.5 Agendamento Cliente
1. Cliente acessa agenda.  
2. Filtra por profissional/serviço.  
3. Escolhe slot livre → cria registro.  
4. Recebe confirmação ou fica pendente (política).  
5. Pode cancelar se antecedência >= limite.  

### 12.6 Solicitação Material (Fornecedor Terceirizado) – Fase 2
1. Fornecedor (prestador) abre formulário.  
2. Seleciona itens estoque + quantidades.  
3. Fluxo aprovação (status pendente → aprovado/rejeitado).  
4. Aprovado gera movimento estoque (saida/vinculação).  

### 12.7 Fluxo Mídia Cliente (Novo)
1. Upload de mídia ocorre em contexto staff (atendimento).  
2. Tasks Celery geram thumbnail, webp e (se vídeo) poster + transcode.  
3. Portal Cliente lista apenas registros concluídos (`thumbnail` pronto).  
4. Solicitação de reprocessamento (derivados) somente staff via endpoint protegido.  
5. Acesso vídeo condiciona validação prévia de duração/resolução (task `validar_video`).  

### 12.8 Fluxo Observabilidade / Health
1. `/metrics` expõe counters/summary/histogram.  
2. Portal adiciona labels `portal_view` para agrupamento.  
3. Health endpoint (futuro) checa: DB, Redis, ffmpeg disponível, backlog filas (`celery_inspect`).  

## 13. Regras de Negócio (Consolidadas)
8. Portal Cliente: Mídia exibida apenas se derivativos gerados; vídeos não aprovados em validação são ocultos.  
9. Slot de agenda não pode ser reservado se já bloqueado (race resolvido por transação).  
10. Circuit breaker de transcodificação impede novas tentativas após N falhas consecutivas até resfriamento (persistência Redis).  
11. Permissão portal cliente nunca sobrepõe deny explícito da camada PermissaoPersonalizada.
1. Fornecedor deve estar homologado e portal_ativo para enviar proposta.  
2. Proposta rascunho não participa de ranking.  
3. Cancelar cotação só se nenhuma proposta selecionada.  
4. Cliente só visualiza/agenda serviços marcados como `disponivel_online`.  
5. Janela de cancelamento definida por configuração tenant (ex: 24h).  
6. Solicitação material só para fornecedor tipo_fornecimento inclui SERVICOS/AMBOS.  
7. Permissão granular: ação negada explícita (PermissaoPersonalizada concedida=False) prevalece.  

## 14. Permissões e Segurança
Camada Permission Resolver (Atualizado):
1. Checagem estado conta (ativo / bloqueado / portal_ativo / homologação).  
2. Deny explícito (PermissaoPersonalizada scoped) > Allow explícito.  
3. Roles do Tenant agregam permissões base (cache local por request).  
4. Papel derivado (AcessoFornecedor / ContaCliente) injeta claims padrão (ex: SUBMIT_PROPOSTA, VIEW_DASHBOARD_CLIENTE).  
5. Defaults de módulo (fallback).  

Cache: mapa (tenant_id, user_id, version_stamp) -> estrutura de permissões; invalidar em alteração relevante.

Auditoria adicional: gravar eventos chave (LOGIN_PORTAL, VIEW_DOCUMENTO, DOWNLOAD_DOCUMENTO, VIEW_FOTO, CREATE_AGENDAMENTO, CANCEL_AGENDAMENTO, SUBMIT_PROPOSTA, SELECT_PROPOSTA).
Hierarquia de decisão (topo = maior precedência):
1. Bloqueio de Conta (status fornecedor/cliente ou bloqueado_ate).  
2. PermissaoPersonalizada (deny > allow) – agora com `scope_tenant`.  
3. Role do Tenant (via TenantUser).  
4. Papel implícito via AcessoFornecedor/AcessoCliente (ex: portar permissões base).  
5. Defaults de módulo.  

Controles adicionais:
- Rate limit uploads documentos (config).  
- Auditoria de eventos críticos (envio proposta, seleção proposta, homologação).  
- Sanitização de inputs (preço >= 0, prazos positivos).  

## 15. Migração & Implantação (Passo a Passo)
Fase 1 (Atualizada):
1. Criar `AcessoFornecedor` + campo `portal_ativo` em Fornecedor.  
2. Criar modelos cotações (Cotacao, CotacaoItem, PropostaFornecedor, PropostaFornecedorItem).  
3. Adicionar `scope_tenant` em PermissaoPersonalizada (se aprovado).  
4. Implementar Permission Resolver com precedência.  
5. Services cotações + testes unidade (status transitions).  

Fase 2:
6. Implementar Portal Cliente (model `ContaCliente` + dashboard read‑only + listagens).  
7. Integração agenda (slots + criação agendamento pendente).  
8. Serializers de mídia derivativa portal (safe).  
9. Métricas portal (counters + histogram).  

Fase 3:
10. SolicitaçãoMaterialExterno + integração estoque.  
11. Circuit breaker persistente (já base) + health endpoint.  
12. Auditoria portal (AuditLogPortal).  

Fase 4:
13. Auto‑cadastro fornecedor + workflow homologação automatizado.  
14. Threads mensagens cliente & fornecedor (mensageria unificada opcional).  

Fase 5:
15. Subcontas fornecedor / colaboradores + granularidade permissões.  
16. URLs assinadas documentos + política expiração.  

Fase 6:
17. Participação unificada (ParticipacaoUsuario) e refator AcessoX.  
18. External storage (S3) e CDN para mídia pesada.  

Fase 7:
19. Pagamentos / assinatura eletrônica / theming avançado.  
20. Exportação / portabilidade LGPD.  

## 16. Roadmap (Timeline Indicativa)
| Fase | Duração Est. | Entregáveis Chave |
|------|--------------|-------------------|
| 1 | 1-2 sprints | AcessoFornecedor, Cotações MVP, permissões escopo tenant |
| 2 | 1 sprint | Solicitação Material + integração estoque |
| 3 | 1 sprint | Auto-cadastro + homologação workflow |
| 4 | 1-2 sprints | Portal Cliente agenda |
| 5 | 1 sprint | Subcontas fornecedor |
| 6 | 2 sprints | Participação unificada + migração |

## 17. Métricas de Sucesso
Adicionais (Portal Cliente / Mídia / Observabilidade):
- % agendamentos auto‑serviço confirmados sem intervenção manual.
- Tempo médio geração derivados mídia (p50/p95). 
- Falhas de transcodificação por 100 uploads vídeo. 
- Latência média (p95) endpoints portal críticos (< 300ms). 
- Erros 5xx portal (< 0.5%). 
- % Fornecedores homologados que enviaram ao menos 1 proposta (meta inicial ≥ 30% em 90 dias).  
- Tempo médio ciclo cotação (aberta → seleção).  
- Taxa de conversão auto‑cadastro aprovado (≥ 60%).  
- Erros 4xx/5xx em endpoints cotações (< 1% das requisições).  
- SLA resposta permissão < 5ms médio (cache local).  
- Aderência testes: cobertura > 80% em domínio cotações.  

## 18. Plano de Testes
Portal Cliente (novos):
- Acesso somente derivativos. 
- Tentativa acessar mídia original → 403. 
- Reserva concorrente de slot (testa race). 
- Cancelamento fora da janela → 400. 
- Limite de agendamentos pendentes ativo. 

Mídia / Tasks:
- Sucesso transcodificação reduz tamanho >15%. 
- Circuit breaker bloqueia após N falhas simuladas. 
- Métricas expõem counters incrementados. 
### 18.1 Unit
- Modelos: validação status transitions (Cotacao, PropostaFornecedor).  
- permission_resolver precedence (deny > allow > role).  
- Cálculo total proposta (somatório itens).  

### 18.2 Integração
- Fluxo completo criar cotação → fornecedor envia proposta → seleção.  
- Bloqueio fornecedor não homologado.  
- Cancelamento cotação sem propostas selecionadas.  
- Agendamento cliente com janelas válidas.  

### 18.3 E2E (Selenium / Playwright futuramente)
- Auto-cadastro fornecedor.  
- Envio proposta com itens.  
- Cliente agenda e cancela.  

### 18.4 Segurança
- Tentativa de acessar proposta de outro fornecedor (403).  
- Injeção de preço negativo (validação).  
- Escalada de permissões negada (deny).  

## 19. Riscos e Mitigações
| Uso indevido mídia original | Vazamento dados sensíveis | Filtrar campos no serializer portal + testes obrigatórios |
| Backlog filas media/video | Latência derivativos | Escalar workers dedicados + gauge backlog + alertas |
| Circuit breaker não persiste restart | Loop falha contínua | Persistência Redis + TTL (implementado Fase 3) |
| Exposição endpoints sem rate limit | Abusos / DoS leve | Configurar throttling DRF + limites adaptativos |
| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Complexidade permissão | Acesso indevido | Resolver precedência clara + testes |
| Crescimento logs | Storage | Rotina limpeza + index apropriado |
| Reabertura cotação sem versionamento | Perda histórico | Auditar transições + version tag |
| Auto-cadastro spam | Carga moderação | Captcha / throttle / validação CNPJ |
| Duplicidade cargo/salário | Dados inconsistentes | Plano de depreciação campos perfil |

## 20. Glossário
- **Cotação**: Processo competitivo para obtenção de preços/prazos.  
- **Proposta**: Resposta formal do fornecedor à cotação.  
- **Homologação**: Aprovação interna da empresa para permitir interação avançada do fornecedor.  
- **Portal**: Interface externa controlada (fornecedor/cliente) para operações específicas.  
- **Participação**: Relacionamento genérico futuro entre usuário e entidade de domínio.  

## 21. Próximos Passos Imediatos (Após Aprovação deste Documento)
1. Validar nomenclatura `ContaCliente` vs `AcessoCliente` (decisão final).  
2. Aprovar inclusão dos campos de mídia seguros listados para portal.  
3. Confirmar políticas iniciais: limites cancelamento / janela máxima / limite agendamentos pendentes.  
4. Aprovar precedence Permission Resolver e cache design.  
5. Iniciar implementação Fase 1 (cotações + fornecedor acesso).  
6. Definir métricas SLO portal (latência, erro) para acompanhar a partir da Fase 2.  

---
Fim do documento.
