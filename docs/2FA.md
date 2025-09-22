## 2FA (TOTP) - Visão Geral

Endpoints (namespace `user_management`):

- POST `2fa_setup` – Inicia configuração. Retorna `secret`, `provisioning_uri` e **(uma única vez)** os `recovery_codes`. Se já habilitado e confirmado retorna `{"status": "already_enabled"}`.
- POST `2fa_confirm` – Confirma primeiro token. Body: `token`.
- POST `2fa_verify` – Verifica token em cada nova sessão / challenge. Body: `token` ou `recovery_code`.
- POST `2fa_disable` – Desabilita 2FA (requer usuário autenticado). Remove secret e códigos.
- GET  `2fa_challenge` – Página HTML de desafio (middleware redireciona para cá se necessário).

### Recovery Codes

Gerados 8 códigos aleatórios (hex uppercase) somente exibidos no `setup` inicial. Armazenados em hash. A partir desta versão:

- Se `settings.TWOFA_RECOVERY_PEPPER` estiver definido, os novos hashes usam formato `v2:<sha256>` com pepper.
- Códigos antigos (sem pepper) continuam válidos (compatibilidade em `use_recovery_code`).
- Repetir `setup` após confirmação não revela novamente os códigos.

### Segurança Adicional

- `twofa_passed` setado em sessão após verificação bem-sucedida (TOTP ou recovery code).
- Campo `failed_2fa_attempts` incrementado em falhas (pode ser usado para futura política de lockout).
- Pepper opcional permite endurecer armazenamento dos códigos; rotacione definindo novo valor e oferecendo regeneração de códigos aos usuários.
 - Lockout automático: após 5 falhas consecutivas, verificação 2FA bloqueada por 5 minutos (`twofa_locked_until`). Retorna HTTP 423 durante bloqueio.

### Estado de Implementação

Implementado:
1. Endpoint de regeneração de recovery codes (com token TOTP válido).
2. Lockout após 5 falhas por 5 minutos (`twofa_locked_until`).
3. Criptografia Fernet do `totp_secret` + flag `twofa_secret_encrypted` + suporte multi-key.
4. Admin action + endpoint para reset 2FA (`2fa/admin-reset/`).
5. Endpoint admin para forçar regeneração de recovery codes sem token do usuário (`2fa/admin-force-regenerate/`).
6. Rate limiting micro-burst (429) com contador `twofa_rate_limit_block_count`.
7. Métricas persistidas: sucessos, falhas, uso de recovery, bloqueios de rate limit.
8. Comando de auditoria `python manage.py twofa_status_report [--json] [--detailed]`.
9. Exibição de lockout na interface de challenge (HTTP 423).
10. Dashboard de métricas: `2fa/metrics-dashboard/` (superuser).
11. Comando de recriptografia/rotação primária: `python manage.py twofa_reencrypt_secrets [--dry-run] [--unencrypted-only]`.
12. Alerta proativo por email em marcos de falhas (20/50/100 falhas acumuladas).

Pendentes (opcionais / futuros):
13. Limpeza/normalização periódica de métricas antigas (task agendada).
14. Notificações multi-canal (SMS/Push) para eventos críticos.
15. UI para auto-serviço de rotação de recovery codes sem sair da tela principal.

### Configuração

Defina no `settings.py` (opcional):

```python
TWOFA_RECOVERY_PEPPER = os.environ.get('TWOFA_RECOVERY_PEPPER', '')
```

Manter vazio preserva hashes legacy.

---

## Especificações Detalhadas dos Incrementos Opcionais

### 1. Endpoint de Regeneração de Recovery Codes

Objetivo: Permitir que o usuário (já com 2FA confirmado) gere um novo conjunto de recovery codes invalidando os anteriores.

Proposta:
- Método: POST `user_management:2fa_regenerate_codes`
- Autenticação: Usuário logado + 2FA já habilitado e confirmado.
- Segurança adicional: Requer validação de um token TOTP válido no body (`token`) para impedir abuso de sessão já aberta + CSRF.
- Resposta: Retorna lista NOVA de códigos em claro UMA ÚNICA VEZ e contador.

Request exemplo (JSON):
```json
{ "token": "123456" }
```
Resposta sucesso (HTTP 200):
```json
{ "status": "ok", "recovery_codes": ["AAAA...", "BBBB..."], "count": 8 }
```
Erros:
- 400: token ausente ou inválido
- 423: lockout ativo (mesma regra de verify)

Interno:
1. Validar lockout.
2. Validar TOTP.
3. Gerar novos códigos → hash + salvar.
4. Zerar `failed_2fa_attempts`.
5. Registrar log `2FA_RECOVERY_REGENERATED`.

