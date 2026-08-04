import json
from urllib.parse import urlparse

from flask import jsonify, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

import config as cfg
from app.utils import login_required


def register_settings_routes(app):
    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        if request.method == "POST":
            # ── Security / Login ──
            cfg.LOGIN_ENABLED = request.form.get("login_enabled") == "on"
            cfg.HR_USERNAME    = request.form.get("hr_username", cfg.HR_USERNAME).strip()
            new_pw = request.form.get("hr_password", "").strip()
            if new_pw:
                cfg.HR_PASSWORD = ""
                cfg.HR_PASSWORD_HASH = generate_password_hash(new_pw)
            # ── Theme & Palette ──
            cfg.THEME = request.form.get("theme", "light")
            cfg.COLOR_PALETTE = request.form.get("color_palette", "lavender")
            # ── Profile ──
            cfg.HR_DISPLAY_NAME = request.form.get("display_name", "").strip()
            cfg.HR_EMAIL        = request.form.get("email", "").strip()
            cfg.HR_COMPANY      = request.form.get("company", "").strip()

            # ── Ollama / AI Mode ──
            if "ollama_model" in request.form:
                cfg.OLLAMA_MODEL   = request.form.get("ollama_model", cfg.OLLAMA_MODEL).strip()
                cfg.OLLAMA_BASE_URL = request.form.get("ollama_base_url", cfg.OLLAMA_BASE_URL).strip()

            if "app_mode" in request.form:
                cfg.APP_MODE = request.form.get("app_mode", "privacy").strip()
                cfg.ANTHROPIC_KEY = request.form.get("anthropic_key", "").strip()
                cfg.GEMINI_KEY    = request.form.get("gemini_key", "").strip()
                cfg.GROQ_KEY      = request.form.get("groq_key", "").strip()
                cfg.OPENAI_KEY    = request.form.get("openai_key", "").strip()
                cfg.NVIDIA_KEY    = request.form.get("nvidia_key", "").strip()
                cfg.OPENROUTER_KEY = request.form.get("openrouter_key", "").strip()
                cfg.GITHUB_KEY    = request.form.get("github_key", "").strip()
                cfg.OLLAMA_CLOUD_KEY = request.form.get("ollama_cloud_key", "").strip()

                cfg.PRIVACY_MODEL   = request.form.get("privacy_model", "llama3.2:3b").strip()
                cfg.ANTHROPIC_MODEL = request.form.get("anthropic_model", "claude-3-5-haiku-latest").strip()
                cfg.GEMINI_MODEL    = request.form.get("gemini_model", "gemini-1.5-flash").strip()
                cfg.GROQ_MODEL      = request.form.get("groq_model", "llama3-8b-8192").strip()
                cfg.OPENAI_MODEL    = request.form.get("openai_model", "gpt-4o-mini").strip()
                cfg.NVIDIA_MODEL    = request.form.get("nvidia_model", "meta/llama-3.1-nemotron-70b-instruct").strip()
                cfg.OPENROUTER_MODEL = request.form.get("openrouter_model", "meta-llama/llama-3.1-8b-instruct:free").strip()
                cfg.GITHUB_MODEL    = request.form.get("github_model", "gpt-4o-mini").strip()
                cfg.OLLAMA_CLOUD_MODEL = request.form.get("ollama_cloud_model", "llama3.2:3b").strip()

                cfg.ANTHROPIC_ENABLED = request.form.get("anthropic_enabled") == "on"
                cfg.GEMINI_ENABLED    = request.form.get("gemini_enabled") == "on"
                cfg.GROQ_ENABLED      = request.form.get("groq_enabled") == "on"
                cfg.OPENAI_ENABLED    = request.form.get("openai_enabled") == "on"
                cfg.NVIDIA_ENABLED    = request.form.get("nvidia_enabled") == "on"
                cfg.OPENROUTER_ENABLED = request.form.get("openrouter_enabled") == "on"
                cfg.GITHUB_ENABLED    = request.form.get("github_enabled") == "on"
                cfg.OLLAMA_CLOUD_ENABLED = request.form.get("ollama_cloud_enabled") == "on"

                cfg.OLLAMA_MODEL = cfg.PRIVACY_MODEL

            # ── Email / SMTP & Templates ──
            if "smtp_email" in request.form or "email_template_subject" in request.form:
                cfg.SMTP_EMAIL    = request.form.get("smtp_email", cfg.SMTP_EMAIL).strip()
                cfg.SMTP_PASSWORD = request.form.get("smtp_password", cfg.SMTP_PASSWORD).strip()
                cfg.SMTP_HOST     = request.form.get("smtp_host", cfg.SMTP_HOST).strip()
                try:
                    cfg.SMTP_PORT = int(request.form.get("smtp_port", cfg.SMTP_PORT))
                except Exception:
                    pass
                if "email_template_subject" in request.form:
                    cfg.EMAIL_TEMPLATE_SUBJECT = request.form.get("email_template_subject", getattr(cfg, "EMAIL_TEMPLATE_SUBJECT", "")).strip()
                    cfg.EMAIL_TEMPLATE_BODY = request.form.get("email_template_body", getattr(cfg, "EMAIL_TEMPLATE_BODY", "")).strip()

            import main
            main._save_config(cfg)
            return redirect(url_for("settings"))

        about_html = (
            "<div style='display:flex; align-items:center; gap:20px; margin-bottom:24px; padding:20px; background:var(--md-sys-color-surface-container-low); border:1px solid var(--md-sys-color-outline-variant); border-radius:var(--radius-lg);'>"
            "<img src='/static/icon/ai.png' alt='AI Logo' style='width:64px; height:64px; border-radius:16px; object-fit:contain; box-shadow:var(--elevation-1);'>"
            "<div>"
            "<h2 style='margin:0 0 4px 0; border:none; padding:0; font-size:24px; font-weight:800;'>AI Recruitment System</h2>"
            "<p style='margin:0; font-size:13px; color:var(--md-sys-color-primary); font-weight:600;'>v1.1.0 Enterprise Edition — Offline-First Talent Acquisition Platform</p>"
            "</div>"
            "</div>"
            "<p>The AI Recruitment System is an enterprise-grade desktop application engineered for modern HR teams and talent acquisition specialists. It automates end-to-end recruitment pipelines—including resume intake, OCR text extraction, structured candidate profiling, objective ranking, automated scheduling, interactive evaluations, AI proctoring, and executive reporting.</p>"
            "<h3>Core Architectural Capabilities</h3>"
            "<ol>"
            "<li><strong>Intake &amp; OCR Engine:</strong> High-speed extraction for digital PDFs via PyMuPDF and scanned document images (PNG/JPG) using embedded Tesseract OCR.</li>"
            "<li><strong>Structured Profile Extraction:</strong> Natural Language Processing (NLP) converts raw text into standardized JSON candidate profiles detailing technical skills, work experience, education, and domain expertise.</li>"
            "<li><strong>Objective Leaderboard Ranking:</strong> Job Description template library and weighted scoring algorithm rank candidates objectively against target role requirements.</li>"
            "<li><strong>Calendar &amp; Scheduling Automation:</strong> Automated slot coordination, iCalendar (.ics) invitation generation, and 2-way Google Calendar API synchronization.</li>"
            "<li><strong>Interactive Evaluation Portal:</strong> Secure token-authenticated portal supporting both <strong>Text</strong> and offline <strong>Voice</strong> (Vosk STT &amp; pyttsx3 TTS) response modes.</li>"
            "<li><strong>AI Proctoring &amp; Security:</strong> Real-time MediaPipe and OpenCV Haar Cascade webcam face detection combined with browser tab-switch and copy-paste violation logging.</li>"
            "<li><strong>Live System Console:</strong> Streaming log history buffer enabling real-time monitoring of background jobs, database transactions, and model inference.</li>"
            "<li><strong>Executive Analytics:</strong> Exportable shortlist reports, candidate evaluation cards, and aggregate hiring pool summaries.</li>"
            "</ol>"
            "<h3>Technology &amp; Security Stack</h3>"
            "<p>Built on a resilient, multi-threaded local architecture:</p>"
            "<ul>"
            "<li><strong>Application Framework:</strong> Python 3.12, Flask 3.0, pywebview Desktop Frame</li>"
            "<li><strong>Data Persistence:</strong> SQLite in Write-Ahead Logging (WAL) mode with busy timeout handling</li>"
            "<li><strong>Privacy &amp; AI Execution:</strong> Zero-egress local LLMs via Ollama (llama3.2, mistral) with optional cloud API routing (OpenAI, Claude, Gemini, Groq)</li>"
            "<li><strong>Security Middleware:</strong> Request rate-limiting, session TTL expiration, and PBKDF2 credential hashing</li>"
            "</ul>"
            "<h3>Demographic Neutrality &amp; Fairness Policy</h3>"
            "<p>The application enforces strict anti-bias protocols across all evaluation stages:</p>"
            "<ul>"
            "<li>Ranking scores are computed <em>exclusively</em> from verified skills, education, and relevant work experience matched against role requirements.</li>"
            "<li>Candidate names, age, gender, ethnicity, and demographic identifiers are <strong>strictly excluded</strong> from LLM scoring prompts.</li>"
            "<li>Interview questions are dynamically constructed from job responsibilities and technical domains, never personal attributes.</li>"
            "<li>All compiled reports include an audited fairness verification line confirming non-discriminatory scoring.</li>"
            "</ul>"
        )
        return render_template("settings.html", cfg=cfg, about_html=about_html)

    @app.route("/about")
    def about_page():
        return render_template("about.html", about_html=about_html)

    @app.route("/api/toggle-theme", methods=["POST"])
    def api_toggle_theme():
        cfg.THEME = "dark" if cfg.THEME == "light" else "light"
        import main
        main._save_config(cfg)
        return jsonify({"success": True, "theme": cfg.THEME})

    @app.route("/api/change-theme", methods=["POST"])
    def api_change_theme():
        data = request.json or {}
        theme = data.get("theme", "light")
        cfg.THEME = theme
        import main
        main._save_config(cfg)
        return jsonify({"success": True, "theme": cfg.THEME})

    @app.route("/api/change-palette", methods=["POST"])
    def api_change_palette():
        data = request.json or {}
        palette = data.get("palette", "lavender")
        cfg.COLOR_PALETTE = palette
        import main
        main._save_config(cfg)
        return jsonify({"success": True, "palette": palette})

    @app.route("/api/toggle-ai-mode", methods=["POST"])
    def api_toggle_ai_mode():
        cfg.APP_MODE = "cloud" if getattr(cfg, "APP_MODE", "privacy") == "privacy" else "privacy"
        import main
        main._save_config(cfg)
        return jsonify({"success": True, "mode": cfg.APP_MODE})

    @app.route("/api/provider-models", methods=["POST"])
    def api_provider_models():
        """Fetch available model IDs from a cloud provider's API."""
        import urllib.error
        import urllib.request
        data     = request.json or {}
        provider = data.get("provider", "")
        key      = data.get("key", "").strip()

        STATIC_LISTS = {
            "anthropic": [
                "claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5",
                "claude-3-7-sonnet-latest", "claude-3-5-sonnet-latest",
                "claude-3-5-haiku-latest", "claude-3-opus-latest",
            ],
            "gemini": [
                "gemini-2.5-flash-preview-05-20", "gemini-2.5-pro-preview-06-05",
                "gemini-2.0-flash", "gemini-2.0-flash-lite",
                "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro",
            ],
        }

        if provider in STATIC_LISTS:
            return jsonify({"success": True, "models": STATIC_LISTS[provider], "source": "static"})

        # OpenAI-compatible /models endpoints
        ENDPOINTS = {
            "nvidia":      ("https://integrate.api.nvidia.com/v1/models",       "Bearer"),
            "openai":      ("https://api.openai.com/v1/models",                 "Bearer"),
            "groq":        ("https://api.groq.com/openai/v1/models",            "Bearer"),
            "openrouter":  ("https://openrouter.ai/api/v1/models",              "Bearer"),
            "github":      ("https://models.inference.ai.azure.com/models",     "Bearer"),
            "ollama_cloud":("http://localhost:11434/api/tags",                   "None"),
        }

        if provider not in ENDPOINTS:
            return jsonify({"success": False, "error": f"Unknown provider: {provider}"}), 400

        url, auth_scheme = ENDPOINTS[provider]
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"https", "http"}:
            return jsonify({"success": False, "error": "Unsupported provider endpoint scheme."}), 400
        if parsed_url.scheme == "http" and parsed_url.hostname not in {"localhost", "127.0.0.1"}:
            return jsonify({"success": False, "error": "Plain HTTP is only allowed for local Ollama."}), 400

        headers = {"Content-Type": "application/json"}
        if auth_scheme == "Bearer" and key:
            headers["Authorization"] = f"Bearer {key}"

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            # ENDPOINTS is a fixed allowlist and _validate_endpoint checks the scheme.
            with urllib.request.urlopen(req, timeout=15) as r:  # nosec B310
                raw = json.loads(r.read())

            # Ollama tags format
            if provider == "ollama_cloud":
                models = sorted(m["name"] for m in raw.get("models", []))
            # OpenRouter returns data[*].id
            elif "data" in raw:
                models = sorted(m["id"] for m in raw["data"] if m.get("id"))
            # Fallback
            else:
                models = sorted(str(m) for m in raw.get("models", []))

            return jsonify({"success": True, "models": models, "source": "api", "count": len(models)})

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            return jsonify({"success": False, "error": f"HTTP {e.code}: {body}"}), 400
        except Exception as ex:
            return jsonify({"success": False, "error": str(ex)}), 500

    @app.route("/api/test-smtp", methods=["POST"])
    def api_test_smtp():
        from email_sender import test_smtp_connection
        success, err = test_smtp_connection()
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": err})
