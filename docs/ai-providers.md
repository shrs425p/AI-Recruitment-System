# AI Providers

The application supports local AI through Ollama and optional cloud providers. Local mode is the default and is recommended when candidate data must remain on the machine.

## Modes

| Mode | Config | Behavior |
|---|---|---|
| Privacy | `APP_MODE = 'privacy'` | Calls Ollama at `OLLAMA_BASE_URL` |
| Cloud | `APP_MODE = 'cloud'` | Uses enabled cloud providers in fallback order |

## Ollama

Install Ollama from the official site, then pull a model:

```bat
ollama pull llama3.2:3b
```

Recommended models:

| Model | Use |
|---|---|
| `llama3.2:1b` | Very low-resource testing |
| `llama3.2:3b` | Default balance of speed and quality |
| `llama3.1:8b` | Better quality on stronger machines |
| `mistral:7b` | General alternative |
| `qwen2.5:7b` | Strong multilingual resumes |

Verify Ollama:

```bat
curl http://localhost:11434/api/tags
```

## Cloud Providers

Enable only providers approved for your data policy.

| Provider | Key | Enable flag | Model key |
|---|---|---|---|
| Anthropic | `ANTHROPIC_KEY` | `ANTHROPIC_ENABLED` | `ANTHROPIC_MODEL` |
| Gemini | `GEMINI_KEY` | `GEMINI_ENABLED` | `GEMINI_MODEL` |
| Groq | `GROQ_KEY` | `GROQ_ENABLED` | `GROQ_MODEL` |
| OpenAI | `OPENAI_KEY` | `OPENAI_ENABLED` | `OPENAI_MODEL` |
| NVIDIA | `NVIDIA_KEY` | `NVIDIA_ENABLED` | `NVIDIA_MODEL` |
| OpenRouter | `OPENROUTER_KEY` | `OPENROUTER_ENABLED` | `OPENROUTER_MODEL` |
| GitHub Models | `GITHUB_KEY` | `GITHUB_ENABLED` | `GITHUB_MODEL` |
| Ollama Cloud | `OLLAMA_CLOUD_KEY` | `OLLAMA_CLOUD_ENABLED` | `OLLAMA_CLOUD_MODEL` |

## Fallback Order

When cloud mode is active, the provider router tries enabled providers in this order:

```text
Anthropic -> Gemini -> Groq -> OpenAI -> NVIDIA -> OpenRouter -> GitHub -> Ollama Cloud
```

If a provider fails, the router logs the error and tries the next enabled provider.

## Security Guidance

- Store API keys only through Settings or the runtime config.
- Do not commit real keys.
- Use HTTPS provider endpoints.
- Keep local Ollama mode for regulated or sensitive hiring data.
