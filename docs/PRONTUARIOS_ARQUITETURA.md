# 🏥 Arquitetura do Módulo Prontuários (Pós-Remoção de Paciente)

> [!WARNING]
> **Módulo de Agendamento Obsoleto**: As funcionalidades de agendamento, disponibilidade e slots descritas neste documento (`AtendimentoDisponibilidade`, `AtendimentoSlot`) foram substituídas pelo novo módulo `agendamentos`. A documentação de referência para a nova arquitetura se encontra em **[MODULO_AGENDAMENTOS.md](./MODULO_AGENDAMENTOS.md)**. Este documento permanece como referência para as demais funcionalidades do prontuário (Perfil Clínico, Anamnese, etc.).

## 1. Contexto e Objetivo
O módulo `prontuarios` consolidou o antigo modelo `Paciente` nas entidades centrais do domínio de clientes (`clientes.Cliente`, `clientes.PessoaFisica`) e o perfil clínico (`prontuarios.PerfilClinico`). Este documento descreve a arquitetura atual após a desativação completa do modelo `Paciente` e seus fluxos associados.

## 2. Modelos Principais

### Cliente / Pessoa Física (app `clientes`)
- `Cliente`: Entidade comercial genérica (PF ou PJ) multi-tenant.
- `PessoaFisica`: Atributos pessoais (nome completo, CPF, sexo, nascimento, profissão) vinculados a um `Cliente` tipo PF.

### Modelos Clínicos (apps `prontuarios` e `servicos`)
- `PerfilClinico` (prontuarios): Informações permanentes de histórico clínico de um cliente PF.
- `Servico` (servicos): Catálogo de serviços possíveis (nome, preço base, categoria, requisitos) multi-tenant.
- `ServicoClinico` (servicos): Especialização/atributos clínicos do serviço (ex.: duração estimada, flags)
- `Atendimento` (prontuarios): Execução agendada ou realizada de um serviço para um cliente PF (estado, timestamps, profissional responsável, anotações, anexos).
- `Anamnese` (prontuarios): Registro estruturado adicional (questionário) vinculado ao cliente / perfil.
- `FotoEvolucao` (prontuarios): Imagens de evolução clínica associadas a um atendimento ou perfil.

### Relações (simplificado)
```
Cliente(PF) ─1─1→ PessoaFisica ─1─?→ PerfilClinico ─1─*→ Atendimento ─1─*→ FotoEvolucao
                                        │                    │
                                        │                    └─*→ Anamnese (opcional / complementar)
                                        └─*→ Anamnese (se ligada diretamente ao perfil)

Profissional(User) ─1─*→ Atendimento
```

## 3. Fluxos Operacionais

### 3.1 Execução de Atendimento
1. Atendimento muda de estados: `agendado → em_andamento → concluido / cancelado`.
2. Durante execução: criação de `FotoEvolucao` (upload) e `Anamnese` (se aplicável).
3. Geração posterior de relatórios mensais agregando estatísticas por serviço.

### 3.2 Upload e Processamento de Fotos (`FotoEvolucao`)
- Upload via formulário web ou endpoint móvel (`upload_foto_evolucao_mobile`).
- Tarefas assíncronas geram derivados (thumbnail, webp, hash) – filas Celery (fila `media`).
- Reprocessamento possível via tarefa `reprocessar_derivados_foto`.

### 3.3 Relatório Mensal
- Função `enviar_relatorio_mensal(tenant_id)` coleta atendimentos do mês anterior.
- Mantém chave `total_pacientes` por compatibilidade antiga, mas fonte agora é `clientes`.

## 4. Tarefas Assíncronas (Celery)
| Tarefa | Fila | Função |
|--------|------|--------|
| gerar_derivados_foto / reprocessar_derivados_foto | media | Processamento de imagens |
| validar_video / extrair_video_poster (quando aplicável) | video | Processamento de mídia rica |
| enviar_relatorio_mensal | default | Relatórios mensais por tenant |
| verificar_atendimentos_pendentes | default | Notificações de clientes inativos |
| limpar_arquivos_temporarios | default | Housekeeping de mídia |

Tarefas legadas de paciente (backup, relatórios específicos) foram eliminadas; placeholders residuais retornam vazio para compatibilidade de chamadas externas que possam persistir temporariamente.

## 5. Permissões e Segurança
- Escopo multi-tenant: todos os modelos clínicos amarrados ao `tenant` via cadeia de chaves (Cliente → Tenant).
- Restrições típicas:
  - Profissional só acessa atendimentos onde é responsável ou conforme política futura (ex.: equipe). 
  - Superusuários podem acessar globalmente.
- A remoção de `Paciente` simplifica o grafo de autorização (cliente unifica contexto comercial + clínico PF).

## 6. API (DRF)
Prefixo: `/prontuarios/api/`

