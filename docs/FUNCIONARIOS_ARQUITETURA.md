# Módulo de Funcionários (RH) - Arquitetura e Especificação Moderna

## Visão Geral
O módulo de Funcionários é a fundação operacional para gestão de capital humano dentro do Pandora ERP, servindo também como provedor de identidade profissional para fluxos clínicos (prontuários/atendimentos), financeiros (folha, benefícios, custo hora), materiais (responsabilidades) e auditoria (trilhas de alteração). Ele suporta múltiplos modelos de vínculo de trabalho e extensibilidade vertical.

## Objetivos Principais
1. Centralizar cadastro estruturado de pessoas em exercício profissional ("Funcionário"), mantendo integridade multi-tenant.
2. Unificar múltiplos tipos de vínculo laboral: CLT, contrato PJ, freelancer, tarefa/projeto, estágio, aprendiz, temporário, voluntário.
3. Sustentar cálculo de custo real (com encargos), folha simplificada e projeções.
4. Fornecer API estável (REST) + eventos internos para integração com módulos adjacentes.
5. Garantir governança: auditoria completa (quem alterou salário, quem aprovou férias, etc.).
6. Maximizar desacoplamento: regras de negócio concentradas em serviços/domain layer; views/serializers enxutos.

## Escopo Funcional
- Cadastro e ciclo de vida do funcionário (admissão → mudanças contratuais → desligamento).
- Modelagem de vínculos múltiplos (Funcionário pode ter 1:N contratos históricos coexistentes em timeline, evitando sobrescritas destrutivas).
- Estrutura salarial evolutiva (histórico granular com justificativa, responsável e impactos previstos).
- Jornada/Horário de trabalho flexível (fixo, turnos, banco de horas, escala rotativa, remoto híbrido).
- Frequência e apontamentos (cartão ponto, eventos extraordinários, justificativas, geo/microlocalização opcional).
- Férias, folgas, afastamentos, licenças (uniformizados como "Eventos de Ausência" com tipagem e políticas).
- Benefícios (recorrentes e pontuais), rateio por centro de custo e elegibilidade dinâmica.
- Dependentes para efeitos fiscais e de benefícios.
- Cálculos: INSS, FGTS, IRRF, provisões (13º, férias), custo hora total e incremental.
- API pública (tenant isolado) + actions especializadas.
- Web UI moderna (painéis analíticos, edição completa com formsets reativos, filtragem facetada, exportações CSV/Excel/JSON).
- Notificações (alteração salarial, aprovação férias, ponto não batido, documentos pendentes).

## Anti-Objetivos (Fora de Escopo Inicial)
- Folha oficial completa (eSocial, CAGED) – previsto para fase futura.
- Gestão profunda de saúde ocupacional (outro módulo dedicado).
- Workflow de recrutamento (pode integrar futuramente via outro app).

## Modelo de Domínio (Entidades Principais)
- Tenant (já existente).
- Funcionario
  - Identidade (user FK opcional), dados pessoais, situação atual.
  - Propriedades calculadas: idade, tempo_empresa, salario_atual.
- ContratoTrabalho (Novo)
  - funcionario FK, tipo_vinculo (ENUM), data_inicio, data_fim opcional, carga_base_horas, modelo_remuneracao (fixo, hora, tarefa, misto), status.
  - Campos específicos por tipo em tabela polimórfica ou JSON estruturado (ex: PJ: cnpj_prestador; Freelancer: valor_hora_negociado; Tarefa: valor_unidade, unidade_referencia).
- SalarioHistorico
  - contrato FK (não somente funcionário) para granularidade; remove ambiguidade quando há múltiplos vínculos.
  - data_vigencia, valor_salario / base_calculo, alterado_por, motivo_alteracao, origem (manual, reajuste_automatizado, importação).
- JornadaTrabalhoModelo
  - Regras reutilizáveis (escala 5x2, 12x36, turnos), versionamento.
- HorarioTrabalho
  - Instância aplicada ao contrato ou funcionário; overrides pontuais (data_especifica, motivo).
- ApontamentoPonto
  - Registro cru (timestamp, tipo, origem, coords, device_hash), integridade antifraude mínima.
- EventoAusencia (unificação de Ferias, Folga, Afastamento)
  - subtipo (FERIAS, FOLGA, LICENCA_MEDICA, MATERNIDADE, SUSPENSAO, TREINAMENTO, etc.), período, aprovadores, anexos.
- Beneficio
  - tipo_beneficio (VA, VR, VT, PLANO_SAUDE, BONUS, AUX_COMBUSTIVEL...), categoria (ALIMENTACAO, SAUDE...), valor (fixo ou fórmula), recorrente, centro_custo.
- Dependente
- RateioCusto (Novo – opcional)
  - contrato FK, centro_custo, percentual.
- ParametrosEncargos (Tabela de referência por ano/competência) para INSS, IRRF, FGTS, etc.
- LogAuditoriaRH (ou integração com auditoria genérica) – eventos semânticos.

