import logging

from flask import jsonify, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

import config as cfg
from app.utils import login_required

logger = logging.getLogger(__name__)


def _get_about_html() -> str:
    return (
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


def register_settings_routes(app):
    if "settings" in app.view_functions:
        return

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        if request.method == "POST":
            if "hr_username" in request.form:
                # ── Security / Login ──
                cfg.LOGIN_ENABLED = request.form.get("login_enabled") == "on"
                cfg.HR_USERNAME    = request.form.get("hr_username", cfg.HR_USERNAME).strip()
                new_pw = request.form.get("hr_password", "").strip()
                if new_pw:
                    cfg.HR_PASSWORD = ""
                    cfg.HR_PASSWORD_HASH = generate_password_hash(new_pw)
                # ── Theme & Palette ──
                cfg.THEME = request.form.get("theme", getattr(cfg, "THEME", "light"))
                cfg.COLOR_PALETTE = request.form.get("color_palette", getattr(cfg, "COLOR_PALETTE", "lavender"))
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
                except Exception as e:
                    logger.warning('Caught exception: %s', e, exc_info=True)
                if "email_template_subject" in request.form:
                    cfg.EMAIL_TEMPLATE_SUBJECT = request.form.get("email_template_subject", getattr(cfg, "EMAIL_TEMPLATE_SUBJECT", "")).strip()
                    cfg.EMAIL_TEMPLATE_BODY = request.form.get("email_template_body", getattr(cfg, "EMAIL_TEMPLATE_BODY", "")).strip()

            import main
            main._save_config(cfg)
            return redirect(url_for("settings"))

        return render_template("settings.html", cfg=cfg, about_html=_get_about_html())

    @app.route("/about")
    def about_page():
        return render_template("about.html", about_html=_get_about_html())

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

    @app.route("/api/test-smtp", methods=["POST"])
    @login_required
    def api_test_smtp():
        from src.email_sender import test_smtp_connection
        success, message = test_smtp_connection()
        if success:
            return jsonify({"success": True, "message": "SMTP connection test succeeded!"})
        return jsonify({"success": False, "error": message}), 400

