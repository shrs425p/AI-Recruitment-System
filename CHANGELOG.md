# Changelog

All notable changes to AI Recruitment System are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] — 2026-05-30

### Added

- Full offline-first recruitment pipeline (PDF upload → OCR → NLP → Ranking → Scheduling → Interview)
- Multi-provider cloud AI router with round-robin load balancing and RPM rate limiting
  - NVIDIA NIM, Anthropic Claude, Google Gemini, Groq, OpenAI, OpenRouter, GitHub Models
- Privacy Mode — fully offline local inference via Ollama (zero data leaves the machine)
- Cloud Mode — live model listing via each provider's `/models` API endpoint
- One-click Offline/Cloud toggle in the sidebar (persists across restarts)
- Settings persist to `config/config.py` on every save (all 35+ keys)
- Tesseract OCR fallback for scanned/image-based PDFs
- Google Calendar integration for interview scheduling (OAuth 2.0)
- AI-powered interview proctor (face detection via OpenCV Haar cascade, MediaPipe optional)
- PDF and ICS export for scheduling summaries
- Email invitations via SMTP (Gmail App Password)
- Live log streaming to the Settings → Logs terminal
- Material Design 3 UI with light/dark theme and 4 color palette options
- GitHub Actions CI/CD workflows (CI, Bandit, CodeQL, Dependency Review, Stale, AI Summary)
- Dependabot configuration for daily dependency updates
- Pre-commit hooks (Ruff, file hygiene, Bandit, secret detection)
- Full documentation suite (13 Markdown files in `docs/`)

### Fixed

- SSL certificate generation migrated from `pyOpenSSL` to `cryptography` library
- Tesseract path resolution on Windows (`models/Tesseract-OCR/`)
- `asyncio.run()` used consistently — no `get_event_loop()` deprecation warnings
- Provider router rejects placeholder API keys via exact-string match
- NVIDIA model name corrected to `meta/llama-3.3-70b-instruct`
- Groq base URL corrected (`openai/v1` not `openapi/v1`)
- Scheduling page crash (`cal_status` was missing from template context)
- Config persistence — settings no longer reset on application restart

---

## [0.9.0] — 2026-04-15

### Added

- Initial private release
- Resume upload and PDF-to-text pipeline
- Basic NLP extraction (skills, experience, education)
- Candidate ranking leaderboard
- Interview scheduling with ICS generation
- pywebview desktop wrapper

---

[1.0.0]: https://github.com/shrs425p/AI-Recruitment-System/releases/tag/v1.0.0
[0.9.0]: https://github.com/shrs425p/AI-Recruitment-System/releases/tag/v0.9.0