## Extensões Futuras Planejáveis
- DocumentoObrigatorio (ex: CNH, ASO, Certificação) com vencimentos.
- PlanoCargosSalarios (faixas, steps, promoções).
- Engine de regras para elegibilidade de benefícios.
- Gamificação / Engajamento (pontuação por tarefas, compliance de ponto, etc.).

## Tipos de Vínculo e Atributos
| Tipo | Campos Específicos | Cálculo Custo | Observações |
|------|--------------------|---------------|-------------|
| CLT | regime_jornada, sindicato, categoria | Base + INSS + FGTS + provisões | Reajustes periódicos normatizados |
| PJ | cnpj_prestador, nota_fiscal_req | Valor faturado + impostos indiretos (estimados) | Sem encargos CLT diretos |
| Freelancer | valor_hora, limite_horas_mes | horas * valor_hora + taxa plataforma | Pode virar contrato se recorrente |
| Tarefa (piece-work) | unidade_referencia, valor_unidade | qtd * valor_unidade | Integrar com módulo de produção |
| Estágio | instituicao_ensino, nivel | Bolsa + auxílios | Encargos diferenciados |
| Aprendiz | programa, fase | Base reduzida | Regras específicas legais |
| Temporário | agencia_intermediadora, lote_contrato | Similar CLT porém com data_fim obrigatória | |
| Voluntário | termo_compromisso, escopo | Custo operacional (0 salarial) | Pode receber benefícios não monetários |

## Arquitetura Lógica
Camadas:
- Models (dados + constraints mínimas)
- Domain Services (regras complexas: cálculo encargos, projeções, validações cruzadas)
- Application Services / Use Cases (orquestram múltiplos serviços + persistência atômica)
- Serializers / Forms (transformação e validação de entrada superficial)
- Views/ViewSets (delivery layer HTTP)
- Signals / Event Bus (disparo de eventos para auditoria, notificações, integrações)
- Tasks (Celery) para cálculos assíncronos pesados (projeção anual de custos, importações em lote)

## Padrões Técnicos
- Enum centralizado para tipos de vínculo, subtipos de ausência, tipos de benefício.
- Soft delete opcional (flag ativo) + histórico imutável (SalarioHistorico nunca edita – cria nova versão).
- Idempotência em endpoints de registro de ponto (hash de janela temporal + tipo).
- Otimização de queries: índices compostos (tenant, funcionario_id), (contrato, data_vigencia DESC), (funcionario, data_inicio) para ausências.
- Uso de QuerySet.annotate para métricas (dias trabalhad os, horas saldo).
- Campos JSON estruturados para atributos específicos por vínculo (subdocument out-extensível) ou herança multi-table se regras divergirem muito.

## Fluxos Principais
1. Admissão:
   - Cria Funcionário (dados pessoais) → Cria ContratoTrabalho (tipo vinculo) → Cria SalarioHistorico inicial → Gera eventos (AUDIT_FUNCIONARIO_ADMITIDO).
2. Alteração Salarial:
   - Validação de permissão (role RH) → Cria novo SalarioHistorico com data_vigencia >= hoje → Enfileira recalculo provisões → Notificação.
3. Registro de Ponto:
   - POST /api/funcionarios/ponto/registrar → Domain service valida janela mínima (ex: 2 min) + coerência de sequência (entrada/saída) → Apontamento persistido → (Opcional) geovalidação.
4. Férias / Ausência:
   - Solicitação → Validação saldo adquirido → Aprovação dupla opcional → Geração de EventoAusencia → Atualização projeções custo.
5. Cálculo Custo Hora Atual:
   - Base salarial vigente + encargos proporcionais (INSS patronal, FGTS, provisões férias+13º rateadas) + benefícios rateáveis / carga mensal horas.
6. Desligamento:
   - Data fim contrato → trava criação de novos apontamentos após data → dispara revisão de pendências (férias não gozadas, benefícios ativos) → AUDIT_FUNCIONARIO_DESLIGADO.

## Estratégia de Cálculo (Encargos)
- Tabelas ParametrosEncargos versionadas por competência (ano-mês).
- Serviço CalculadoraFolha:
  - calcular_inss(base) → faixas + teto.
  - calcular_irrf(base, dependentes) → deduções dinâmicas.
  - calcular_fgts(base) → % fixo.
  - provisionar_ferias(base) → base/12 * fator (1/3 adicional se política).
  - provisionar_decimo_terceiro(base) → base/12.
  - total_encargos = soma(provisões + encargos diretos) → custo_total.
- Cache interno de faixas (in-memory + invalidado em mudança de competência).

## Segurança e Permissões
- Escopo por tenant obrigatório em todas as queries.
- Roles sugeridas: RH_ADMIN, RH_ANALISTA, GESTOR_DEPARTAMENTO, APONTADOR (apenas ponto), BENEFICIOS_MANAGER.
- Field-level permission (ex: salário visível apenas para RH_ADMIN e gestor do departamento).
- Auditoria: cada alteração crítica gera entrada em LogAuditoriaRH (timestamp, actor_user_id, objeto, diffs compactados, contexto IP/user-agent).

