# Limpeza de resíduos de "procedimento"

- Verifique se o arquivo `procedimento_servico_map.json` existe na raiz e remova-o após confirmar migrações aplicadas.
- Execute auditoria de agenda: `python manage.py audit_evento_tipo_procedimento`.
- Quando a auditoria apontar 0 por 14 dias, rode: `python manage.py migrate_evento_tipo_procedimento_to_servico` e em seguida remova o choice legado via migração de modelo.