| Endpoint | ViewSet/Função | Descrição |
|----------|-----------------|-----------|
| `atendimentos/` | `AtendimentoViewSet` | CRUD + filtros por cliente / datas |
| `fotos-evolucao/` | `FotoEvolucaoViewSet` | Listagem / criação de fotos ligadas a atendimento |
| `anamneses/` | `AnamneseViewSet` | Questionários clínicos |
| `perfis-clinicos/` | `PerfilClinicoViewSet` | Histórico clínico consolidado |
| `mobile/upload-foto/` | função | Upload rápido mobile |
| `search/clientes/` | função | Busca Select2 de clientes do tenant atual |
| `search/procedimentos/` | função | Compat: busca Select2 retornando Serviços (com extras de compatibilidade) |
| `search/profissionais/` | função | Busca Select2 de profissionais; padrão `staff_only=1` (enviar `staff_only=0` para incluir todos) |

Campos legados / chaves de contexto retornados para compatibilidade estão marcados internamente com comentários (ex.: `total_pacientes`).

## 7. Estratégia de Migração (Resumo)
1. Congelamento de escrita no modelo `Paciente`.
2. Criação / consolidação de `Cliente` + `PessoaFisica` + `PerfilClinico`.
3. Migração (script `migrar_pacientes_para_clientes`) – agora desativado e marcado para remoção definitiva.
4. Atualização de serializers, views, permissões e tasks.
5. Remoção de templates e rotas de paciente; redirecionamentos temporários removidos nesta fase final.
 6. Substituição completa de `Procedimento` por `Servico/ServicoClinico` (app `servicos`) em modelos, formulários, templates e integrações.

## 8. Decisões Arquiteturais
- Unificação reduz duplicidade de dados pessoais (evita divergência entre Cadastro Comercial e Paciente).
- `PerfilClinico` isola atributos sensíveis mantendo base de cliente genérica reutilizável em módulos não clínicos.
- Derivados de mídia tratados de forma idempotente para suportar reprocessamentos.
- Filas separadas (`media`, `video`) evitam starvation de tarefas críticas de relatório.

## 9. Próximos Passos (Evolução Planejada)
- Indexação full-text de anotações de atendimento (busca clínica avançada).
- Auditoria estruturada por campo (diferenças em PerfilClinico / Anamnese).
- Implementar locking otimista em edição simultânea de atendimentos.
- Suporte a anexos genéricos (PDF / laudos) vinculados a atendimento.

## 10. Glossário Rápido
- Atendimento: Sessão clínica individual (realizada ou agendada).
- Perfil Clínico: Dados clínicos permanentes / históricos do cliente PF.

---
Documento mantido: Atualize ao introduzir novos campos estruturais ou fluxos.

## 11. Status de Modernização (feito vs. faltante)

Feito (implementado no código):
- Remoção completa do modelo Paciente; vínculo por `clientes.Cliente` + `PessoaFisica` + `PerfilClinico`.
- Filtro multi-tenant aplicado em ViewSets e ListViews (via `get_current_tenant`/mixins).
- Disponibilidade/Slots clínicos: geração e reserva com lock transacional e liberação em cancelamento.
- Integração com `agenda.Evento` (criar/atualizar/cancelar) a partir de `Atendimento`.
- Upload de `FotoEvolucao`: geração de `thumbnail` e `WEBP` assíncronos; validação e transcodificação de vídeo com métricas.
- Permissões baseadas em profissional/superuser/secretaria (heurística) e classes DRF dedicadas.
- Templates criados para Anamnese (list/detail/form), Perfil Clínico, Atendimento e Fotos. Templates de Procedimento foram descontinuados e a navegação aponta para o módulo de Serviços Clínicos.
- Endpoints mobile: `upload_foto_evolucao_mobile` com restrições de acesso.
- Partial `_form_actions.html` presente e reutilizável.
- Select2/AJAX: endpoints `search/clientes`, `search/procedimentos` (compat: retorna Serviços com extras), `search/profissionais` e integração em formulário de Atendimento.
- Quick-create de Procedimento: REMOVIDO. Utilizar criação/edição de Serviço Clínico no módulo `servicos`.
 - UX: Mensagens de sucesso via Django messages exibidas como alert e toast (PandoraNotif.toast) após criar/atualizar/cancelar atendimentos.
 - Update: Auto-liberação do slot quando o status muda para `CANCELADO` (transacional, segura contra corrida).
 - API Slots: quando não há disponibilidade para a data, retorna `[]` (coberto por teste unitário dedicado).

Faltante/Pendências:
- Sidebar resumo dinâmica em Atendimento (dados e validações inline mais ricas).
- Regras de edição de Atendimento com troca de slot: backend pronto; melhorar UX e validação de conflitos na UI.
- Métricas de UX (time-to-first-save, abandono) e logs de UI.
- KPIs clínicos: ocupação por profissional, lead time, no-show rate (exige status futuro).
- Documentar e cobrir com testes o fluxo de reagendamento total (inclui liberar/reatribuir slots e eventos).
- Unificar docs `MODULE_PRONTUARIOS.md` e plano legado (mover legacy para `docs/legacy`).
 - Adicionar teste de transição de status para `CANCELADO` cobrindo liberação automática de slot.

## 12. Próximos Passos Sugeridos
1) UI: Select2 de Serviços Clínicos; sidebar resumo em Atendimento.
2) UX: Reagendamento com troca de slot assistido (confirm dialog + validação client-side).
3) Observabilidade: métricas de UI e KPIs clínicos básicos em relatório.
4) Testes: cenários de slot troca/rollback e upload vídeo inválido (limites), e permissionamento de Perfil Clínico.
