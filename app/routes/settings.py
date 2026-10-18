import json
import logging

from flask import jsonify, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

import config as cfg
from app.utils import login_required

logger = logging.getLogger(__name__)


def _get_about_html() -> str:
    return (
        "<div style='display:flex; align-items:center; gap:20px; margin-bottom:24px; padding:20px; background:var(--md-sys-color-surface-container-low); border:1px solid var(--md-sys-color-outline-variant); border-radius:var(--radius-lg); max-width:900px;'>"
        "<img src='/static/icon/ai.png' alt='AI Logo' style='width:64px; height:64px; border-radius:16px; object-fit:contain; box-shadow:0 4px 12px rgba(0,0,0,0.05);'>"
        "<div>"
        "<h2 style='margin:0 0 4px 0; border:none; padding:0; font-size:24px; font-weight:800; color:var(--md-sys-color-on-surface);'>AI Recruitment System</h2>"
        "<p style='margin:0; font-size:13px; color:var(--md-sys-color-primary); font-weight:600;'>Version 2.0 — Open Architecture Intelligence Project</p>"
        "</div>"
        "</div>"
        "<p>This platform is an advanced AI research and development project focused on transforming traditional recruitment workflows. It leverages state-of-the-art machine learning models and fluid, data-dense user interfaces to explore how automation can streamline candidate evaluation, from initial resume parsing to final technical interviews.</p>"
        "<h3>Core Architecture &amp; Features</h3>"
        "<ol>"
        "<li><strong>Intelligent Data Import:</strong> Advanced extraction pipeline utilizing pypdf for digital documents and Tesseract OCR for image-based or scanned resumes, ensuring high-fidelity data capture.</li>"
        "<li><strong>AI Skills Analysis:</strong> Employs sophisticated Natural Language Processing (NLP) models to parse unstructured text, accurately identifying key technical skills, educational background, and domain expertise.</li>"
        "<li><strong>Algorithmic Fit Scoring:</strong> A dynamic scoring engine that matches extracted candidate profiles against highly configurable role templates, delivering objective and explainable match scores.</li>"
        "<li><strong>Automated Coordination:</strong> Integrated calendar management system capable of auto-generating iCalendar (.ics) invitations and streamlining interview scheduling without manual overhead.</li>"
        "<li><strong>Interactive Evaluation Mode:</strong> An experimental proctored technical evaluation environment featuring multimodal input capabilities, including real-time speech-to-text integration.</li>"
        "<li><strong>Security &amp; Integrity:</strong> Experimental integration of MediaPipe face detection and browser event monitoring to explore automated proctoring solutions.</li>"
        "<li><strong>Real-time System Telemetry:</strong> A live console streaming event logs and model inference metrics, built for complete transparency during background job execution.</li>"
        "<li><strong>Comprehensive Reporting:</strong> Aggregates pipeline data into human-readable executive summaries and detailed candidate evaluation cards for deep dive analysis.</li>"
        "</ol>"
        "<h3>Technology Stack</h3>"
        "<p>Built entirely on a lightweight, privacy-focused local architecture:</p>"
        "<ul>"
        "<li><strong>Backend Engine:</strong> Python 3.12, Flask 3.0, and SQLite in WAL mode for highly concurrent, reliable data operations.</li>"
        "<li><strong>Frontend UI:</strong> Custom-built Glassmorphic design system wrapped in PyWebView for a seamless desktop application experience.</li>"
        "<li><strong>Local AI Inference:</strong> Designed to run zero-egress local Large Language Models via Ollama, ensuring candidate data never leaves the host machine during parsing.</li>"
        "<li><strong>System Security:</strong> Implements rate-limiting, session management, and robust PBKDF2 credential hashing.</li>"
        "</ul>"
        "<h3>Algorithmic Fairness Goals</h3>"
        "<p>As a research project, a primary objective is exploring objective evaluation methodologies:</p>"
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

                # ── Interview Configuration ──
                if "interview_tech_questions" in request.form:
                    try:
                        cfg.INTERVIEW_TECH_QUESTIONS = max(1, min(10, int(request.form.get("interview_tech_questions", 3))))
                    except (ValueError, TypeError):
                        pass
                if "interview_beh_questions" in request.form:
                    try:
                        cfg.INTERVIEW_BEH_QUESTIONS = max(1, min(5, int(request.form.get("interview_beh_questions", 2))))
                    except (ValueError, TypeError):
                        pass
                if "interview_time_limit" in request.form:
                    try:
                        cfg.INTERVIEW_TIME_LIMIT_SECONDS = max(30, min(600, int(request.form.get("interview_time_limit", 120))))
                    except (ValueError, TypeError):
                        pass

            # ── Ollama / AI Mode ──
            if "ollama_model" in request.form or "privacy_model" in request.form or "ollama_base_url" in request.form:
                new_model = (request.form.get("privacy_model") or request.form.get("ollama_model") or "").strip()
                if new_model:
                    cfg.PRIVACY_MODEL = new_model
                    cfg.OLLAMA_MODEL = new_model
                if "ollama_base_url" in request.form:
                    cfg.OLLAMA_BASE_URL = request.form.get("ollama_base_url", cfg.OLLAMA_BASE_URL).strip()
                if "ollama_fallback_model" in request.form:
                    cfg.OLLAMA_FALLBACK_MODEL = request.form.get("ollama_fallback_model", "").strip()
                if "ollama_num_ctx" in request.form:
                    try:
                        cfg.OLLAMA_NUM_CTX = int(request.form.get("ollama_num_ctx"))
                    except (ValueError, TypeError):
                        pass
                if "ollama_num_predict" in request.form:
                    try:
                        cfg.OLLAMA_NUM_PREDICT = int(request.form.get("ollama_num_predict"))
                    except (ValueError, TypeError):
                        pass
                if "ollama_temperature" in request.form:
                    try:
                        cfg.OLLAMA_TEMPERATURE = float(request.form.get("ollama_temperature"))
                    except (ValueError, TypeError):
                        pass
                if "ai_retry_attempts" in request.form:
                    try:
                        cfg.AI_RETRY_ATTEMPTS = int(request.form.get("ai_retry_attempts"))
                    except (ValueError, TypeError):
                        pass
                if "ai_retry_backoff" in request.form:
                    try:
                        cfg.AI_RETRY_BACKOFF = int(request.form.get("ai_retry_backoff"))
                    except (ValueError, TypeError):
                        pass
                if "ollama_workers" in request.form:
                    try:
                        cfg.OLLAMA_WORKERS = max(1, min(10, int(request.form.get("ollama_workers"))))
                    except (ValueError, TypeError):
                        pass

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

                if "privacy_model" in request.form:
                    cfg.PRIVACY_MODEL = request.form.get("privacy_model", cfg.PRIVACY_MODEL).strip()
                    cfg.OLLAMA_MODEL = cfg.PRIVACY_MODEL
                cfg.ANTHROPIC_MODEL = request.form.get("anthropic_model", "claude-3-5-haiku-latest").strip()
                cfg.GEMINI_MODEL    = request.form.get("gemini_model", "gemini-1.5-flash").strip()
                cfg.GROQ_MODEL      = request.form.get("groq_model", "llama3-8b-8192").strip()
                cfg.OPENAI_MODEL    = request.form.get("openai_model", "gpt-4o-mini").strip()
                cfg.NVIDIA_MODEL    = request.form.get("nvidia_model", "meta/llama-3.1-nemotron-70b-instruct").strip()
                cfg.OPENROUTER_MODEL = request.form.get("openrouter_model", "meta-llama/llama-3.1-8b-instruct:free").strip()
                cfg.GITHUB_MODEL    = request.form.get("github_model", "gpt-4o-mini").strip()
                cfg.OLLAMA_CLOUD_MODEL = request.form.get("ollama_cloud_model", cfg.OLLAMA_CLOUD_MODEL).strip()

                cfg.ANTHROPIC_ENABLED = request.form.get("anthropic_enabled") == "on"
                cfg.GEMINI_ENABLED    = request.form.get("gemini_enabled") == "on"
                cfg.GROQ_ENABLED      = request.form.get("groq_enabled") == "on"
                cfg.OPENAI_ENABLED    = request.form.get("openai_enabled") == "on"
                cfg.NVIDIA_ENABLED    = request.form.get("nvidia_enabled") == "on"
                cfg.OPENROUTER_ENABLED = request.form.get("openrouter_enabled") == "on"
                cfg.GITHUB_ENABLED    = request.form.get("github_enabled") == "on"
                cfg.OLLAMA_CLOUD_ENABLED = request.form.get("ollama_cloud_enabled") == "on"

                if "cloud_workers" in request.form:
                    try:
                        cfg.CLOUD_WORKERS = max(1, min(20, int(request.form.get("cloud_workers"))))
                    except (ValueError, TypeError):
                        pass

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

            # ── Role Scoring & Knockout Rules ──
            if "save_scoring" in request.form or "scoring_preset" in request.form:
                cfg.SCORING_PRESET = request.form.get("scoring_preset", "default").strip()
                try:
                    w_dict = {
                        "skills_match": int(request.form.get("weight_skills", 35)),
                        "experience_years": int(request.form.get("weight_exp", 20)),
                        "domain_match": int(request.form.get("weight_domain", 20)),
                        "education": int(request.form.get("weight_edu", 15)),
                        "certifications": int(request.form.get("weight_certs", 10)),
                    }
                except (ValueError, TypeError):
                    w_dict = {"skills_match": 35, "experience_years": 20, "domain_match": 20, "education": 15, "certifications": 10}
                cfg.SCORING_WEIGHTS = json.dumps(w_dict)

                ko_exp_raw = request.form.get("ko_min_exp", "0").strip()
                try:
                    ko_exp = float(ko_exp_raw) if ko_exp_raw else 0.0
                except (ValueError, TypeError):
                    ko_exp = 0.0
                ko_skills_raw = request.form.get("ko_skills", "")
                ko_skills = [s.strip() for s in ko_skills_raw.split(",") if s.strip()]
                ko_certs_raw = request.form.get("ko_certs", "")
                ko_certs = [c.strip() for c in ko_certs_raw.split(",") if c.strip()]
                cfg.KNOCKOUT_RULES = json.dumps({
                    "min_experience_years": ko_exp,
                    "required_skills": ko_skills,
                    "required_certifications": ko_certs,
                })

            import main
            main._save_config(cfg)
            redirect_target = url_for("settings")
            if "save_scoring" in request.form or "scoring_preset" in request.form:
                redirect_target += "?tab=scoring"
            return redirect(redirect_target)

        try:
            parsed_weights = json.loads(getattr(cfg, "SCORING_WEIGHTS", "{}"))
        except Exception:
            parsed_weights = {"skills_match": 35, "experience_years": 20, "domain_match": 20, "education": 15, "certifications": 10}
        try:
            parsed_knockouts = json.loads(getattr(cfg, "KNOCKOUT_RULES", "{}"))
        except Exception:
            parsed_knockouts = {"min_experience_years": 0, "required_skills": [], "required_certifications": []}

        return render_template(
            "settings.html",
            cfg=cfg,
            about_html=_get_about_html(),
            scoring_weights=parsed_weights,
            knockout_rules=parsed_knockouts,
        )

    @app.route("/api/settings/scoring", methods=["POST"])
    @login_required
    def api_save_scoring_settings():
        data = request.json or {}
        preset = data.get("preset", "default")
        weights = data.get("weights")
        knockout_rules = data.get("knockout_rules")

        cfg.SCORING_PRESET = str(preset)
        if weights is not None:
            cfg.SCORING_WEIGHTS = json.dumps(weights) if isinstance(weights, dict) else str(weights)
        if knockout_rules is not None:
            cfg.KNOCKOUT_RULES = json.dumps(knockout_rules) if isinstance(knockout_rules, dict) else str(knockout_rules)

        import main
        main._save_config(cfg)
        return jsonify({
            "success": True,
            "preset": cfg.SCORING_PRESET,
            "weights": cfg.SCORING_WEIGHTS,
            "knockout_rules": cfg.KNOCKOUT_RULES,
        })

    @app.route("/api/settings/interview", methods=["POST"])
    @login_required
    def api_update_interview_settings():
        data = request.get_json(silent=True) or request.form.to_dict()
        tech = data.get("tech_questions", data.get("interview_tech_questions"))
        beh = data.get("beh_questions", data.get("interview_beh_questions"))
        limit = data.get("time_limit", data.get("interview_time_limit"))
        if tech is not None:
            try:
                cfg.INTERVIEW_TECH_QUESTIONS = max(1, min(10, int(tech)))
            except (ValueError, TypeError):
                pass
        if beh is not None:
            try:
                cfg.INTERVIEW_BEH_QUESTIONS = max(1, min(5, int(beh)))
            except (ValueError, TypeError):
                pass
        if limit is not None:
            try:
                cfg.INTERVIEW_TIME_LIMIT_SECONDS = max(30, min(600, int(limit)))
            except (ValueError, TypeError):
                pass
        import main
        main._save_config(cfg)
        return jsonify({
            "success": True,
            "interview_tech_questions": cfg.INTERVIEW_TECH_QUESTIONS,
            "interview_beh_questions": cfg.INTERVIEW_BEH_QUESTIONS,
            "interview_time_limit": cfg.INTERVIEW_TIME_LIMIT_SECONDS,
        })

    @app.route("/about")
    @login_required
    def about_page():
        return render_template("about.html", about_html=_get_about_html())

    @app.route("/api/toggle-theme", methods=["POST"])
    @login_required
    def api_toggle_theme():
        cfg.THEME = "dark" if cfg.THEME == "light" else "light"
        import main
        main._save_config(cfg)
        return jsonify({"success": True, "theme": cfg.THEME})

    @app.route("/api/change-theme", methods=["POST"])
    @login_required
    def api_change_theme():
        data = request.json or {}
        theme = data.get("theme", "light")
        cfg.THEME = theme
        import main
        main._save_config(cfg)
        return jsonify({"success": True, "theme": cfg.THEME})

    @app.route("/api/change-palette", methods=["POST"])
    @login_required
    def api_change_palette():
        data = request.json or {}
        palette = data.get("palette", "lavender")
        cfg.COLOR_PALETTE = palette
        import main
        main._save_config(cfg)
        return jsonify({"success": True, "palette": cfg.COLOR_PALETTE})

    @app.route("/api/toggle-ai-mode", methods=["POST"])
    @login_required
    def api_toggle_ai_mode():
        current = getattr(cfg, "APP_MODE", "privacy")
        cfg.APP_MODE = "cloud" if current == "privacy" else "privacy"
        import main
        main._save_config(cfg)
        return jsonify({"success": True, "mode": cfg.APP_MODE})

    @app.route("/api/ollama/models", methods=["GET"])
    @login_required
    def api_ollama_models():
        try:
            from src.common import _ollama
            client = _ollama()
            resp = client.list()
            models = []
            raw_models = getattr(resp, "models", None)
            if raw_models is None and isinstance(resp, dict):
                raw_models = resp.get("models", [])
            for m in (raw_models or []):
                name = getattr(m, "model", None) or getattr(m, "name", None)
                if not name and isinstance(m, dict):
                    name = m.get("model") or m.get("name")
                if name and name not in models:
                    models.append(name)
            return jsonify({"models": models})
        except Exception as e:
            return jsonify({"error": str(e), "models": []})

    @app.route("/api/provider-models", methods=["POST"])
    @login_required
    def api_provider_models():
        data = request.json or {}
        provider = data.get("provider", "")
        key = data.get("key", "").strip()

        if not key and provider != "ollama_cloud":
            return jsonify({"success": False, "error": "API Key is required to fetch models."})

        import json
        import urllib.request

        models = []
        try:
            if provider == "openai":
                req = urllib.request.Request("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
                with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
                    resp_data = json.loads(resp.read().decode())
                    models = [m["id"] for m in resp_data.get("data", []) if "gpt" in m["id"] or "o1" in m["id"]]
            elif provider == "groq":
                req = urllib.request.Request("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"})
                with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
                    resp_data = json.loads(resp.read().decode())
                    models = [m["id"] for m in resp_data.get("data", [])]
            elif provider == "gemini":
                req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
                with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
                    resp_data = json.loads(resp.read().decode())
                    models = [m["name"].replace("models/", "") for m in resp_data.get("models", []) if "gemini" in m["name"]]
            elif provider == "anthropic":
                # Anthropic's model API is limited, returning standard hardcoded ones + test key validation
                req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    data=json.dumps({"model":"claude-3-haiku-20240307","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}).encode())
                try:
                    urllib.request.urlopen(req, timeout=5)  # nosec B310
                    models = ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"]
                except urllib.error.HTTPError as e:
                    if e.code == 401:
                        raise Exception("Invalid API Key")
                    models = ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"]
            elif provider == "openrouter":
                req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {key}"})
                with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                    resp_data = json.loads(resp.read().decode())
                    models = [m["id"] for m in resp_data.get("data", [])]
            elif provider == "nvidia":
                req = urllib.request.Request("https://integrate.api.nvidia.com/v1/models", headers={"Authorization": f"Bearer {key}"})
                with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
                    resp_data = json.loads(resp.read().decode())
                    models = [m["id"] for m in resp_data.get("data", [])]
            elif provider == "github":
                # Fallback to standard github models
                models = ["gpt-4o", "gpt-4o-mini", "meta-llama-3-70b-instruct", "meta-llama-3-8b-instruct"]
            elif provider == "ollama_cloud":
                base = (key or "").strip()
                if not base:
                    return jsonify({"success": False, "error": "Ollama Cloud URL is required."}), 400
                from urllib.parse import urlparse
                parsed = urlparse(base)
                if parsed.scheme != "https":
                    return jsonify({"success": False, "error": "Ollama Cloud URL must use HTTPS."}), 400
                url = f"{base.rstrip('/')}/api/tags"
                req = urllib.request.Request(url)
                try:
                    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                        resp_data = json.loads(resp.read().decode())
                        models = [m["name"] for m in resp_data.get("models", [])]
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
                    return jsonify({"success": False, "error": f"Failed to connect to Ollama Cloud: {e}"}), 400
        except urllib.error.HTTPError as e:
            return jsonify({"success": False, "error": f"API Key rejected or error (HTTP {e.code})"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

        if not models:
            models = ["gpt-4o", "claude-3-5-sonnet-latest", "gemini-1.5-flash", "llama3-8b-8192"]

        return jsonify({"success": True, "models": models, "count": len(models)})

    @app.route("/api/test-smtp", methods=["POST"])
    @login_required
    def api_test_smtp():
        from src.email_sender import test_smtp_connection
        success, message = test_smtp_connection()
        if success:
            return jsonify({"success": True, "message": "SMTP connection test succeeded!"})
        return jsonify({"success": False, "error": message}), 400

