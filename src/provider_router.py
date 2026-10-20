import logging

logger = logging.getLogger(__name__)
# provider_router.py - Load Balanced Multi-Provider Router with Jittered Backoff

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

try:
    import ai_mode
except ImportError:
    from src import ai_mode


def sanitize_prompt_pii(text: str, candidate_name: str = "") -> str:
    """
    Redact candidate PII (names, emails, phone numbers) from prompt text
    before it is transmitted to external cloud LLM providers.
    """
    if not text:
        return text

    res = text
    # 1. Known candidate name if passed
    if candidate_name and len(candidate_name.strip()) > 1:
        res = re.sub(re.escape(candidate_name.strip()), "[CANDIDATE_NAME]", res, flags=re.IGNORECASE)

    # 2. Labelled candidate names: e.g. "Candidate Name: Alice Smith", "Candidate: Alice Smith", "Applicant: Alice Smith", "Name: Alice Smith"
    res = re.sub(
        r"(?i)\b(candidate(?:\s+name)?|applicant(?:\s+name)?|name)\s*:\s*([A-Z][a-zA-Z\'-]+(?:\s+[A-Z][a-zA-Z\'-]+){1,3})",
        r"\1: [CANDIDATE_NAME]",
        res,
    )

    # 3. Email addresses
    res = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL_REDACTED]", res)

    # 4. Phone numbers
    res = re.sub(r"(?:\+?\d{1,3}[-.\s]*)?\(?\d{3}\)?[-.\s]+\d{3}[-.\s]+\d{4}\b", "[PHONE_REDACTED]", res)
    res = re.sub(r"(?:\+?\d{1,3}[-.\s]*)?\b\d{3}[-.]\d{3}[-.]\d{4}\b", "[PHONE_REDACTED]", res)
    res = re.sub(r"(?:\+?\d{1,3}[-.\s]*)?\b\d{10,12}\b", "[PHONE_REDACTED]", res)

    return res


def _validate_endpoint(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise RuntimeError("Unsupported provider endpoint scheme.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Plain HTTP provider endpoints are only allowed for local Ollama.")


def sync_http_post(url, headers, payload, timeout=90):
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
        with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:400]
        except Exception as e:
            logger.warning('Caught exception: %s', e, exc_info=True)
        parsed_url = urlparse(url)
        sanitized_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        raise RuntimeError(
            f"HTTP {e.code} {e.reason} calling {sanitized_url} "
            f"[model={payload.get('model', payload.get('contents','?'))}] "
            f"- response: {body}"
        ) from e


def _calc_provider_cost(provider_name: str, p_tok: int, c_tok: int) -> float:
    rates = {
        "gemini": (0.000075 / 1000, 0.0003 / 1000),
        "openai": (0.00015 / 1000, 0.0006 / 1000),
        "anthropic": (0.0008 / 1000, 0.004 / 1000),
        "groq": (0.00005 / 1000, 0.00008 / 1000),
        "nvidia": (0.0001 / 1000, 0.0002 / 1000),
        "github": (0.0, 0.0),
        "openrouter": (0.00015 / 1000, 0.0006 / 1000),
        "ollama_cloud": (0.0, 0.0),
    }
    p_rate, c_rate = rates.get(provider_name.lower(), (0.0001 / 1000, 0.0002 / 1000))
    return round((p_tok * p_rate) + (c_tok * c_rate), 6)


