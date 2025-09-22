import base64
import hashlib
import secrets

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

# ================== Mensagens Canonicas ==================
RATE_MSG_GLOBAL_IP = "Muitas tentativas deste IP. Aguarde."
RATE_MSG_MICRO = "Muitas tentativas. Aguarde alguns segundos."
RATE_MSG_LOCK = "Muitas tentativas falhas. 2FA bloqueado por 5 minutos."


def get_rate_messages():
    """Retorna dicionário com mensagens padronizadas para reutilização em views/tests."""
    return {
        "global_ip": RATE_MSG_GLOBAL_IP,
        "micro": RATE_MSG_MICRO,
        "lock": RATE_MSG_LOCK,
    }


RECOVERY_CODES_COUNT = 8
RECOVERY_CODE_LENGTH = 10


def generate_totp_secret():
    return pyotp.random_base32()


# ================== Criptografia do segredo ==================
_FERNET_PRIMARY = None
_FERNET_FALLBACKS = []


def _derive_key(seed: str) -> bytes:
    raw = hashlib.sha256(seed.encode()).digest()
    return base64.urlsafe_b64encode(raw)


def _init_fernets():
    global _FERNET_PRIMARY, _FERNET_FALLBACKS
    if _FERNET_PRIMARY:
        return
    seeds = getattr(settings, "TWOFA_FERNET_KEYS", None)
    if not seeds:
        seeds = [settings.SECRET_KEY + "::2FA_FERNET_V1"]
    keys = [_derive_key(s) for s in seeds]
    _FERNET_PRIMARY = Fernet(keys[0])
    _FERNET_FALLBACKS = [Fernet(k) for k in keys[1:]]


def _get_primary():
    _init_fernets()
    return _FERNET_PRIMARY


def _get_all():
    _init_fernets()
    return [_FERNET_PRIMARY, *_FERNET_FALLBACKS]


def encrypt_secret(plain: str) -> str:
    if not plain:
        return plain
    return _get_primary().encrypt(plain.encode()).decode()


def decrypt_secret(cipher: str) -> str:
    if not cipher:
        return cipher
    for f in _get_all():
        try:
            return f.decrypt(cipher.encode()).decode()
        except InvalidToken:
            continue
        except Exception:
            break
    # fallback: assume plaintext legado
    return cipher


# ================== Rate Limiting ==================


def rate_limit_check(user_id: int, ip: str, limit: int = 10, window_seconds: int = 60) -> bool:
    """Limite (user_id + IP). True se dentro, False se excedeu."""
    return _increment_rate_key(f"2fa:rl:{user_id}:{ip if ip else 'na'}", limit, window_seconds)


def global_ip_rate_limit_check(ip: str, limit: int = 30, window_seconds: int = 60) -> bool:
    """Limite global por IP para tentativas 2FA (independente de usuário).
    Evita abuso distribuído em múltiplas contas.
    """
    # Permite configurar via settings
    limit = getattr(settings, "TWOFA_GLOBAL_IP_LIMIT", limit)
    window_seconds = getattr(settings, "TWOFA_GLOBAL_IP_WINDOW", window_seconds)
    key = f"2fa:rlip:{ip if ip else 'na'}"
    ok = _increment_rate_key(key, limit, window_seconds)
    if not ok:
        # Incrementar métrica agregada de bloqueios globais de IP (alinhado com views.global_ip_rate_limit)
        try:
            cache.incr("twofa_global_ip_block_metric")
        except Exception:
            cur = cache.get("twofa_global_ip_block_metric", 0) or 0
            cache.set("twofa_global_ip_block_metric", cur + 1, 24 * 3600)
    return ok


def _increment_rate_key(key: str, limit: int, window_seconds: int) -> bool:
    try:
        current = cache.get(key)
        if current is None:
            cache.set(key, 1, timeout=window_seconds)
            return True
        if current >= limit:
            return False
        cache.incr(key)
        return True
    except Exception:
        return True


