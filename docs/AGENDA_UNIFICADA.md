# Agenda Unificada: Centralização no módulo Agendamentos

Este documento descreve o estado atual da integração entre Prontuários e Agendamentos.

## Objetivo

- Tornar o módulo Agendamentos a única fonte de verdade para disponibilidade e capacidade de slots.
- Evitar manipulações de capacidade (reservar/liberar) a partir de Prontuários.

## O que mudou

- Prontuários não incrementa ou decrementa capacidade de `AtendimentoSlot` em Create/Update/Delete nem em `Atendimento.save()`.
- `Atendimento.liberar_slot_se_cancelado()` tornou-se no-op.
- DRF (AtendimentoViewSet) apenas salva dados clínicos e cria/atualiza `Evento` na agenda; não altera slots.
- Formulários de `Atendimento` ocultam o campo `slot` quando `AGENDA_UNIFICADA=True` (default), exigindo `data_atendimento` ou a integração com o novo fluxo.

## Compatibilidade

- O modelo legado `AtendimentoSlot` permanece para compatibilidade de dados, porém todas as listas/consultas devem usar os endpoints do módulo Agendamentos (`agendamentos:slot-list`, `agendamentos:disponibilidade-list`). Não há mais endpoint de compatibilidade em Prontuários.

## Indicadores/Logs

- `AtendimentoSerializer.get_slot_info()` emite um log em nível DEBUG quando encontra `slot_id`, para monitorar usos legados.

## Próximos passos sugeridos

1. Remover gradualmente referências diretas a `AtendimentoSlot` de templates e forms quando a migração estiver completa.
2. Criar redirects/bridges no Agendamentos para consultas de disponibilidade atuais.
3. Deprecar e, por fim, remover `AtendimentoDisponibilidade`/`AtendimentoSlot`, transferindo testes para o módulo Agendamentos.