def call_provider_sync(provider, system_msg, user_msg, max_tokens, candidate_name="", think=None, format=None):
    """Synchronously call a specific cloud provider's API endpoint with PII sanitized."""
    name = provider["name"]
    key = provider["key"]
    model = provider["model"]

    # Redact candidate PII before transmitting payload to external cloud providers
    sanitized_system_msg = sanitize_prompt_pii(system_msg, candidate_name=candidate_name)
    sanitized_user_msg = sanitize_prompt_pii(user_msg, candidate_name=candidate_name)

    t0 = time.time()
    try:
        if name == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "system": sanitized_system_msg,
                "messages": [{"role": "user", "content": sanitized_user_msg}],
            }
            if think is True and "3-7" in model:
                budget = min(1024, max(1000, max_tokens - 1000))
                payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
            res = sync_http_post(url, headers, payload)
            result_text = json.loads(res)["content"][0]["text"]

        elif name == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": key,
            }
            payload = {
                "contents": [
                    {
                        "parts": [{"text": f"System Instructions:\n{sanitized_system_msg}\n\nUser Question:\n{sanitized_user_msg}"}]
                    }
                ]
            }
            gen_config = {}
            if format == "json":
                gen_config["responseMimeType"] = "application/json"
            if think is False:
                gen_config["thinkingConfig"] = {"thinkingBudget": 0}
            elif think is True and ("2.5" in model or "thinking" in model):
                gen_config["thinkingConfig"] = {"thinkingBudget": -1}
            if gen_config:
                payload["generationConfig"] = gen_config

            res = sync_http_post(url, headers, payload)
            result_text = json.loads(res)["candidates"][0]["content"]["parts"][0]["text"]

        else:
            # OpenAI compatible (groq, openai, nvidia, github, openrouter, ollama_cloud)
            base_url = provider.get("base_url")
            if name == "openai":
                base_url = "https://api.openai.com/v1"
            elif name == "groq":
                base_url = "https://api.groq.com/openai/v1"  # openai not openapi
            elif name == "ollama_cloud":
                base_url = provider.get("key") or provider.get("base_url") or ""
                parsed = urlparse(base_url)
                if parsed.scheme != "https":
                    raise RuntimeError("Ollama Cloud base URL must use HTTPS.")

            url = f"{base_url.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            if name == "ollama_cloud":
                headers = {"Content-Type": "application/json"}  # no auth key required

            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": sanitized_system_msg},
                    {"role": "user", "content": sanitized_user_msg},
                ],
            }
            if format == "json":
                payload["response_format"] = {"type": "json_object"}
            if think is False and any(r in model.lower() for r in ("o1", "o3", "deepseek-r1", "reason")):
                payload["reasoning_effort"] = "low"
            elif think is True and any(r in model.lower() for r in ("o1", "o3", "deepseek-r1", "reason")):
                payload["reasoning_effort"] = "medium"

            res = sync_http_post(url, headers, payload)
            result_text = json.loads(res)["choices"][0]["message"]["content"]

        latency = time.time() - t0
        p_tokens = (len(sanitized_system_msg) + len(sanitized_user_msg)) // 4
        c_tokens = len(result_text) // 4
        cost = _calc_provider_cost(name, p_tokens, c_tokens)
        try:
            from app.database import log_telemetry
            log_telemetry(name, model, p_tokens, c_tokens, latency, "SUCCESS", cost)
        except Exception:
            pass

        return result_text
    except Exception:
        latency = time.time() - t0
        p_tokens = (len(sanitized_system_msg) + len(sanitized_user_msg)) // 4
        try:
            from app.database import log_telemetry
            log_telemetry(name, model, p_tokens, 0, latency, "ERROR", 0.0)
        except Exception:
            pass
        raise



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

    async def call(self, system_msg: str, user_msg: str, max_tokens: int = 2048, candidate_name: str = "", think: bool | None = None, format: str | None = None) -> str:
        """Query LLM asynchronously using round-robin provider balancing with local fallback."""
        active = self.get_active_providers()
        if not active:
            logger.warning("  [WARNING] No cloud providers active. Falling back to local Ollama...")
            from src.common import call_ollama_async
            return await call_ollama_async(system_msg, user_msg, num_predict=max_tokens, think=think, format=format)

        last_error = None
        loop = asyncio.get_running_loop()

        for provider in active:
            try:
                def _sync_wrapper(prov=provider):
                    return call_provider_sync(prov, system_msg, user_msg, max_tokens, candidate_name=candidate_name, think=think, format=format)
                return await loop.run_in_executor(None, _sync_wrapper)
            except Exception as e:
                last_error = e
                logger.warning(f"  [WARNING] Cloud provider '{provider['name']}' failed ({e}). Checking alternatives...")

        # If all cloud providers are rate-limited or failed, fall back to local Ollama
        logger.warning(f"  [WARNING] All cloud providers failed or quota exceeded ({last_error}). Falling back to local Ollama...")
        try:
            from src.common import call_ollama_async
            return await call_ollama_async(system_msg, user_msg, num_predict=max_tokens, think=think, format=format)
        except Exception as oe:
            logger.error(f"  [ERROR] Fallback to local Ollama also failed: {oe}")
            if last_error:
                raise last_error
            raise oe

router = ProviderRouter()
