# AI Providers

This document explains how the AI provider system works, how to set up each provider, and how to choose between Cloud mode and Privacy mode.

---

## Two Modes

### Cloud Mode (`APP_MODE = "cloud"`)

All AI calls go through the `ProviderRouter` in `src/provider_router.py`. The router selects from your enabled cloud providers using round-robin load balancing while respecting each provider's rate limits.

- Requires at least one enabled provider with a valid API key
- Internet connection required
- Faster and more capable models available
- API costs apply (most providers offer free tiers)

### Privacy Mode (`APP_MODE = "privacy"`)

All AI calls go to a **local Ollama server** running on your machine. Nothing leaves the device.

- Requires Ollama installed and running locally
- No internet needed (fully offline)
- Slower — depends on your CPU/GPU
- Falls back to Anthropic cloud if Ollama times out and `CLOUD_ENABLED` is `True`

You can switch modes in Settings → AI Providers → App Mode.

---

## The Provider Router

When in Cloud mode, the `ProviderRouter` class handles selecting which provider to call:

1. Loads all providers marked as `enabled = True` with a non-placeholder API key
2. Filters out providers that have exceeded their RPM (requests per minute) limit in the last 60 seconds
3. Picks the first available provider from the list
4. If all providers are rate-limited, falls back to the first one anyway
5. Logs the call timestamp per provider for RPM tracking

This means you can configure multiple providers simultaneously and the system will automatically spread load and recover from rate limits.

**Placeholder keys are automatically skipped.** If your key is still the default placeholder (e.g. `nvapi-...`, `sk-...`, `AIza...`), that provider will not be used.

---

## Setting Up Each Provider

### NVIDIA NIM *(Default — free credits available)*

1. Go to [build.nvidia.com](https://build.nvidia.com)
2. Sign in or create an account
3. Go to any model page → click **Get API Key**
4. Copy the key (starts with `nvapi-`)
5. In Settings → AI Providers → NVIDIA: paste the key, select a model, enable

**Recommended models:**
- `meta/llama-3.1-8b-instruct` (default, fast, free)
- `meta/llama-3.3-70b-instruct` (more capable)
- `nvidia/nemotron-4-340b-instruct` (most capable, slower)

**Verify:**
```bash
python scripts/verify_providers.py
```

---

### Anthropic (Claude)

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account and add billing
3. Go to API Keys → Create Key
4. Copy the key (starts with `sk-ant-`)
5. In Settings → AI Providers → Anthropic: paste the key, enable

**Recommended models:**
- `claude-3-5-haiku-latest` (default, fast, cheap)
- `claude-3-5-sonnet-latest` (smarter, more expensive)

**Note:** Anthropic is also used as the **Privacy mode fallback** if Ollama times out. Set `CLOUD_ENABLED = True` and `ANTHROPIC_KEY` to enable this.

---

### Gemini (Google)

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API key** → Create API key
3. Copy the key (starts with `AIza`)
4. In Settings → AI Providers → Gemini: paste the key, enable

**Recommended models:**
- `gemini-1.5-flash` (default, fast, generous free tier)
- `gemini-1.5-pro` (more capable)

---

### Groq

1. Go to [console.groq.com](https://console.groq.com)
2. Create an account (free tier available)
3. Go to API Keys → Create API Key
4. Copy the key (starts with `gsk_`)
5. In Settings → AI Providers → Groq: paste the key, enable

**Recommended models:**
- `llama3-8b-8192` (default, very fast, free tier)
- `llama-3.1-70b-versatile` (more capable)

Groq is one of the fastest providers — good for high-volume extraction runs.

---

### OpenAI

1. Go to [platform.openai.com](https://platform.openai.com)
2. Add billing and create an API key
3. Copy the key (starts with `sk-`)
4. In Settings → AI Providers → OpenAI: paste the key, enable

**Recommended models:**
- `gpt-4o-mini` (default, cheap, capable)
- `gpt-4o` (more capable, more expensive)

---

### OpenRouter

OpenRouter is a unified gateway to many models from different providers (Mistral, Meta, Google, etc.) — often with free tiers.

1. Go to [openrouter.ai](https://openrouter.ai)
2. Create an account and add credits (or use free models)
3. Go to API Keys → Create
4. Copy the key (starts with `sk-or-`)
5. In Settings → AI Providers → OpenRouter: paste the key, enter model name, enable

**Free model example:**
- `meta-llama/llama-3.1-8b-instruct:free`

---

### GitHub Models

1. Go to [github.com/marketplace/models](https://github.com/marketplace/models)
2. Create a GitHub personal access token with model access enabled
3. Copy the token (starts with `ghp_`)
4. In Settings → AI Providers → GitHub Models: paste the token, enable

**Recommended models:**
- `gpt-4o-mini` (default)

---

### Ollama (Local)

Ollama runs LLMs locally on your machine with no internet required.

#### Install Ollama
```
https://ollama.com/download
```

#### Pull a model
```bash
ollama pull llama3.2:3b
```

#### Start Ollama (if not already running as a service)
```bash
ollama serve
```

#### In Settings → AI Providers → Local Ollama:
- Set Base URL: `http://localhost:11434` (default)
- Set Model: `llama3.2:3b` (or whatever you pulled)
- Set App Mode to `Privacy` to route all calls through Ollama

**Recommended models by use case:**

| Use Case | Recommended Model |
|---|---|
| Fast, low RAM | `llama3.2:3b` |
| Better quality | `llama3.1:8b` |
| Best local quality | `llama3.1:70b` (requires 32+ GB RAM) |

**GPU acceleration:** If you have an NVIDIA GPU, Ollama automatically uses it. No configuration needed.

---

## Rate Limits Reference

The provider router tracks calls per minute. These are the approximate free tier limits:

| Provider | Free RPM | Notes |
|---|---|---|
| NVIDIA NIM | ~10 | Per model, resets monthly |
| Groq | 30 | Varies by model |
| Gemini | 15 | Flash model on free tier |
| OpenRouter | Varies | Per model |
| Ollama | Unlimited | Local — no limits |

If you are running NLP extraction on many resumes, using multiple providers simultaneously will spread the load and avoid hitting rate limits.

---

## Troubleshooting Providers

**"No cloud providers are enabled"**
→ Go to Settings → AI Providers, enable at least one provider and make sure the API key is not a placeholder.

**Provider returns HTTP 401 / 403**
→ The API key is wrong or expired. Re-check and update in Settings.

**Provider returns HTTP 429**
→ Rate limit hit. The router will automatically skip this provider and try the next one. If only one provider is enabled, add more or wait.

**Ollama not responding**
→ Make sure `ollama serve` is running. Check that the Base URL matches (default: `http://localhost:11434`). Make sure the model is pulled: `ollama list`.