### 2. Criptografia Real do `totp_secret`

Motivação: Reduzir impacto em caso de vazamento de banco; segredo TOTP não deve estar em claro.

Abordagem recomendada:
- Usar `cryptography.fernet.Fernet`.
- Chave base derivada de `settings.SECRET_KEY` via HKDF / PBKDF2 (salt fixo versionado, p.ex. `b"2fa-fernet-v1"`).
- Armazenar no campo existente `totp_secret` o texto cifrado Base64 e marcar `twofa_secret_encrypted=True`.
- Backward: Se `twofa_secret_encrypted=False`, tratar como plaintext; ao primeiro uso bem-sucedido (verify ou confirm), migrar/criptografar on-the-fly.

Pseudocódigo derivação:
```python
import base64, hashlib
from cryptography.fernet import Fernet
def get_fernet_key():
	raw = hashlib.sha256((settings.SECRET_KEY + '::2FA_FERNET_V1').encode()).digest()
	return base64.urlsafe_b64encode(raw)
FERNET = Fernet(get_fernet_key())
```

Fluxo de migração suave:
1. Adicionar util `encrypt_secret` / `decrypt_secret`.
2. Em `verify_totp` wrapper: se não cifrado → cifrar e salvar.
3. Em `setup_2fa`: já armazenar cifrado.

### 3. Admin Action / Reset 2FA

Objetivo: Permitir que um superusuário ou administrador autorizado resete o 2FA de um usuário quando este perde acesso aos fatores.

Pontos:
- Ação no Django Admin em `PerfilUsuarioEstendidoAdmin` (action: "Resetar 2FA").
- Opcional: Endpoint POST `user_management:2fa_admin_reset` restrito a superuser.
- Efeito: Chamar `disable_2fa(perfil)` + log `2FA_ADMIN_RESET`.
- (Opcional) Notificar usuário por email sobre reset.

Resposta endpoint (200):
```json
{ "status": "ok", "detail": "2FA resetado; usuário deve reconfigurar." }
```

### 4. Teste Específico de Lockout

Objetivo: Garantir que após 5 falhas sequênciais a API responda 423 e bloqueie novas tentativas até expirar janela.

Estrutura do teste:
1. Configurar 2FA (setup + confirm).
2. Executar 5 POST `/2fa_verify` com token inválido → últimas respostas: 400, 400, 400, 400, 423.
3. Nova tentativa ainda dentro do período → 423.
4. Avançar tempo (freezegun ou monkeypatch timezone.now) +1 segundo após desbloqueio.
5. Enviar token válido → 200 e remover lock (`twofa_locked_until is None`).

Asserções chave:
- `perfil.twofa_locked_until` preenchido na 5ª falha.
- Resposta 423 contém mensagem padronizada.
- Após desbloqueio, contador de falhas zerado.

### 5. Rate Limiting (Planejado)

Abordagens possíveis:
- Contador em cache (Redis/Memcached) chave `2fa:attempts:<user_id>` com TTL curto (ex: 60s). Acima de 10 no minuto → 429.
- Complementar lockout: lockout atua por bursts prolongados de falha, RL controla micro-bursts.

Estrutura resposta 429:
```json
{ "detail": "Muitas tentativas. Aguarde alguns segundos." }
```

### 6. Regeneração + Pepper Rotation

Quando alterar `TWOFA_RECOVERY_PEPPER`:
1. Novos códigos passam a vir como `v2:`.
2. Antigos continuam aceitos (lógica híbrida já implementada).
3. Para forçar atualização dos existentes, instruir usuários a regenerar.

Checklist segurança pós-implementação:
- [ ] Todos segredos cifrados (`twofa_secret_encrypted=True` para 100% dos perfis).
- [ ] Scripts de auditoria para detectar perfis sem `autenticacao_dois_fatores` em grupos de risco.
- [ ] Monitorar métricas: taxa de falhas 2FA, uso de recovery codes, resets admin.

---

## FAQ Rápido

Pergunta: Posso mostrar novamente os recovery codes?  
Resposta: Não. Por design são one-time display. Use regeneração.

Pergunta: O lockout bloqueia também recovery codes?  
Resposta: Sim, a verificação passa pelo mesmo endpoint; durante lockout tudo retorna 423.

Pergunta: Como rotacionar a chave Fernet?  
Resposta: Introduzir `FERNET_KEYS = [nova, antiga]` e tentar de forma sequencial; re-salvar cifrando com a primeira.

