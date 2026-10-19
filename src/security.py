"""
src/security.py — Secret Encryption & Security Module
Provides machine-bound, salted AES-Fernet encryption for sensitive credentials and files.
Key derivation uses PBKDF2-HMAC-SHA256 (100,000 iterations) bound to a host machine secret
(such as Windows Registry MachineGuid) and a persistent random salt.
"""

from __future__ import annotations

import base64
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

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

_fernet_instance: Fernet | None = None
_legacy_fernet_instance: Fernet | None = None


def reset_cipher_cache() -> None:
    """Clear cached Fernet instances (useful for testing and key migration)."""
    global _fernet_instance, _legacy_fernet_instance
    _fernet_instance = None
    _legacy_fernet_instance = None


def _get_machine_secret() -> str:
    """
    Retrieve a host machine-specific identifier to bind encryption keys to this machine.

    Priority order:
    1. Explicit environment variable ARS_MACHINE_SECRET (for testing, CI, containers).
    2. Windows MachineGuid from HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography.
    3. Linux /etc/machine-id or /var/lib/dbus/machine-id.
    4. macOS IOPlatformUUID via ioreg.
    5. Fallback hardware fingerprint derived from system UUID, MAC address, hostname, and user context.
    """
    env_secret = os.environ.get("ARS_MACHINE_SECRET", "").strip()
    if env_secret:
        return env_secret

    # 1. Windows MachineGuid
    if sys.platform == "win32":
        try:
            import winreg

            access_flags = [winreg.KEY_READ]
            if hasattr(winreg, "KEY_WOW64_64KEY"):
                access_flags.insert(0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)

            for flag in access_flags:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\Microsoft\Cryptography",
                        0,
                        flag,
                    ) as key:
                        val, _ = winreg.QueryValueEx(key, "MachineGuid")
                        if val and str(val).strip():
                            return str(val).strip()
                except OSError:
                    continue
        except Exception as e:
            logger.debug("Failed querying Windows Registry MachineGuid: %s", e)

    # 2. Linux machine ID
    for mid_path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            if mid_path.is_file():
                mid = mid_path.read_text(encoding="utf-8").strip()
                if mid:
                    return mid
        except Exception as e:
            logger.debug("Failed reading Linux machine-id from %s: %s", mid_path, e)

    # 3. macOS IOPlatformUUID
    if sys.platform == "darwin":
        try:
            import subprocess

            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            )
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    parts = line.split("=")
                    if len(parts) > 1:
                        uuid_val = parts[1].strip().strip('"')
                        if uuid_val:
                            return uuid_val
        except Exception as e:
            logger.debug("Failed reading macOS IOPlatformUUID: %s", e)

    # 4. Hardware fingerprint fallback
    try:
        import getpass
        import hashlib
        import platform
        import uuid

        components = [
            str(uuid.getnode()),
            platform.node(),
            platform.machine(),
            platform.processor(),
            os.environ.get("COMPUTERNAME", ""),
            os.environ.get("USER", os.environ.get("USERNAME", "")),
        ]
        try:
            components.append(getpass.getuser())
        except Exception as e:
            logger.debug("Failed fetching user login name for fingerprint: %s", e)
        return hashlib.sha256(":".join(components).encode("utf-8")).hexdigest()
    except Exception as e:
        import uuid

        logger.debug("Failed generating hardware fingerprint, falling back to node UUID: %s", e)
        return f"fallback-node-{uuid.getnode()}"


def _get_salt() -> bytes:
    """Retrieve or initialize the persistent 16-byte random salt."""
    salt_path_env = os.environ.get("ARS_SALT_FILE", "").strip()
    if salt_path_env:
        salt_file = Path(salt_path_env)
    else:
        salt_file = APP_DATA_DIR / ".secret_salt"

    if salt_file.is_file():
        try:
            salt = salt_file.read_bytes()
            if len(salt) >= 16:
                return salt[:16]
        except Exception as e:
            logger.debug("Failed reading existing salt file: %s", e)

    salt = os.urandom(16)
    try:
        salt_file.parent.mkdir(parents=True, exist_ok=True)
        salt_file.write_bytes(salt)
        if os.name != "nt":
            try:
                os.chmod(salt_file, 0o600)
            except Exception as e:
                logger.debug("Failed setting permissions on salt file: %s", e)
    except Exception as e:
        logger.debug("Failed persisting salt file: %s", e)
    return salt


