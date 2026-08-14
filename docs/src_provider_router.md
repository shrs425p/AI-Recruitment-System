# Documentation for `provider_router.py`

**Path:** `src/provider_router.py`

## Module Docstring
No module-level docstring provided.

## Role
The `provider_router.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (_validate_endpoint, sync_http_post, call_provider_sync) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `logging`
- `asyncio`
- `json`
- `time`
- `urllib.error`
- `urllib.request`
- `urllib.parse.urlparse`
- `ai_mode`

### Global Variables
- `logger`
- `router`

### Classes
#### `ProviderRouter`
**Docstring:** Round-robin router across multiple cloud providers.
Tracks per-provider request count to respect RPM limits.
Auto-skips a provider if it is rate limited and tries the next one.

**Methods:**
- `__init__(self)`
  - **Docstring:** No method docstring provided.
- `_key_is_valid(self, provider)`
  - **Docstring:** Return True only if the provider has a real (non-placeholder) API key.
- `get_active_providers(self)`
  - **Docstring:** Dynamic lookup of enabled providers from ai_mode.
- `_is_rate_limited(self, provider)`
  - **Docstring:** Check if this provider has exceeded its RPM in the last 60 seconds.
- `_log_call(self, provider)`
  - **Docstring:** No method docstring provided.
- `get_provider(self)`
  - **Docstring:** Get the next available provider that is enabled and not rate limited.
- `call(self, system_msg, user_msg, max_tokens)`
  - **Docstring:** Query LLM asynchronously using round-robin provider balancing.


### Functions
#### `_validate_endpoint(url)`
**Docstring:** No function docstring provided.

#### `sync_http_post(url, headers, payload)`
**Docstring:** Perform a synchronous HTTP POST request.

#### `call_provider_sync(provider, system_msg, user_msg, max_tokens)`
**Docstring:** Synchronously call a specific cloud provider's API endpoint.
