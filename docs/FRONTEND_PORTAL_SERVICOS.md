# Frontend Portal - Serviços e Serviços Clínicos

Atualizado: 2025-09-11

## Objetivo
Centralizar parâmetros, eventos e contratos de UI usados pelo portal/administrativo para exibir e interagir com `servicos.Servico` e o perfil clínico (`ServicoClinico`).

## 1. Campos Principais (Servico)
| Campo | Input name | Tipo | Observações |
|-------|------------|------|-------------|
| nome_servico | nome_servico | text | Obrigatório |
| tipo_servico | tipo_servico | select | OFERTADO ou RECEBIDO (bloqueado após criação) |
| preco_base | preco_base | decimal | Pode ser referência se RECEBIDO |
| regra_cobranca | regra_cobranca | select | Aplica cálculo dinâmico (JS futuro) |
| is_clinical | is_clinical | checkbox | Toggle do bloco clínico |
| ativo | ativo | checkbox | Controla visibilidade/catalogo |

## 2. Bloco Clínico (visível se is_clinical=True)
Campos renderizados via `ServicoClinicoForm` (prefixo `clinico-`):
| Campo | Input name real | Formato | Regras |
|-------|------------------|---------|--------|
| Duração Estimada | clinico-duracao_estimada | HH:MM ou HH:MM:SS | Obrigatório se clínico |
| Intervalo Mínimo entre Sessões | clinico-intervalo_minimo_sessoes | inteiro (dias) | Default 7 |
| Requisitos Pré-Procedimento | clinico-requisitos_pre_procedimento | texto | Opcional |
| Contraindicações | clinico-contraindicacoes | texto | Opcional |
| Cuidados Pós-Procedimento | clinico-cuidados_pos_procedimento | texto | Opcional |
| Requer Anamnese | clinico-requer_anamnese | boolean | Default True |
| Requer Termo Consentimento | clinico-requer_termo_consentimento | boolean | Default True |
| Permite Fotos Evolução | clinico-permite_fotos_evolucao | boolean | Default True |

## 3. Comportamento JS Atual
Arquivo: `servicos/servico_form.html` (bloco extra_js)
- Ao alterar `#id_is_clinical`, mostra/oculta o container `#bloco-clinico`.
- Na submissão, se clínico e `#id_clinico-duracao_estimada` vazio, bloqueia e mostra feedback inline.

Pendentes:
- Debounce para cálculo futuro de preço contextual.
- Tooltips de ajuda para flags clínicas.
- Mensagens acessíveis ARIA para exibição dinâmica.

## 4. Permissões de Agendamento Clínico
Função central: `shared.permissions_servicos.can_schedule_clinical_service(user, servico)`.
Regras (resumo):
1. Serviço deve ser clínico e ativo.
2. superuser ou staff autorizado direto.
3. Grupo contendo 'secretaria' concede.
4. Cliente portal: apenas se `disponivel_online=True` e não for staff/secretaria.
5. Caso contrário, negar.

Usar em futuras views/APIs antes de criar agendamento clínico.

## 5. Próximos Incrementos Planejados
| Item | Status |
|------|--------|
| Tooltips explicando campos clínicos | Pendente |
| Endpoint readonly JSON perfil clínico | Pendente |
| Tests E2E frontend (selenium/pytest-django) | Pendente |
| Revalidação dinâmica de HH:MM para duração | Pendente |

## 6. Boas Práticas
- Sempre validar no backend mesmo que haja validação JS.
- Nunca persistir perfil clínico se `is_clinical` desmarcado; backend já limpa (delete) — comportamento documentado.
- Usar `select_related('perfil_clinico')` quando listar serviços clínicos para evitar N+1.

## 7. Anti-Pattern a Evitar
- Duplicar campos clínicos direto no modelo `Servico`.
- Fazer inferência de clínica por categoria ao invés de `is_clinical`.
- Alterar defaults dos campos clínicos sem aprovação formal.

---
Este documento deve ser atualizado sempre que novos elementos de UI ou endpoints forem adicionados ao fluxo de serviços clínicos.
