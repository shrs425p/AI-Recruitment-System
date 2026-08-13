"""
app/crypto.py -- AES-256-GCM Field Encryption for Candidate PII
================================================================

Provides transparent encrypt/decrypt for sensitive fields (names, emails)
stored in SQLite. The master key is protected by the OS:

  Windows : Windows DPAPI (CryptProtectData) -- key bound to the current
             Windows user account. No plaintext key ever touches disk.
  Fallback : PBKDF2-HMAC-SHA256 derived from FLASK_SECRET_KEY + machine-id.
             Used on non-Windows or when pywin32 is unavailable.

Public API
----------
  encrypt_field(plaintext: str) -> str   # returns base64url token
  decrypt_field(ciphertext: str) -> str  # returns original string
  is_encrypted(value: str) -> bool       # True when value looks like our token

Token format (base64url of):
  b"ARS1" + nonce(12) + ciphertext + tag(16)

The "ARS1" magic prefix lets us detect already-encrypted values and skip
double-encryption during migrations.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import platform
import struct
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

_MAGIC = b"ARS1"
_KEY_CACHE: bytes | None = None  # Module-level cache -- loaded once per process


# -- Key management -----------------------------------------------------------

def _get_or_create_dpapi_key() -> bytes:
    """
    Load (or generate) a 32-byte master key, protected by Windows DPAPI.
    Key is stored as an encrypted blob at <AppData>/ARS/crypto.key.dpapi.
    """
    from src.common import data_path
    key_path = data_path("crypto.key.dpapi")

    try:
        import win32crypt  # type: ignore[import]
    except ImportError:
        raise RuntimeError("pywin32 not available -- cannot use DPAPI.")

    if key_path.exists():
        encrypted_blob = key_path.read_bytes()
        key, _ = win32crypt.CryptUnprotectData(encrypted_blob, None, None, None, 0)
        return key

    # Generate a fresh key and protect it
    raw_key = os.urandom(32)
    encrypted_blob = win32crypt.CryptProtectData(raw_key, "ARS-PII-Key", None, None, None, 0)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(encrypted_blob)
    logger.info("[CRYPTO] New AES-256 key generated and protected with DPAPI.")
    return raw_key


def _get_or_create_fallback_key() -> bytes:
    """
    Derive a 32-byte key from FLASK_SECRET_KEY + machine-id via PBKDF2.
    Used when DPAPI is unavailable (non-Windows / pywin32 missing).
    """
    from src.common import data_path

    # Machine identifier (stable but not secret)
    machine_id_path = Path("/etc/machine-id")  # Linux
    if not machine_id_path.exists():
        machine_id_path = Path(os.environ.get("COMPUTERNAME", "ARS-MACHINE")).with_suffix(".id")
    try:
        machine_salt = machine_id_path.read_bytes()[:32]
    except Exception:
        machine_salt = platform.node().encode()[:32]

    # Use an on-disk nonce so key is stable across restarts
    nonce_path = data_path("crypto.salt")
    if not nonce_path.exists():
        nonce_path.parent.mkdir(parents=True, exist_ok=True)
        nonce_path.write_bytes(os.urandom(16))
    file_salt = nonce_path.read_bytes()

    # Import secret key from Flask config (available at module init)
    try:
        import config as _cfg
        secret = getattr(_cfg, "FLASK_SECRET_KEY", "") or ""
    except Exception:
        secret = ""

    ikm = secret.encode() + machine_salt + file_salt
    key = hashlib.pbkdf2_hmac("sha256", ikm, file_salt, iterations=200_000, dklen=32)
    logger.info("[CRYPTO] AES-256 key derived (PBKDF2 fallback mode).")
    return key


def _load_key() -> bytes:
    """Return the master AES-256 key, using DPAPI if on Windows, else PBKDF2."""
    global _KEY_CACHE
    if _KEY_CACHE is not None:
        return _KEY_CACHE

    if platform.system() == "Windows":
        try:
            _KEY_CACHE = _get_or_create_dpapi_key()
            logger.info("[CRYPTO] Master key loaded via Windows DPAPI.")
            return _KEY_CACHE
        except Exception as exc:
            logger.warning("[CRYPTO] DPAPI unavailable (%s) -- falling back to PBKDF2.", exc)

    _KEY_CACHE = _get_or_create_fallback_key()
    return _KEY_CACHE


# -- Encryption / decryption --------------------------------------------------

def encrypt_field(plaintext: str) -> str:
    """
    Encrypt a plaintext string with AES-256-GCM.

    Args:
        plaintext: The raw string to protect (name, email, etc.).

    Returns:
        A base64url-encoded token including the magic prefix, nonce,
        ciphertext, and GCM authentication tag. Safe to store in SQLite TEXT.

    Raises:
        ValueError: If plaintext is not a string.
    """
    if not isinstance(plaintext, str):
        raise ValueError(f"encrypt_field expects str, got {type(plaintext)}")
    if is_encrypted(plaintext):
        return plaintext  # Already encrypted -- idempotent

    key = _load_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    blob = _MAGIC + nonce + ct
    return base64.urlsafe_b64encode(blob).decode("ascii")


def decrypt_field(ciphertext: str) -> str:
    """
    Decrypt a field encrypted by ``encrypt_field``.

    Args:
        ciphertext: A base64url token as returned by ``encrypt_field``.
                    If the value does not look encrypted, it is returned as-is
                    (allows a graceful migration period where old plaintext rows
                    coexist with new encrypted rows).

    Returns:
        The original plaintext string.
    """
    if not isinstance(ciphertext, str):
        return str(ciphertext)
    if not is_encrypted(ciphertext):
        return ciphertext  # Legacy plaintext -- return unchanged

    try:
        blob = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    except Exception:
        return ciphertext  # Cannot decode -- treat as plaintext

    if not blob.startswith(_MAGIC):
        return ciphertext

    blob = blob[len(_MAGIC):]
    if len(blob) < 12 + 16:  # nonce(12) + tag(16) minimum
        logger.warning("[CRYPTO] Blob too short -- returning raw value.")
        return ciphertext

    nonce, ct = blob[:12], blob[12:]
    key = _load_key()
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ct, None)
        return plaintext.decode("utf-8")
    except Exception as exc:
        logger.error("[CRYPTO] Decryption failed: %s", exc)
        return ciphertext  # Return ciphertext rather than crash


def is_encrypted(value: str) -> bool:
    """Return True if value appears to be an ARS1 encrypted token."""
    if not isinstance(value, str) or len(value) < 30:
        return False
    try:
        blob = base64.urlsafe_b64decode(value.encode("ascii") + b"==")
        return blob.startswith(_MAGIC)
    except Exception:
        return False
