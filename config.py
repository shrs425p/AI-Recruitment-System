"""
config.py — Central Configuration for AI Recruitment System
=============================================================
All project-wide settings live here so you only need to change
one file when tuning the AI model or retry behaviour.

How to use:
  from config import OLLAMA_MODEL, AI_RETRY_ATTEMPTS, AI_RETRY_BACKOFF
"""

# ─────────────────────────────────────────────
# HR LOGIN / SECURITY
# ─────────────────────────────────────────────

LOGIN_ENABLED = False
HR_USERNAME = 'admin'
HR_PASSWORD = 'admin'
FLASK_SECRET_KEY = 'ars_secure_key_2026'

# ─────────────────────────────────────────────
# HR PROFILE (shown on Settings page)
# ─────────────────────────────────────────────
HR_DISPLAY_NAME = 'HR Admin'
HR_EMAIL        = ''
HR_COMPANY      = ''

# ─────────────────────────────────────────────
# UI THEME  ("light" or "dark")
# ─────────────────────────────────────────────
THEME = 'light'

# ─────────────────────────────────────────────
# OLLAMA SETTINGS
# ─────────────────────────────────────────────
OLLAMA_MODEL    = 'cogito-2.1:671b-cloud'
OLLAMA_BASE_URL = 'http://localhost:11434'

# ─────────────────────────────────────────────
# EMAIL / SMTP SETTINGS (Gmail App Password)
# ─────────────────────────────────────────────
SMTP_HOST     = 'smtp.gmail.com'
SMTP_PORT     = 587
SMTP_EMAIL    = 'pawarshreyas425@gmail.com'
SMTP_PASSWORD = 'rvxi pjhu gylk zrsa'

# ─────────────────────────────────────────────
# RETRY / BACKOFF SETTINGS
# ─────────────────────────────────────────────
AI_RETRY_ATTEMPTS  = 3
AI_RETRY_BACKOFF   = 2