def _derive_fernet_key(secret_material: str, salt: bytes) -> bytes:
    """Derive a URL-safe base64 Fernet key using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret_material.encode("utf-8")))


def _get_fernet() -> Fernet:
    """
    Return the primary Fernet cipher instance bound to the host machine secret.
    Derives key from f"{APP_NAME}::{machine_secret}" and persistent salt.
    """
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    salt = _get_salt()
    machine_secret = _get_machine_secret()
    secret_material = f"{APP_NAME}::{machine_secret}"
    key = _derive_fernet_key(secret_material, salt)
    _fernet_instance = Fernet(key)
    return _fernet_instance


def _get_legacy_fernet() -> Fernet:
    """
    Return the legacy Fernet cipher instance derived from public APP_NAME alone.
    Used exclusively for backward-compatible decryption and migration of existing data.
    """
    global _legacy_fernet_instance
    if _legacy_fernet_instance is not None:
        return _legacy_fernet_instance

    salt = _get_salt()
    key = _derive_fernet_key(APP_NAME, salt)
    _legacy_fernet_instance = Fernet(key)
    return _legacy_fernet_instance


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext string using machine-bound AES-Fernet. Returns an ENC:... prefixed token."""
    if not plaintext or not isinstance(plaintext, str):
        return ""
    if plaintext.startswith("ENC:"):
        return plaintext
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"ENC:{encrypted}"


