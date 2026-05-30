# AI Providers

The AI Recruitment System supports two operational modes: **privacy mode** (fully offline via Ollama) and **cloud mode** (one or more external API providers). This document explains how to configure each provider.

---

## Selecting a Mode

Edit `config/config.py`:

```python
APP_MODE = 'privacy'   # Offline Ollama inference
APP_MODE = 'cloud'     # External API provider(s)
```

---

## Ollama (Privacy Mode)

Ollama runs a local inference server. All AI calls remain on the machine.

### Installation

Download and install Ollama from [https://ollama.com](https://ollama.com). After installation, Ollama runs as a background service on port 11434.

### Pulling a Model

```bat
ollama pull llama3.2:3b
```

Recommended models by use case:

| Model | Size | Use Case |
|---|---|---|
| `llama3.2:3b` | 2 GB | Default — balanced speed and quality |
| `llama3.2:1b` | 1.3 GB | Low-RAM systems (4 GB RAM minimum) |
| `llama3.1:8b` | 4.7 GB | Higher quality extraction and ranking |
| `mistral:7b` | 4.1 GB | Alternative general-purpose model |
| `qwen2.5:7b` | 4.7 GB | Strong multilingual resume support |

### Configuration

```python
OLLAMA_MODEL    = 'llama3.2:3b'
OLLAMA_BASE_URL = 'http://localhost:11434'
APP_MODE        = 'privacy'
```

### Verifying the Connection

```bat
curl http://localhost:11434/api/tags
```

A JSON list of installed models should be returned.

---

## Anthropic (Claude)

### Setup

1. Create an account at [https://console.anthropic.com](https://console.anthropic.com).
2. Generate an API key from **Account Settings > API Keys**.
3. Add the key to `config/config.py`:

```python
ANTHROPIC_KEY     = 'sk-ant-...'
ANTHROPIC_MODEL   = 'claude-3-5-haiku-latest'
ANTHROPIC_ENABLED = True
APP_MODE          = 'cloud'
```

### Available Models

| Model | Description |
|---|---|
| `claude-3-5-haiku-latest` | Fast and cost-effective — recommended |
| `claude-3-5-sonnet-latest` | Higher quality reasoning |
| `claude-3-opus-latest` | Maximum capability |

---

## Google Gemini

### Setup

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2. Create a new API key.
3. Configure:

```python
GEMINI_KEY     = 'AIza...'
GEMINI_MODEL   = 'gemini-1.5-flash'
GEMINI_ENABLED = True
APP_MODE       = 'cloud'
```

### Available Models

| Model | Description |
|---|---|
| `gemini-1.5-flash` | Fast, cost-efficient — recommended |
| `gemini-1.5-pro` | Higher quality, higher cost |
| `gemini-2.0-flash` | Latest generation |

---

## Groq

Groq provides extremely fast inference using LPU hardware. Free tier available.

### Setup

1. Register at [https://console.groq.com](https://console.groq.com).
2. Create an API key under **API Keys**.
3. Configure:

```python
GROQ_KEY     = 'gsk_...'
GROQ_MODEL   = 'llama3-8b-8192'
GROQ_ENABLED = True
APP_MODE     = 'cloud'
```

### Available Models

| Model | Context | Description |
|---|---|---|
| `llama3-8b-8192` | 8K | Default — fast and free |
| `llama3-70b-8192` | 8K | High quality |
| `mixtral-8x7b-32768` | 32K | Large context window |

---

## OpenAI

### Setup

1. Create an account at [https://platform.openai.com](https://platform.openai.com).
2. Generate an API key under **API Keys**.
3. Configure:

```python
OPENAI_KEY     = 'sk-...'
OPENAI_MODEL   = 'gpt-4o-mini'
OPENAI_ENABLED = True
APP_MODE       = 'cloud'
```

---

## OpenRouter

OpenRouter provides unified access to hundreds of models from a single API key.

```python
OPENROUTER_KEY     = 'sk-or-...'
OPENROUTER_MODEL   = 'meta-llama/llama-3.1-8b-instruct:free'
OPENROUTER_ENABLED = True
APP_MODE           = 'cloud'
```

---

## Provider Fallback Chain

When `APP_MODE = 'cloud'`, `src/provider_router.py` tries enabled providers in this order:

```
Anthropic -> Gemini -> Groq -> OpenAI -> NVIDIA -> OpenRouter -> GitHub -> Ollama Cloud
```

If the first provider returns an error or times out, the next enabled provider is attempted. If all providers fail, the system returns an empty response and logs the failure.

### Priority Customisation

The order is defined in `src/provider_router.py`. Edit the `PROVIDER_ORDER` list to change priority.

---

## Automatic Ollama Setup (Settings UI)

The Settings page includes a **Setup Local AI** panel. Clicking **Install and Configure** triggers `src/privacy_setup.py`, which:

1. Checks if Ollama is already installed.
2. If not, downloads the Ollama installer from the official URL.
3. Runs the installer silently (`/S` flag).
4. Pulls the configured model via `ollama pull`.

Progress is reported in real time via the UI. An active internet connection is required for this step.
