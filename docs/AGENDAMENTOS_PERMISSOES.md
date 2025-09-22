# Permissões de Agendamento Clínico

Este documento descreve a função central de autorização para agendamentos de serviços clínicos e como ela é aplicada nas APIs.

## Função de Permissão

Arquivo: `shared/permissions_servicos.py`

```python
can_schedule_clinical_service(user, servico) -> bool
```

Retorna `True` se o usuário pode agendar o serviço clínico informado. A função NÃO deve ter a regra de negócio alterada sem aprovação explícita.

Regras atuais:
1. Serviço deve estar ativo e `is_clinical=True`.
2. Superuser sempre pode.
3. Usuário `is_staff` (profissional) pode.
4. Grupo que contenha `secretaria` no nome (case-insensitive) concede acesso.
5. Cliente portal: permitido se `servico.disponivel_online=True` e usuário não é staff/secretaria e tem grupo com `cliente` ou nenhum grupo especial.
6. Caso contrário, negado.

Mensagem padronizada (i18n): `CLINICAL_SCHEDULING_DENIED_MESSAGE`.

## Pontos de Enforcment nas APIs

Arquivo: `agendamentos/api_views.py`

Aplicada nas seguintes rotas:
- `POST /agendamentos/api/slots/{id}/reservar/` (staff / operador) – valida serviço clínico enviado.
- `POST /agendamentos/api/agendamentos/` (ModelViewSet create) – valida `servico_id`.
- `POST /agendamentos/api/cliente/slots/{id}/reservar/` (portal cliente) – valida `servico_id`.
- `POST /agendamentos/api/cliente/agendamentos/` – valida `servico_id`.

Quando negado retorna HTTP 403 (ou PermissionDenied DRF) com corpo:
```json
{"detail": "Sem permissão para agendar serviço clínico"}
```
A string é obtida de `CLINICAL_SCHEDULING_DENIED_MESSAGE` e traduzível via Django i18n.

## Boas Práticas
- Sempre usar `can_schedule_clinical_service` em qualquer novo fluxo de criação ou reserva que envolva serviços clínicos.
- Nunca duplicar lógica de permissão inline; reutilizar a função.
- Centralizar quaisquer futuras variações (flags, auditoria) dentro da função ou por decorators antes do enforcment.

### Nota sobre `IsClientePortal`
O permission `IsClientePortal` foi ajustado para tentar inferir o tenant a partir do `slot` (param `pk`) quando ainda não presente em sessão. Isso evita um 403 genérico precoce e permite que a mensagem padronizada de negação clínica seja retornada de forma consistente nas rotas de reserva (`cliente-slot-reservar`).

## Testes
Tests de unidade: `tests/shared/test_permissions_servicos.py`.

Tests de integração de API (novo): `tests/agendamentos/test_api_clinico_permissions.py` cobre cenários de autorização/negação em endpoints REST.

## Métricas de Negações (Observabilidade)
Uma métrica simples foi adicionada para contar negações clínicas:
- Chave de cache: `metric:clinical_schedule_denials` (expira após 1h sem incrementos).
- Incrementada sempre que `can_schedule_clinical_service` retorna `False`.
- Helper para debug/monitor: `shared.permissions_servicos.get_clinical_denials_count()`.

Uso sugerido:
1. Expor futuramente via endpoint admin ou integração Prometheus.
2. Reset controlado (ex.: `cache.delete('metric:clinical_schedule_denials')`) somente em manutenção.
3. Não utilizar para lógica de negócio; apenas telemetria.

## Roadmap Futuro
- Internacionalização completa das mensagens (incluir contexto em arquivos .po).
- Métricas Prometheus para contagem de negações clínicas.
- Feature flag para habilitar/desabilitar o módulo clínico.
