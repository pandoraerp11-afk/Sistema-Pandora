# Agendamentos – Notas de API (pós-migração Serviço)

- Parâmetro padrão: usar `servico` ou `servico_id` nos endpoints (query/body).
- Select2 / listagem de slots/agendamentos respeitam `servico_id`.
- Evento espelho (agenda.Evento) padronizado: `tipo_evento='servico'`. O valor legado `'procedimento'` permanece apenas para leitura/compat em instâncias antigas até remoção final.
- Respostas incluem `servico_nome` onde aplicável; serializer carrega `servico.nome_servico`.

## Exemplos rápidos
- GET `/agendamentos/api/slots/?profissional=...&servico=123&data=YYYY-MM-DD`
- POST `/agendamentos/api/agendamentos/` com JSON `{ "cliente":1, "profissional":2, "data_inicio":"...", "servico":123, "origem":"PROFISSIONAL" }`
