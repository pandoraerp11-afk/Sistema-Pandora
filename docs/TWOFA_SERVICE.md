# TwoFA Service (user_management.services.twofa_service)

Utilitário central para operações de 2FA (TOTP) desacopladas de views e commands.

## Objetivos
- Gerar e rotacionar segredo TOTP (32 chars Base32) com opção de criptografia Fernet (`TWOFA_ENCRYPT_SECRETS`).
- Gerar códigos de recuperação (apenas mostrados uma vez ao usuário).
- Armazenar somente hashes SHA-256 dos códigos.
- Consumir (invalidar) código de recuperação usado.
- Registrar métricas de sucesso / falha / rate-limit no perfil.
- Fornecer helpers utilitários (`mask_secret`, `decrypt_profile_secret_if_needed`).

## API
| Função | Descrição | Retorno |
|--------|-----------|---------|
| `generate_totp_secret()` | Cria novo segredo Base32. | `str` |
| `rotate_totp_secret(perfil)` | Substitui segredo, limpa confirmação e códigos (cifra se flag ativa). | novo segredo (`str` ou `None`) |
| `generate_backup_codes(perfil, count=8)` | Gera `count` códigos, sobrescreve os antigos. | Lista de códigos em claro |
| `verify_and_consume_backup_code(perfil, code)` | Valida e remove código (hash match). | `True/False` |
| `register_twofa_result(perfil, success, rate_limited=False)` | Incrementa contadores. | None |
| `mask_secret(secret)` | Mascarar segredo para logs/UI. | `str` |
| `decrypt_profile_secret_if_needed(perfil)` | Retorna segredo em claro (cifrado ou não). | `str` |

## Fluxo Sugerido (Ativação)
1. Usuário opta por habilitar 2FA -> gerar segredo via `rotate_totp_secret`.
2. Mostrar QR (se usar pyotp: `pyotp.totp.TOTP(secret).provisioning_uri(...)`).
3. Usuario digita código TOTP:
   - Se válido, definir `perfil.totp_confirmed_at = timezone.now()`.
   - Gerar backup codes (`generate_backup_codes`).
4. Exibir backup codes uma única vez (front deve instruir usuário a salvar offline).

## Backup Codes
Formato: `XXXX-YYYY` (8 caracteres Base32 divididos). Exemplo: `ABCD-EFG2`.
Armazenado como SHA-256 hex: `hashlib.sha256(code.encode()).hexdigest()`.

## Exemplo de Uso
```python
from user_management.services.twofa_service import rotate_totp_secret, generate_backup_codes, verify_and_consume_backup_code
perfil = request.user.perfil_estendido
secret = rotate_totp_secret(perfil)
# gerar QR + exibir secret
backup_codes = generate_backup_codes(perfil)
# salvar backup_codes em modal/arquivo para usuário
```

Verificação de código de recuperação:
```python
if verify_and_consume_backup_code(perfil, submitted_code):
    # login 2FA aprovado via recovery
    ...
```

Registro de resultado 2FA (ex: após login):
```python
from user_management.services.twofa_service import register_twofa_result
register_twofa_result(perfil, success=True)
```

## Métricas Disponíveis no Perfil
- `twofa_success_count`
- `twofa_failure_count`
- `twofa_recovery_use_count`
- `twofa_rate_limit_block_count`
- `failed_2fa_attempts` (reset em sucesso)

## Segurança / Boas Práticas
- Nunca armazenar ou logar códigos de recuperação em claro após exibição inicial.
- Rotacionar segredo ao suspeitar de comprometimento (`rotate_totp_secret`).
- Ativar criptografia de segredos definindo `TWOFA_ENCRYPT_SECRETS=True` e lista `TWOFA_FERNET_KEYS` (primeira chave usada para encrypt, demais para decrypt legacy).
- Usar comando `python manage.py twofa_reencrypt --dry-run` antes de migrar em produção.
- Implementar política de expiração opcional para códigos antigos.

### Settings relevantes
- `TWOFA_ENCRYPT_SECRETS` (bool): ativa criptografia Fernet dos segredos TOTP no banco.
- `TWOFA_FERNET_KEYS` (list[str]): lista ordenada de segredos para derivar chaves Fernet; a primeira é a primária de cifragem, as demais servem para decifrar segredos antigos.
    - Em desenvolvimento, se vazio, deriva automaticamente de `SECRET_KEY` (apenas para facilitar).

Notas:
- `decrypt_profile_secret_if_needed(perfil)` funciona para valores em claro e criptografados.
- A rotação (`rotate_totp_secret`) zera confirmação e backup codes por segurança.

## Testes
- `tests/user_management/test_twofa_service.py`: rotação, geração, consumo, métricas, criptografia.
- `tests/user_management/test_twofa_reencrypt_command.py`: comando de recriptografia.

## Futuro
- Estatísticas agregadas mensais / endpoint consolidado.
- Expiração automática de recovery codes após N usos ou tempo.
- Alertas de anomalias de uso (ex: muitos resets em curto intervalo).

## Comandos Relacionados
- `twofa_reencrypt`: recriptografa segredos existentes conforme chaves atuais (idempotente, suporta `--dry-run` e `--force`).
- `twofa_reencrypt_secrets`: recifra todos os segredos forçando uso da chave primária atual; útil em rotações amplas (suporta `--dry-run`, `--unencrypted-only`, `--limit`).
- `twofa_status_report`: relatório agregado do status do 2FA (totp configurado, confirmados, criptografados, lockouts; `--json` e `--detailed`).

Exemplos:
```
python manage.py twofa_reencrypt --dry-run
python manage.py twofa_reencrypt --force
python manage.py twofa_reencrypt_secrets --dry-run --unencrypted-only
python manage.py twofa_status_report --json
```

## Operação e Troubleshooting
- Ativando criptografia de segredos:
    - Defina em `settings`:
        - `TWOFA_ENCRYPT_SECRETS = True`
        - `TWOFA_FERNET_KEYS = ["<chave-primaria>", "<chave-anterior-1>", ...]`
            - A primeira chave é usada para cifrar; as demais permitem decifrar segredos legados.
    - Em dev, se `TWOFA_FERNET_KEYS` não for definido, é derivada automaticamente de `SECRET_KEY` (somente para facilitar desenvolvimento).
- Rotação de chave Fernet (blue/green):
    1) Adicione a nova chave como primeira em `TWOFA_FERNET_KEYS` mantendo as antigas ao final.
    2) Rode `twofa_reencrypt --dry-run` para avaliar impacto.
    3) Rode `twofa_reencrypt` (ou `twofa_reencrypt_secrets` se quiser forçar todos) para recifrar com a chave nova.
    4) Após estabilizar, remova chaves antigas da lista.
- Verificando um perfil específico:
    - Use `twofa_status_report --detailed` para listar anomalias (ex.: não criptografado ou não confirmado).
    - Para inspecionar/usar o segredo em claro no código, utilize `decrypt_profile_secret_if_needed(perfil)`.
- Sintomas comuns:
    - "Token inválido" ao decifrar: verifique se a chave antiga ainda está presente em `TWOFA_FERNET_KEYS` durante a migração.
    - Segredos aparecendo como texto claro: confirme `TWOFA_ENCRYPT_SECRETS=True` e reexecute `twofa_reencrypt`.
    - Cobertura de testes em execuções parciais: o `conftest` relaxa `fail-under` quando somente alguns testes são executados; utilize o test suite completo para validar a cobertura global.
