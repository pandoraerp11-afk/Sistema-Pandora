"""Serviços utilitários para 2FA (TOTP + códigos de recuperação).

Objetivos:
- Gerar segredo TOTP (rotacionável) sem depender obrigatoriamente de pyotp.
- Gerar códigos de recuperação (hash armazenado; texto retornado ao chamador).
- Verificar e consumir códigos de recuperação.
- Rotacionar segredo (invalidando confirmação anterior).
- Incrementar métricas simples no perfil do usuário (campos *_count já existentes).

Design:
- Segredo TOTP: 32 caracteres base32 (A-Z2-7). Se pyotp disponível, usar random_base32(); senão fallback manual.
- Códigos de recuperação: lista de strings tipo XXXX-YYYY (2 blocos base32 reduzidos) ou fallback hex.
- Hash: sha256 em formato hex. Guardamos lista de hashes em perfil.totp_recovery_codes.
- Verificação de código: comparar hash constante; se achar remove hash (consumido) e incrementa twofa_recovery_use_count.
- Todas operações silenciam exceções para não derrubar fluxo (retornam None/False em erro).
"""

from __future__ import annotations

import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken  # já em requirements
from django.conf import settings

_FERNET_PRIMARY = None
_FERNET_FALLBACKS = []


def _derive_key(seed: str) -> bytes:
    raw = hashlib.sha256(seed.encode()).digest()
    import base64 as _b64

    return _b64.urlsafe_b64encode(raw)


def _init_fernets():
    global _FERNET_PRIMARY, _FERNET_FALLBACKS
    if _FERNET_PRIMARY:
        return
    seeds = getattr(settings, "TWOFA_FERNET_KEYS", None)
    if not seeds:
        # deriva chave estável da SECRET_KEY (dev) – produção deve definir lista explícita
        seeds = [settings.SECRET_KEY + "::TWOFA_V1"]
    keys = [_derive_key(s) for s in seeds]
    _FERNET_PRIMARY = Fernet(keys[0])
    _FERNET_FALLBACKS = [Fernet(k) for k in keys[1:]]


def _encrypt_secret(plain: str) -> str:
    if not plain:
        return plain
    try:
        _init_fernets()
        return _FERNET_PRIMARY.encrypt(plain.encode()).decode()
    except Exception:
        return plain  # fallback claro


def _decrypt_secret(cipher: str) -> str:
    if not cipher:
        return cipher
    try:
        _init_fernets()
        for f in [_FERNET_PRIMARY, *_FERNET_FALLBACKS]:
            try:
                return f.decrypt(cipher.encode()).decode()
            except InvalidToken:
                continue
            except Exception:
                break
    except Exception:
        pass
    return cipher  # assume legado texto plano


try:  # opcional
    import pyotp  # type: ignore
except Exception:  # pragma: no cover
    pyotp = None

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def _random_base32(length: int = 32) -> str:
    if pyotp and hasattr(pyotp, "random_base32"):
        try:
            return pyotp.random_base32(length=length)
        except Exception:  # pragma: no cover
            pass
    # Fallback manual
    return "".join(secrets.choice(BASE32_ALPHABET) for _ in range(length))


def generate_totp_secret() -> str:
    return _random_base32(32)


def rotate_totp_secret(perfil) -> str | None:
    """Rotaciona o segredo TOTP do perfil.
    Reseta confirmação e códigos de recuperação (boa prática) e retorna novo segredo em claro.
    """
    try:
        secret = generate_totp_secret()
        if getattr(settings, "TWOFA_ENCRYPT_SECRETS", False):
            enc = _encrypt_secret(secret)
            perfil.totp_secret = enc
            perfil.twofa_secret_encrypted = True
        else:
            perfil.totp_secret = secret
            perfil.twofa_secret_encrypted = False
        perfil.totp_confirmed_at = None
        perfil.totp_recovery_codes = []
        perfil.save(update_fields=["totp_secret", "totp_confirmed_at", "totp_recovery_codes", "twofa_secret_encrypted"])
        return secret
    except Exception:  # pragma: no cover
        return None


def generate_backup_codes(perfil, count: int = 8) -> list[str]:
    """Gera 'count' códigos de recuperação novos substituindo os anteriores.
    Retorna lista em claro para exibição única ao usuário.
    """
    plain_codes: list[str] = []
    hashes: list[str] = []
    for _ in range(count):
        # Formato legível: 4+4 chars base32
        raw = "".join(secrets.choice(BASE32_ALPHABET) for _ in range(8))
        code = f"{raw[:4]}-{raw[4:]}"
        plain_codes.append(code)
        h = hashlib.sha256(code.encode("utf-8")).hexdigest()
        hashes.append(h)
    try:
        perfil.totp_recovery_codes = hashes
        perfil.save(update_fields=["totp_recovery_codes"])
    except Exception:  # pragma: no cover
        pass
    return plain_codes


def verify_and_consume_backup_code(perfil, code: str) -> bool:
    """Verifica código de recuperação. Se válido remove-o (consumido) e incrementa métrica.
    Retorna True se aceito.
    """
    if not code:
        return False
    try:
        h = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()
        codes = perfil.totp_recovery_codes or []
        if h not in codes:
            return False
        # consumir
        codes.remove(h)
        perfil.totp_recovery_codes = codes
        perfil.twofa_recovery_use_count = (perfil.twofa_recovery_use_count or 0) + 1
        perfil.save(update_fields=["totp_recovery_codes", "twofa_recovery_use_count"])
        return True
    except Exception:  # pragma: no cover
        return False


def register_twofa_result(perfil, success: bool, rate_limited: bool = False):
    """Incrementa contadores de sucesso/falha e opcionalmente de rate limit."""
    try:
        if success:
            perfil.twofa_success_count = (perfil.twofa_success_count or 0) + 1
            perfil.failed_2fa_attempts = 0
        else:
            perfil.twofa_failure_count = (perfil.twofa_failure_count or 0) + 1
            perfil.failed_2fa_attempts = (perfil.failed_2fa_attempts or 0) + 1
        if rate_limited:
            perfil.twofa_rate_limit_block_count = (perfil.twofa_rate_limit_block_count or 0) + 1
        perfil.save(
            update_fields=[
                "twofa_success_count",
                "twofa_failure_count",
                "failed_2fa_attempts",
                "twofa_rate_limit_block_count",
            ]
        )
    except Exception:  # pragma: no cover
        pass


def mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return secret[:4] + ("*" * (len(secret) - 8)) + secret[-4:]


__all__ = [
    "generate_totp_secret",
    "rotate_totp_secret",
    "generate_backup_codes",
    "verify_and_consume_backup_code",
    "register_twofa_result",
    "mask_secret",
]


def decrypt_profile_secret_if_needed(perfil) -> str:
    """Helper para obter segredo em claro independente de estar cifrado ou não."""
    secret = getattr(perfil, "totp_secret", None)
    if not secret:
        return ""
    if getattr(perfil, "twofa_secret_encrypted", False):
        return _decrypt_secret(secret)
    return secret


__all__.append("decrypt_profile_secret_if_needed")
