"""
src/security.py — Secret Encryption & Security Module
Provides salted AES-Fernet encryption for sensitive credentials stored in the SQLite database.
"""

import base64
import os
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.common import APP_DATA_DIR, APP_NAME

# Set of config keys that are considered sensitive and must be encrypted at rest
SENSITIVE_KEYS = {
    "ANTHROPIC_KEY",
    "GEMINI_KEY",
    "GROQ_KEY",
    "OPENAI_KEY",
    "NVIDIA_KEY",
    "OPENROUTER_KEY",
    "GITHUB_KEY",
    "OLLAMA_CLOUD_KEY",
    "SMTP_PASSWORD",
    "FLASK_SECRET_KEY",
}

_fernet_instance = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    salt_file = APP_DATA_DIR / ".secret_salt"
    if salt_file.exists():
        try:
            salt = salt_file.read_bytes()
        except Exception:
            salt = os.urandom(16)
            salt_file.write_bytes(salt)
    else:
        salt = os.urandom(16)
        try:
            salt_file.write_bytes(salt)
        except Exception:
            pass

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(APP_NAME.encode()))
    _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext string using salted AES-Fernet. Returns an ENC:... prefixed token."""
    if not plaintext or not isinstance(plaintext, str):
        return ""
    if plaintext.startswith("ENC:"):
        return plaintext
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"ENC:{encrypted}"


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt an ENC:... prefixed token back to plaintext in memory."""
    if not ciphertext or not isinstance(ciphertext, str):
        return ""
    if not ciphertext.startswith("ENC:"):
        return ciphertext
    try:
        raw_payload = ciphertext[4:]
        fernet = _get_fernet()
        decrypted = fernet.decrypt(raw_payload.encode("utf-8")).decode("utf-8")
        return decrypted
    except Exception:
        # Fallback if decryption fails (e.g. invalid key/corrupted token)
        return ""
