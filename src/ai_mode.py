import os
from pathlib import Path

import config

_system_drive = os.environ.get("SystemDrive", "C:")
OLLAMA_INSTALL_DIR   = str(Path(_system_drive) / "ollama")            # where to install Ollama silently
OLLAMA_DOWNLOAD_URL  = "https://ollama.com/download/OllamaSetup.exe"   # Windows

def get_app_mode():
    return getattr(config, 'APP_MODE', 'privacy')

def get_privacy_model():
    return getattr(config, 'PRIVACY_MODEL', 'llama3.2:3b')

def get_providers():
    return [
        {
            "name":    "anthropic",
            "enabled": getattr(config, 'ANTHROPIC_ENABLED', False),
            "key":     getattr(config, 'ANTHROPIC_KEY', ''),
            "model":   getattr(config, 'ANTHROPIC_MODEL', 'claude-3-5-haiku-latest'),
            "rpm":     50,
        },
        {
            "name":    "gemini",
            "enabled": getattr(config, 'GEMINI_ENABLED', False),
            "key":     getattr(config, 'GEMINI_KEY', ''),
            "model":   getattr(config, 'GEMINI_MODEL', 'gemini-1.5-flash'),
            "rpm":     60,
        },
        {
            "name":    "groq",
            "enabled": getattr(config, 'GROQ_ENABLED', False),
            "key":     getattr(config, 'GROQ_KEY', ''),
            "model":   getattr(config, 'GROQ_MODEL', 'llama3-8b-8192'),
            "rpm":     30,
        },
        {
            "name":    "openai",
            "enabled": getattr(config, 'OPENAI_ENABLED', False),
            "key":     getattr(config, 'OPENAI_KEY', ''),
            "model":   getattr(config, 'OPENAI_MODEL', 'gpt-4o-mini'),
            "rpm":     60,
        },
        {
            "name":    "nvidia",
            "enabled": getattr(config, 'NVIDIA_ENABLED', False),
            "key":     getattr(config, 'NVIDIA_KEY', ''),
            "model":   getattr(config, 'NVIDIA_MODEL', 'meta/llama-3.3-70b-instruct'),
            "base_url": "https://integrate.api.nvidia.com/v1",
            "rpm":     40,
        },
        {
            "name":    "openrouter",
            "enabled": getattr(config, 'OPENROUTER_ENABLED', False),
            "key":     getattr(config, 'OPENROUTER_KEY', ''),
            "model":   getattr(config, 'OPENROUTER_MODEL', 'meta-llama/llama-3.1-8b-instruct:free'),
            "base_url": "https://openrouter.ai/api/v1",
            "rpm":     30,
        },
        {
            "name":    "github",
            "enabled": getattr(config, 'GITHUB_ENABLED', False),
            "key":     getattr(config, 'GITHUB_KEY', ''),
            "model":   getattr(config, 'GITHUB_MODEL', 'gpt-4o-mini'),
            "base_url": "https://models.inference.ai.azure.com",
            "rpm":     60,
        },
        {
            "name":    "ollama_cloud",
            "enabled": getattr(config, 'OLLAMA_CLOUD_ENABLED', False),
            "key":     getattr(config, 'OLLAMA_CLOUD_KEY', ''),
            "model":   getattr(config, 'OLLAMA_CLOUD_MODEL', 'llama3.2:3b'),
            "base_url": getattr(config, 'OLLAMA_BASE_URL', 'http://localhost:11434'),
            "rpm":     120,
        }

    ]
