# Prontuários – Notas de API (pós-migração para Serviços)

- Substituição de parâmetro: use `servico_id` no lugar de `procedimento_id` em todos os fluxos.
- Endpoints Select2 mantidos neste módulo:
  - `/prontuarios/api/search/clientes/`
  - `/prontuarios/api/search/profissionais/` (padrão `staff_only=1`; envie `staff_only=0` para incluir todos os usuários do tenant)
- Busca de serviços: utilize os endpoints do módulo `servicos`.
- Quick-create de procedimento/removido: crie serviços exclusivamente pelo módulo `servicos/`.

## Exemplos

- Clientes: `GET /prontuarios/api/search/clientes/?q=ana&page=1&page_size=20`
- Profissionais: `GET /prontuarios/api/search/profissionais/?q=jo&page=1&page_size=20&staff_only=1`