"""
config.py — Central Configuration for AI Recruitment System
All settings are written here automatically when saved via the Settings UI.
"""

# Login / Security
LOGIN_ENABLED = True
HR_USERNAME = 'admin'
HR_PASSWORD = 'shrs'
FLASK_SECRET_KEY = 'ars_secure_key_2026'

# HR Profile
HR_DISPLAY_NAME = 'HR Admin'
HR_EMAIL = ''
HR_COMPANY = ''

# UI Theme
THEME = 'light'
COLOR_PALETTE = 'lavender'

# Ollama
OLLAMA_MODEL = 'llama3.2:3b'
OLLAMA_BASE_URL = 'http://localhost:11434'

# Legacy cloud aliases (kept for compatibility)
CLOUD_ENABLED = True
CLOUD_MODEL = 'claude-3-5-haiku-latest'

# SMTP / Email
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_EMAIL = 'pawarshreyas425@gmail.com'
SMTP_PASSWORD = 'rvxi pjhu gylk zrsa'

# Retry / Backoff
AI_RETRY_ATTEMPTS = 3
AI_RETRY_BACKOFF = 2

# AI Mode  ('privacy' = local Ollama, 'cloud' = external API)
APP_MODE = 'cloud'

# API Keys
ANTHROPIC_KEY = 'fucku'
GEMINI_KEY = 'fucku'
GROQ_KEY = ''
OPENAI_KEY = ''
NVIDIA_KEY = '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'
OPENROUTER_KEY = ''
GITHUB_KEY = ''
OLLAMA_CLOUD_KEY = ''

# Models
PRIVACY_MODEL = 'llama3.2:3b'
ANTHROPIC_MODEL = 'claude-3-5-haiku-latest'
GEMINI_MODEL = 'gemini-1.5-flash'
GROQ_MODEL = 'llama3-8b-8192'
OPENAI_MODEL = 'gpt-4o-mini'
NVIDIA_MODEL = 'openai/gpt-oss-120b'
OPENROUTER_MODEL = 'meta-llama/llama-3.1-8b-instruct:free'
GITHUB_MODEL = 'gpt-4o-mini'
OLLAMA_CLOUD_MODEL = 'llama3.2:3b'

# Enabled Providers
ANTHROPIC_ENABLED = True
GEMINI_ENABLED = True
GROQ_ENABLED = False
OPENAI_ENABLED = False
NVIDIA_ENABLED = True
OPENROUTER_ENABLED = False
GITHUB_ENABLED = False
OLLAMA_CLOUD_ENABLED = False
