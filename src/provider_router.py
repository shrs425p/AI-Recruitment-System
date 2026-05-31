# provider_router.py - Load Balanced Multi-Provider Router with Jittered Backoff

import asyncio
import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

import ai_mode


def _validate_endpoint(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise RuntimeError("Unsupported provider endpoint scheme.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Plain HTTP provider endpoints are only allowed for local Ollama.")


def sync_http_post(url, headers, payload):
    """Perform a synchronous HTTP POST request."""
    _validate_endpoint(url)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        # Endpoint scheme is validated above.
        with urllib.request.urlopen(req, timeout=60) as response:  # nosec B310
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        raise RuntimeError(
            f"HTTP {e.code} {e.reason} calling {url} "
            f"[model={payload.get('model', payload.get('contents','?'))}] "
            f"- response: {body}"
        ) from e


def call_provider_sync(provider, system_msg, user_msg, max_tokens):
    """Synchronously call a specific cloud provider's API endpoint."""
    name = provider["name"]
    key = provider["key"]
    model = provider["model"]

    if name == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_msg,
            "messages": [{"role": "user", "content": user_msg}]
        }
        res = sync_http_post(url, headers, payload)
        return json.loads(res)["content"][0]["text"]

    elif name == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [{"text": f"System Instructions:\n{system_msg}\n\nUser Question:\n{user_msg}"}]
                }
            ]
        }
        res = sync_http_post(url, headers, payload)
        return json.loads(res)["candidates"][0]["content"]["parts"][0]["text"]

    else:
        # OpenAI compatible (groq, openai, nvidia, github, openrouter, ollama_cloud)
        base_url = provider.get("base_url")
        if name == "openai":
            base_url = "https://api.openai.com/v1"
        elif name == "groq":
            base_url = "https://api.groq.com/openai/v1"  # openai not openapi

        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        if name == "ollama_cloud":
            headers = {"Content-Type": "application/json"} # no auth key required

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ]
        }
        res = sync_http_post(url, headers, payload)
        return json.loads(res)["choices"][0]["message"]["content"]


class ProviderRouter:
    """
    Round-robin router across multiple cloud providers.
    Tracks per-provider request count to respect RPM limits.
    Auto-skips a provider if it is rate limited and tries the next one.
    """

    def __init__(self):
        self.call_log  = {}  # timestamps of calls per provider
        self._lock     = asyncio.Lock()

    def _key_is_valid(self, provider: dict) -> bool:
        """Return True only if the provider has a real (non-placeholder) API key."""
        name = provider["name"]
        key  = provider.get("key", "")
        if name == "ollama_cloud":   # no key required
            return True
        if not key or not key.strip():
            return False
        # Reject exact placeholder strings that ship in the default config.
        # Use exact-match, NOT startswith; real NVIDIA keys start with 'nvapi-'
        # and real Groq keys start with 'gsk_', so prefix matching would wrongly
        # reject them.
        PLACEHOLDER_EXACT = {
            "sk-ant-...", "sk-...", "AIza...", "gsk_...", "nvapi-...",
            "ghp_...", "sk-or-...",
        }
        return key.strip() not in PLACEHOLDER_EXACT

    def get_active_providers(self):
        """Dynamic lookup of enabled providers from ai_mode."""
        return [p for p in ai_mode.get_providers() if p["enabled"] and self._key_is_valid(p)]

    def _is_rate_limited(self, provider: dict) -> bool:
        """Check if this provider has exceeded its RPM in the last 60 seconds."""
        now = time.time()
        name = provider["name"]
        rpm = provider["rpm"]

        if name not in self.call_log:
            self.call_log[name] = []

        # Keep only calls from last 60 seconds
        self.call_log[name] = [t for t in self.call_log[name] if now - t < 60]
        return len(self.call_log[name]) >= rpm

    def _log_call(self, provider: dict):
        name = provider["name"]
        if name not in self.call_log:
            self.call_log[name] = []
        self.call_log[name].append(time.time())

    async def get_provider(self) -> dict:
        """Get the next available provider that is enabled and not rate limited."""
        async with self._lock:
            active = self.get_active_providers()
            if not active:
                raise RuntimeError("No cloud providers are enabled in Settings! Please enable at least one provider.")

            # Try to find one not rate limited
            for provider in active:
                if not self._is_rate_limited(provider):
                    self._log_call(provider)
                    return provider

            # If all are rate limited, pick the first active one as fallback
            self._log_call(active[0])
            return active[0]

    async def call(self, system_msg: str, user_msg: str, max_tokens: int = 2048) -> str:
        """Query LLM asynchronously using round-robin provider balancing."""
        provider = await self.get_provider()

        def _sync_wrapper():
            return call_provider_sync(provider, system_msg, user_msg, max_tokens)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_wrapper)

router = ProviderRouter()
