# Documentation for `security.py`

**Path:** `src/security.py`

## Module Docstring
src/security.py — Secret Encryption & Security Module
Provides salted AES-Fernet encryption for sensitive credentials stored in the SQLite database.

## Role
The `security.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (_get_fernet, encrypt_secret, decrypt_secret) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `base64`
- `os`
- `pathlib.Path`
- `cryptography.fernet.Fernet`
- `cryptography.hazmat.primitives.hashes`
- `cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC`
- `src.common.APP_DATA_DIR`
- `src.common.APP_NAME`

### Global Variables
- `SENSITIVE_KEYS`
- `_fernet_instance`

### Classes
No classes found.

### Functions
#### `_get_fernet()`
**Docstring:** No function docstring provided.

#### `encrypt_secret(plaintext)`
**Docstring:** Encrypt a plaintext string using salted AES-Fernet. Returns an ENC:... prefixed token.

#### `decrypt_secret(ciphertext)`
**Docstring:** Decrypt an ENC:... prefixed token back to plaintext in memory.