## API (Esboço)
- /api/funcionarios/ (CRUD) + filtros (ativo, departamento, tipo_vinculo, search=nome|cpf)
- /api/funcionarios/{id}/custos/
- /api/funcionarios/{id}/salarios/ (lista histórico) [POST cria nova vigência]
- /api/contratos/ (CRUD) – separa múltiplos vínculos
- /api/ausencias/ (FERIAS/FOLGA/etc.)
- /api/ponto/registrar/ (idempotente) + /api/ponto/relatorio/?funcionario=...&data_inicio=...&data_fim=...
- /api/beneficios/ (CRUD) + /api/beneficios/calcular-folha/?competencia=YYYY-MM
- /api/parametros-encargos/ (admin)
- /api/relatorios/custos-agregados/?departamento=...&competencia=...

## Métricas & Observabilidade
- Signals para Prometheus / OpenTelemetry: total_registros_ponto, tempo_medio_aprovacao_ferias, alteracoes_salarial_mensal.
- Logging estruturado (json) em tasks de cálculo massivo.
- Feature flags (ex: habilitar módulo de banco de horas experimental).

## Performance & Escalabilidade
- Uso de select_related / prefetch_related padrão em listas.
- Paginação consistente (page_size máximo controlado via setting).
- Partitionamento futuro possível em tabelas de apontamentos (por mês/ano) se volume crescer (>5M registros).
- Tarefas batch (recalcular provisões para todos funcionários) executadas off-peak.

## UX / UI Moderno
- Dashboard: KPIs (headcount, rotatividade, custo médio hora, distribuição vínculos, ausências hoje, alertas de documentos vencendo).
- Listas reativas (filtros facetados sem reload completo – HTMX ou Alpine.js / Stimulus leve).
- Formulário completo com tabs: Dados Pessoais | Contratos | Salário | Jornada | Benefícios | Ausências | Dependentes | Auditoria.
- Inline diff viewer para alterações salariais (modal comparativo).
- Exportação multi-formato (CSV, XLSX, JSONL) com limite seguro assíncrono (task + notificação download).

## Estratégia de Migração (Fases)
Fase 1 (Atual): Ajustes básicos: serializer histórico, AJAX moderno, router API.
Fase 2: Introdução ContratoTrabalho + refatorar SalarioHistorico para referenciar contrato.
Fase 3: Unificação Ferias/Folga em EventoAusencia (migração dados). Deprecar modelos antigos progressivamente.
Fase 4: Introduzir ParametrosEncargos + centralizar cálculos em services.
Fase 5: API avançada (relatórios custo, agregações) + otimizações de índice.
Fase 6: Observabilidade (métricas, logs estruturados), permissões field-level.
Fase 7: Recursos avançados (banco de horas, escalas complexas, engine benefícios dinâmica).

## Padrões de Código / Boas Práticas
- NÃO colocar lógica de cálculo em modelos (apenas helpers simples). Domain services dedicados.
- Ações que mutam salário sempre criam nova linha (event sourcing leve) – nunca update destrutivo.
- Validadores isolados em utils/validators_rh.py.
- Serializers somente marshalling; validações cruzadas complexas delegadas a services.
- ViewSets: não sobrescrever list/create onde possível; usar actions nomeadas para semântica (calcular_custos, registrar_ponto).
- Forms para UI – DRY replicando validações leves dos services.

## Auditoria & Compliance
- Hash de integridade (salário + data + alterado_por) para sinalizar manipulações atípicas.
- Retenção configurável de logs.
- Export conforme LGPD: endpoint para extrair bundle de dados de um funcionário (json + attachments).
- Pseudonimização opcional em ambientes de staging.

## Integrações
- Disparo de Webhooks (opcional) em eventos: funcionario.admitido, salario.alterado, ausencia.criada, ponto.registrado.
- Canal interno (ex: Redis Pub/Sub) para módulos internos (agenda clínica consumindo disponibilidade).

## Lista de Backlog Técnico Prioritário
1. Criar modelo ContratoTrabalho + migração.
2. Ajustar SalarioHistorico -> FK contrato.
3. Service de cálculo central (encargos, custo hora).
4. EventoAusencia consolidado (migrar dados de Ferias/Folga).
5. Endpoints dedicados de salários e ausências.
6. Permissões baseadas em role + field masking (salários).
7. Métricas Prometheus iniciais.
8. Export assíncrono.
9. Webhook dispatcher simples.
10. Testes automatizados (unit + API) cobrindo fluxos críticos.

## Critérios de Conclusão (MVP Evoluído)
- 100% endpoints críticos com testes (contrato, salário, ausência, ponto, benefícios).
- Zero acesso fora de tenant confirmado por testes de segurança.
- Cálculo de custo hora consistente dentro de margem ±1% para cenários de teste.
- Auditoria registra todas alterações salariais e contratuais com usuário e IP.
- Documentação atualizada e versionada (este arquivo + diagramas complementares quando aplicável).

---
Este documento serve como contrato de evolução. Próximo passo recomendado: implementar ContratoTrabalho e adaptar queries onde hoje assumem um único vínculo ativo (ex: get_salario_atual passa a consultar contrato vigente).
