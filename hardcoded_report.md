# Hardcoded Values Report

This report outlines hardcoded paths, IPs, localhost references, URLs, and potential secrets found in the codebase.

### `./main.py`
- Line 42: **Localhost** -> `localhost`
- Line 42: **HTTP URLs** -> `http://localhost:11434`
- Line 306: **Localhost** -> `localhost`
- Line 352: **IP Addresses** -> `127.0.0.1`
- Line 357: **IP Addresses** -> `127.0.0.1`
- Line 361: **IP Addresses** -> `127.0.0.1`
- Line 363: **IP Addresses** -> `127.0.0.1`
- Line 384: **IP Addresses** -> `127.0.0.1`
- Line 384: **HTTP URLs** -> `http://127.0.0.1:`

### `./pyproject.toml`
- Line 31: **HTTP URLs** -> `https://github.com/shrs425p/AI-Recruitment-System`
- Line 32: **HTTP URLs** -> `https://github.com/shrs425p/AI-Recruitment-System`
- Line 33: **HTTP URLs** -> `https://github.com/shrs425p/AI-Recruitment-System/tree/main/docs`
- Line 34: **HTTP URLs** -> `https://github.com/shrs425p/AI-Recruitment-System/issues`
- Line 35: **HTTP URLs** -> `https://github.com/shrs425p/AI-Recruitment-System/blob/main/CHANGELOG.md`

### `./app/utils.py`
- Line 261: **IP Addresses** -> `127.0.0.1`
- Line 261: **Localhost** -> `localhost`

### `./app/templates/scheduling.html`
- Line 73: **HTTP URLs** -> `https://console.cloud.google.com`

### `./app/templates/settings.html`
- Line 558: **Localhost** -> `localhost`
- Line 558: **HTTP URLs** -> `http://localhost:11434`

### `./app/templates/login.html`
- Line 8: **HTTP URLs** -> `https://fonts.googleapis.com`
- Line 9: **HTTP URLs** -> `https://fonts.gstatic.com`
- Line 10: **HTTP URLs** -> `https://fonts.googleapis.com/css2?family=Outfit:wght`

### `./app/templates/candidate_interview.html`
- Line 9: **HTTP URLs** -> `https://fonts.googleapis.com`
- Line 10: **HTTP URLs** -> `https://fonts.gstatic.com`
- Line 11: **HTTP URLs** -> `https://fonts.googleapis.com/css2?family=Outfit:wght`
- Line 959: **Secrets & Passwords** -> `TOKEN = "{{ token }}"`

### `./app/templates/ranking.html`
- Line 144: **HTTP URLs** -> `https://cdn.jsdelivr.net/npm/chart.js`

### `./app/templates/base.html`
- Line 9: **HTTP URLs** -> `https://fonts.googleapis.com`
- Line 10: **HTTP URLs** -> `https://fonts.gstatic.com`
- Line 11: **HTTP URLs** -> `https://fonts.googleapis.com/css2?family=Outfit:wght`

### `./app/routes/settings.py`
- Line 187: **HTTP URLs** -> `https://integrate.api.nvidia.com/v1/models`
- Line 188: **HTTP URLs** -> `https://api.openai.com/v1/models`
- Line 189: **HTTP URLs** -> `https://api.groq.com/openai/v1/models`
- Line 190: **HTTP URLs** -> `https://openrouter.ai/api/v1/models`
- Line 191: **HTTP URLs** -> `https://models.inference.ai.azure.com/models`
- Line 192: **Localhost** -> `localhost`
- Line 192: **HTTP URLs** -> `http://localhost:11434/api/tags`
- Line 202: **IP Addresses** -> `127.0.0.1`
- Line 202: **Localhost** -> `localhost`

### `./app/routes/interview.py`
- Line 123: **IP Addresses** -> `127.0.0.1`

### `./src/voice_interview.py`
- Line 20: **HTTP URLs** -> `https://alphacephei.com/vosk/models`

### `./src/ai_mode.py`
- Line 8: **HTTP URLs** -> `https://ollama.com/download/OllamaSetup.exe`
- Line 51: **HTTP URLs** -> `https://integrate.api.nvidia.com/v1`
- Line 59: **HTTP URLs** -> `https://openrouter.ai/api/v1`
- Line 67: **HTTP URLs** -> `https://models.inference.ai.azure.com`
- Line 75: **Localhost** -> `localhost`
- Line 75: **HTTP URLs** -> `http://localhost:11434`

