# Migração 0012 - Campo extra_json em LogAtividadeUsuario

## Resumo
Introduz campo `extra_json` para armazenamento estruturado (JSON) de metadados adicionais no log de atividades.

## Ações Necessárias
1. Aplicar migração em todos os ambientes:
   - `python manage.py migrate`
2. Validar após deploy:
   - Criar evento de log que utilize `extra_json` (ex: via função utilitária de logging em lote).
   - Verificar no admin ou direto no banco se valor JSON foi persistido.

## Compatibilidade
- Campo é opcional (null=True, blank=True) evitando falhas em registros antigos.
- Leituras antigas continuam funcionando (atributo retorna None se vazio).

## Uso Exemplo
```python
log.extra_json = {"origin": "permission_resolver", "cache_hit": True, "ttl": 42}
log.save(update_fields=["extra_json"])
```

## Próximos Passos (Opcional)
- Index GIN se Postgres para consultas JSON complexas.
- Sanitização de chaves sensíveis antes de persistir.