def generate_recovery_codes():
    codes = []
    for _ in range(RECOVERY_CODES_COUNT):
        raw = secrets.token_hex(RECOVERY_CODE_LENGTH // 2).upper()
        codes.append(raw)
    return codes


def _get_recovery_pepper() -> str:
    """Retorna pepper opcional definido em settings.TWOFA_RECOVERY_PEPPER.
    Se não definido, retorna string vazia (compatibilidade).
    """
    return getattr(settings, "TWOFA_RECOVERY_PEPPER", "") or ""


def hash_code(code: str) -> str:
    """Hash canônico (v2 se pepper presente) para recovery codes.

    Estrutura:
      - Sem pepper: retorna apenas o hex (legado v1)
      - Com pepper: prefixa 'v2:' + hex( sha256( pepper + '|' + code ) )
    """
    pepper = _get_recovery_pepper()
    if pepper:
        h = hashlib.sha256(f"{pepper}|{code}".encode()).hexdigest()
        return f"v2:{h}"
    return hashlib.sha256(code.encode()).hexdigest()


def provision_uri(username: str, secret: str, issuer: str = "PandoraERP"):
    return pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret: str, token: str) -> bool:
    if not secret:
        return False
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)
    except Exception:
        return False


def setup_2fa(perfil):
    secret = generate_totp_secret()
    raw_codes = generate_recovery_codes()
    # Armazenar já cifrado
    enc = encrypt_secret(secret)
    perfil.totp_secret = enc
    perfil.twofa_secret_encrypted = True
    perfil.autenticacao_dois_fatores = True
    perfil.failed_2fa_attempts = 0
    perfil.totp_confirmed_at = None
    perfil.totp_recovery_codes = [hash_code(c) for c in raw_codes]
    perfil.save(
        update_fields=[
            "totp_secret",
            "twofa_secret_encrypted",
            "autenticacao_dois_fatores",
            "failed_2fa_attempts",
            "totp_confirmed_at",
            "totp_recovery_codes",
        ]
    )
    return secret, raw_codes


def confirm_2fa(perfil, token: str) -> bool:
    # Garantir decriptação se necessário
    secret = perfil.totp_secret
    if perfil.twofa_secret_encrypted:
        secret = decrypt_secret(secret)
    if verify_totp(secret, token):
        perfil.totp_confirmed_at = timezone.now()
        perfil.failed_2fa_attempts = 0
        perfil.twofa_success_count = (perfil.twofa_success_count or 0) + 1
        perfil.save(update_fields=["totp_confirmed_at", "failed_2fa_attempts", "twofa_success_count"])
        return True
    perfil.failed_2fa_attempts += 1
    perfil.twofa_failure_count = (perfil.twofa_failure_count or 0) + 1
    perfil.save(update_fields=["failed_2fa_attempts", "twofa_failure_count"])
    return False


def disable_2fa(perfil):
    perfil.autenticacao_dois_fatores = False
    perfil.totp_secret = None
    perfil.totp_recovery_codes = []
    perfil.totp_confirmed_at = None
    perfil.failed_2fa_attempts = 0
    perfil.twofa_secret_encrypted = False
    perfil.save(
        update_fields=[
            "autenticacao_dois_fatores",
            "totp_secret",
            "totp_recovery_codes",
            "totp_confirmed_at",
            "failed_2fa_attempts",
            "twofa_secret_encrypted",
        ]
    )


def use_recovery_code(perfil, submitted_code: str) -> bool:
    """Tenta consumir um recovery code.

    Backward compatibility: códigos antigos (v1) foram armazenados como apenas o hash.
    Novos (v2) possuem prefixo 'v2:'. Tentamos ambas as formas para aceitar códigos
    gerados antes da introdução do pepper.
    """
    raw = submitted_code.strip().upper()
    hashed_new = hash_code(raw)  # já inclui prefixo se pepper ativo
    # Versão legacy (sem pepper / sem prefixo)
    hashed_legacy = hashlib.sha256(raw.encode()).hexdigest()
    codes = perfil.totp_recovery_codes or []

    match = None
    if hashed_new in codes:
        match = hashed_new
    elif hashed_legacy in codes:
        match = hashed_legacy

    if match:
        codes.remove(match)
        perfil.totp_recovery_codes = codes
        perfil.failed_2fa_attempts = 0
        perfil.twofa_recovery_use_count = (perfil.twofa_recovery_use_count or 0) + 1
        perfil.twofa_success_count = (perfil.twofa_success_count or 0) + 1
        perfil.save(
            update_fields=[
                "totp_recovery_codes",
                "failed_2fa_attempts",
                "twofa_recovery_use_count",
                "twofa_success_count",
            ]
        )
        return True
    perfil.failed_2fa_attempts += 1
    perfil.twofa_failure_count = (perfil.twofa_failure_count or 0) + 1
    perfil.save(update_fields=["failed_2fa_attempts", "twofa_failure_count"])
    return False