### `./src/ranking_engine.py`
- Line 225: **Secrets & Passwords** -> `key = "|"`

### `./src/google_calendar.py`
- Line 24: **HTTP URLs** -> `https://www.googleapis.com/auth/calendar`
- Line 400: **HTTP URLs** -> `https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project=`
- Line 402: **HTTP URLs** -> `https://console.cloud.google.com/apis/library/calendar-json.googleapis.com`
- Line 438: **HTTP URLs** -> `https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project=`
- Line 440: **HTTP URLs** -> `https://console.cloud.google.com/apis/library/calendar-json.googleapis.com`

### `./src/provider_router.py`
- Line 17: **IP Addresses** -> `127.0.0.1`
- Line 17: **Localhost** -> `localhost`
- Line 54: **HTTP URLs** -> `https://api.anthropic.com/v1/messages`
- Line 70: **HTTP URLs** -> `https://generativelanguage.googleapis.com/v1beta/models/`
- Line 86: **HTTP URLs** -> `https://api.openai.com/v1`
- Line 88: **HTTP URLs** -> `https://api.groq.com/openai/v1`

### `./scripts/test_nvidia_models.py`
- Line 10: **HTTP URLs** -> `https://integrate.api.nvidia.com/v1/chat/completions`

### `./scripts/setup_vosk.py`
- Line 7: **HTTP URLs** -> `https://alphacephei.com/vosk/models`
- Line 22: **HTTP URLs** -> `https://alphacephei.com/vosk/models/vosk-model-small-en-in-0.4.zip`
- Line 29: **HTTP URLs** -> `https://alphacephei.com/vosk/models/vosk-model-en-in-0.5.zip`

### `./scripts/build_installer.bat`
- Line 10: **HTTP URLs** -> `https://jrsoftware.org/isdl.php`
- Line 11: **Absolute Windows Paths** -> `C:\Program`
- Line 60: **Absolute Windows Paths** -> `C:\Program`
- Line 61: **Absolute Windows Paths** -> `C:\Program`
- Line 62: **Absolute Windows Paths** -> `C:\Program`
- Line 63: **Absolute Windows Paths** -> `C:\Program`
- Line 69: **HTTP URLs** -> `https://jrsoftware.org/isdl.php`
- Line 71: **Absolute Windows Paths** -> `C:\...\ISCC.exe`

### `./scripts/verify_environment.py`
- Line 97: **Localhost** -> `localhost`
- Line 97: **HTTP URLs** -> `http://localhost:11434/api/tags`
- Line 100: **Localhost** -> `localhost`
- Line 100: **HTTP URLs** -> `http://localhost:11434`
- Line 103: **Localhost** -> `localhost`
- Line 103: **HTTP URLs** -> `http://localhost:11434:`

### `./tests/test_auth.py`
- Line 12: **Secrets & Passwords** -> `key = "test-secret"`
- Line 53: **IP Addresses** -> `192.168.1.50`
- Line 69: **IP Addresses** -> `192.168.1.50`

### `./tests/test_rate_limiter.py`
- Line 6: **IP Addresses** -> `127.0.0.1`
- Line 6: **Secrets & Passwords** -> `key = "127.0.0.1"`
- Line 15: **IP Addresses** -> `192.168.1.10`
- Line 15: **Secrets & Passwords** -> `key = "192.168.1.10"`
- Line 24: **IP Addresses** -> `10.0.0.1`
- Line 24: **Secrets & Passwords** -> `key = "10.0.0.1"`

### `./tests/test_features.py`
- Line 110: **Localhost** -> `localhost`
- Line 113: **Secrets & Passwords** -> `password="pass"`

### `./tests/test_interview_session.py`
- Line 15: **IP Addresses** -> `127.0.0.1`
- Line 25: **IP Addresses** -> `127.0.0.1`

### `./tests/test_candidate_security.py`
- Line 89: **IP Addresses** -> `192.168.1.20`
- Line 102: **IP Addresses** -> `192.168.1.99`

### `./tests/test_auto_pipeline.py`
- Line 26: **Secrets & Passwords** -> `key = "test-secret"`
