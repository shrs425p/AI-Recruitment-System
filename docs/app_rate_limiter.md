# Documentation for `rate_limiter.py`

**Path:** `app/rate_limiter.py`

## Module Docstring
No module-level docstring provided.

## Role
The `rate_limiter.py` module acts as a foundational component for the AI Recruitment System.

## Working
It provides necessary utilities, classes, or application entry points for the broader system.

## How it works
It defines key structures (like 1 classes and 0 functions) that other modules rely upon for execution.

## Why it works
By providing these standardized utilities, the module reduces code duplication and ensures consistent behavior across the repository.

## Detailed Components

### Imports
- `threading`
- `time`
- `collections.defaultdict`

### Global Variables
No global variables found.

### Classes
#### `SimpleRateLimiter`
**Docstring:** Thread-safe, in-memory token-bucket rate limiter.

Used to protect candidate APIs from request flooding or token guessing.

**Methods:**
- `__init__(self, requests_per_minute)`
  - **Docstring:** No method docstring provided.
- `is_allowed(self, key)`
  - **Docstring:** Check if request from key is allowed under rate limit.
- `clear(self)`
  - **Docstring:** Reset rate limiter state (useful for tests).


### Functions
No functions found.