def decrypt_secret(ciphertext: str) -> str:
    """
    Decrypt an ENC:... prefixed token back to plaintext in memory.
    Tries primary machine-bound cipher first; falls back to legacy cipher for migration if needed.
    """
    if not ciphertext or not isinstance(ciphertext, str):
        return ""
    if not ciphertext.startswith("ENC:"):
        return ciphertext
    try:
        raw_payload = ciphertext[4:].encode("utf-8")
    except Exception:
        return ""

    # 1. Primary: machine-bound Fernet
    try:
        fernet = _get_fernet()
        return fernet.decrypt(raw_payload).decode("utf-8")
    except Exception as e:
        logger.debug("Primary Fernet decrypt failed, falling back to legacy: %s", e)

    # 2. Legacy fallback for backward-compatibility & migration
    try:
        legacy = _get_legacy_fernet()
        return legacy.decrypt(raw_payload).decode("utf-8")
    except Exception as e:
        logger.debug("Legacy Fernet decrypt failed: %s", e)

    return ""


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt raw binary data using machine-bound AES-Fernet with an ARS_ENC: magic prefix."""
    if not data or not isinstance(data, (bytes, bytearray)):
        return b""
    if data.startswith(b"ARS_ENC:"):
        return bytes(data)
    fernet = _get_fernet()
    encrypted = fernet.encrypt(bytes(data))
    return b"ARS_ENC:" + encrypted


def decrypt_bytes(data: bytes) -> bytes:
    """
    Decrypt an ARS_ENC: prefixed binary token back to original bytes.
    Tries primary machine-bound cipher first; falls back to legacy cipher for migration if needed.
    """
    if not data or not isinstance(data, (bytes, bytearray)):
        return b""
    if not data.startswith(b"ARS_ENC:"):
        return bytes(data)
    raw_payload = bytes(data[8:])

    # 1. Primary: machine-bound Fernet
    try:
        fernet = _get_fernet()
        return fernet.decrypt(raw_payload)
    except Exception as e:
        logger.debug("Primary Fernet binary decrypt failed, falling back to legacy: %s", e)

    # 2. Legacy fallback
    try:
        legacy = _get_legacy_fernet()
        return legacy.decrypt(raw_payload)
    except Exception as e:
        logger.debug("Legacy Fernet binary decrypt failed: %s", e)

    return b""


def migrate_database_secrets(conn=None) -> int:
    """
    Scan stored encrypted secrets in the database and upgrade any legacy-encrypted
    records to the machine-bound Fernet key. Returns count of upgraded records.
    """
    should_close = False
    if conn is None:
        try:
            from app.database import get_connection

            conn = get_connection()
            should_close = True
        except Exception:
            return 0

    migrated_count = 0
    primary = _get_fernet()
    legacy = _get_legacy_fernet()

    # 1. app_settings
    try:
        rows = conn.execute("SELECT key, value FROM app_settings WHERE is_encrypted=1").fetchall()
        for row in rows:
            k = row[0] if isinstance(row, (tuple, list)) else row["key"]
            v = row[1] if isinstance(row, (tuple, list)) else row["value"]
            if v and isinstance(v, str) and v.startswith("ENC:"):
                payload = v[4:].encode("utf-8")
                try:
                    primary.decrypt(payload)
                    continue
                except Exception as e:
                    logger.debug("Primary decrypt failed for app_settings key %s: %s", k, e)
                try:
                    decrypted = legacy.decrypt(payload).decode("utf-8")
                    new_enc = f"ENC:{primary.encrypt(decrypted.encode('utf-8')).decode('utf-8')}"
                    conn.execute("UPDATE app_settings SET value = ? WHERE key = ?", (new_enc, k))
                    migrated_count += 1
                except Exception as e:
                    logger.debug("Legacy migration failed for app_settings key %s: %s", k, e)
    except Exception as e:
        logger.debug("Failed querying app_settings for migration: %s", e)

    # 2. candidates
    try:
        rows = conn.execute("SELECT id, email FROM candidates WHERE email LIKE 'ENC:%'").fetchall()
        for row in rows:
            cid = row[0] if isinstance(row, (tuple, list)) else row["id"]
            email_val = row[1] if isinstance(row, (tuple, list)) else row["email"]
            if email_val and isinstance(email_val, str) and email_val.startswith("ENC:"):
                payload = email_val[4:].encode("utf-8")
                try:
                    primary.decrypt(payload)
                    continue
                except Exception as e:
                    logger.debug("Primary decrypt failed for candidate %s: %s", cid, e)
                try:
                    decrypted = legacy.decrypt(payload).decode("utf-8")
                    new_enc = f"ENC:{primary.encrypt(decrypted.encode('utf-8')).decode('utf-8')}"
                    conn.execute("UPDATE candidates SET email = ? WHERE id = ?", (new_enc, cid))
                    migrated_count += 1
                except Exception as e:
                    logger.debug("Legacy migration failed for candidate %s: %s", cid, e)
    except Exception as e:
        logger.debug("Failed querying candidates for migration: %s", e)

    # 3. email_log
    try:
        rows = conn.execute("SELECT id, recipient FROM email_log WHERE recipient LIKE 'ENC:%'").fetchall()
        for row in rows:
            lid = row[0] if isinstance(row, (tuple, list)) else row["id"]
            recip = row[1] if isinstance(row, (tuple, list)) else row["recipient"]
            if recip and isinstance(recip, str) and recip.startswith("ENC:"):
                payload = recip[4:].encode("utf-8")
                try:
                    primary.decrypt(payload)
                    continue
                except Exception as e:
                    logger.debug("Primary decrypt failed for email_log id %s: %s", lid, e)
                try:
                    decrypted = legacy.decrypt(payload).decode("utf-8")
                    new_enc = f"ENC:{primary.encrypt(decrypted.encode('utf-8')).decode('utf-8')}"
                    conn.execute("UPDATE email_log SET recipient = ? WHERE id = ?", (new_enc, lid))
                    migrated_count += 1
                except Exception as e:
                    logger.debug("Legacy migration failed for email_log id %s: %s", lid, e)
    except Exception as e:
        logger.debug("Failed querying email_log for migration: %s", e)

    try:
        conn.commit()
    except Exception as e:
        logger.debug("Failed to commit migrated secrets: %s", e)

    if should_close:
        try:
            conn.close()
        except Exception as e:
            logger.debug("Failed to close connection after migration: %s", e)

    return migrated_count


def escape_xml_payload(text: object, escape_quotes: bool = False) -> str:
    """
    Escape XML delimiter characters in untrusted text (&, <, >)
    to prevent prompt injection and tag boundary breakout in LLM templates.
    """
    if text is None:
        return ""
    if isinstance(text, (dict, list)):
        import json

        s = json.dumps(text, indent=2)
    else:
        s = str(text)

    escaped = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if escape_quotes:
        escaped = escaped.replace('"', "&quot;").replace("'", "&apos;")
    return escaped


def mask_secret(val: str, prefix_len: int = 4, suffix_len: int = 4) -> str:
    """
    Mask sensitive secrets for safe display in UI templates (e.g. sk-a••••••••••••cdef).
    Returns empty string if val is empty/None.
    """
    if not val or not isinstance(val, str):
        return ""
    val = val.strip()
    if not val:
        return ""
    if len(val) <= prefix_len + suffix_len:
        return "••••••••"
    return f"{val[:prefix_len]}{'•' * 12}{val[-suffix_len:]}"


