import inspect as pyinspect  # used to provide source-code introspection in dev mode
import threading              # start Flask in a background thread alongside pywebview
import webview                # pywebview — renders a native desktop window over the Flask app
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, session
from pathlib import Path  # cross-platform file path handling
import json
import sys
import os
import logging
import shutil
from queue import Queue  # FIFO queue for the real-time log stream

# Add project root to path so pipeline scripts can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app_paths import APP_DATA_DIR, data_path, install_path, resource_path

if str(APP_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DATA_DIR))

import config
from config import HR_USERNAME, HR_PASSWORD, FLASK_SECRET_KEY
from pdf_to_txt import process_file as pdf_process_file
from nlp_extractor import process_file as nlp_process_file
from ranking_engine import load_candidates, call_ai, build_jd_prompt, build_scoring_prompt, score_candidate, save_leaderboard_txt, save_scores_json, WEIGHTS
from scheduling import load_top_candidates, assign_slots_to_candidates, generate_ics, save_schedule_summary, SLOTS_TO_OFFER
from interview_bot import load_scheduled_candidates, load_candidate_nlp, generate_questions, evaluate_answer, proctor_check, save_interview_result
from report_generator import load_interview_transcripts, generate_ai_report, calculate_combined_score, save_report_txt, save_report_json, save_final_summary

# ── New modules ──
from voice_interview import (
    create_voice_session, speak_question, listen_answer, end_voice_session,
    check_microphone, check_tts, speak
)
from webcam_proctor import (
    start_proctoring, get_frame, get_proctor_status, stop_proctoring,
    check_webcam_available
)
from google_calendar import (
    get_free_slots, create_bulk_interview_events, check_calendar_auth,
    trigger_auth_flow, create_interview_event
)
from database import (
    init_db, save_schedule as db_save_schedule,
    get_confirmed_not_emailed, mark_email_sent, log_email,
    update_schedule_slot as db_update_slot, upsert_candidate,
    create_run, finish_run,
    create_interview_token, get_interview_token, mark_token_used,
    get_all_tokens, delete_all_tokens
)
from email_sender import send_interview_email

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import re
import time
import uuid
import socket
import ssl
import ipaddress

# ─────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY  # required for session-based login

init_db()  # create SQLite tables on startup

# Make config available in all templates (for theme class, etc.)
@app.context_processor
def inject_config():
    return {"config": config}

# ---------------------------------------------------------------------------
# Real-time log streaming infrastructure
# ---------------------------------------------------------------------------
# A QueueHandler sits on the root Python logger.  Every log.info() / warning()
# call anywhere in the codebase automatically ends up in this queue.
# The /stream-logs route drains the queue as a Server-Sent Events (SSE) stream
# so the browser's Logs page shows backend activity in real time.
# ---------------------------------------------------------------------------
log_queue = Queue()  # thread-safe FIFO buffer between logger and HTTP response

class QueueHandler(logging.Handler):
    """Custom logging.Handler that pushes formatted log records into log_queue.

    This is the bridge between Python's logging framework and the SSE stream
    at /stream-logs.  All existing log calls in every module are captured
    automatically with no changes needed in those modules.
    """
    def emit(self, record):
        try:
            msg = self.format(record)
            log_queue.put(msg)  # non-blocking; Queue is unbounded
        except Exception:
            pass  # never let a logging error crash the application

root_logger = logging.getLogger()  # attach to the root logger (captures everything)
root_logger.setLevel(logging.INFO)
queue_handler = QueueHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')  # human-readable timestamps
queue_handler.setFormatter(formatter)
root_logger.addHandler(queue_handler)


BASE_DIR       = APP_DATA_DIR           # writable per-user app data directory
RESUMES_FOLDER = data_path("resumes")  # where uploaded PDF/PNG/JPG files are stored
OUTPUT_FOLDER  = data_path("output")   # root of all pipeline output sub-folders

# Override Flask's default template/static resolution to work in frozen .exe
app.template_folder = str(resource_path("templates"))
app.static_folder   = str(resource_path("static"))


# Create any missing output sub-folders on startup
# (mkdir with exist_ok=True is idempotent — safe to call every run)
RESUMES_FOLDER.mkdir(exist_ok=True)
(OUTPUT_FOLDER / "txt").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "nlp").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "ranking").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "scheduling").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "interviews").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "reports").mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# SESSION PERSISTENCE
# ─────────────────────────────────────────────
# Interview sessions are stored in an in-memory dict (interview_session) for
# fast access during a live interview, but also written to disk after every
# answer so that nothing is lost if the app crashes or is restarted.
# The session state is a dict keyed by session_id (str) with the full
# interview transcript, questions, responses, and proctor log.

# Session state is persisted to disk so sessions survive app restarts
SESSION_FILE = OUTPUT_FOLDER / "session_state.json"

def _load_sessions() -> dict:
    """Load interview sessions from disk.

    Called once at startup.  If session_state.json exists and is valid JSON
    it is parsed and returned.  Corrupt or missing files return an empty dict.
    """
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}  # corrupted JSON — start fresh rather than crashing
    return {}

def _save_sessions():
    """Persist the current interview_session dict to disk.

    Called after every answer submission and at session end, so a crash
    only loses at most the current in-flight answer — all previous answers
    are already on disk.
    """
    try:
        SESSION_FILE.write_text(
            json.dumps(interview_session, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        logging.warning(f"[SESSION] Could not persist sessions: {e}")

interview_session = _load_sessions()

# ─────────────────────────────────────────────
# PERSIST CONFIG TO DISK
# ─────────────────────────────────────────────
CONFIG_PATH = data_path("config.py")

def _save_config(cfg):
    """Write current config module values back to config.py so they survive restarts."""
    try:
        lines = [
            '"""',
            "config.py — Central Configuration for AI Recruitment System",
            "=============================================================",
            "All project-wide settings live here so you only need to change",
            "one file when tuning the AI model or retry behaviour.",
            "",
            "How to use:",
            "  from config import OLLAMA_MODEL, AI_RETRY_ATTEMPTS, AI_RETRY_BACKOFF",
            '"""',
            "",
            "# ─────────────────────────────────────────────",
            "# HR LOGIN / SECURITY",
            "# ─────────────────────────────────────────────",
            "",
            f"LOGIN_ENABLED = {cfg.LOGIN_ENABLED}",
            f"HR_USERNAME = {cfg.HR_USERNAME!r}",
            f"HR_PASSWORD = {cfg.HR_PASSWORD!r}",
            f"FLASK_SECRET_KEY = {cfg.FLASK_SECRET_KEY!r}",
            "",
            "# ─────────────────────────────────────────────",
            "# HR PROFILE (shown on Settings page)",
            "# ─────────────────────────────────────────────",
            f"HR_DISPLAY_NAME = {cfg.HR_DISPLAY_NAME!r}",
            f"HR_EMAIL        = {cfg.HR_EMAIL!r}",
            f"HR_COMPANY      = {cfg.HR_COMPANY!r}",
            "",
            "# ─────────────────────────────────────────────",
            '# UI THEME  ("light" or "dark")',
            "# ─────────────────────────────────────────────",
            f"THEME = {cfg.THEME!r}",
            "",
            "# ─────────────────────────────────────────────",
            "# OLLAMA SETTINGS",
            "# ─────────────────────────────────────────────",
            f"OLLAMA_MODEL    = {cfg.OLLAMA_MODEL!r}",
            f"OLLAMA_BASE_URL = {cfg.OLLAMA_BASE_URL!r}",
            "",
            "# ─────────────────────────────────────────────",
            "# EMAIL / SMTP SETTINGS (Gmail App Password)",
            "# ─────────────────────────────────────────────",
            f"SMTP_HOST     = {cfg.SMTP_HOST!r}",
            f"SMTP_PORT     = {cfg.SMTP_PORT}",
            f"SMTP_EMAIL    = {cfg.SMTP_EMAIL!r}",
            f"SMTP_PASSWORD = {cfg.SMTP_PASSWORD!r}",
            "",
            "# ─────────────────────────────────────────────",
            "# RETRY / BACKOFF SETTINGS",
            "# ─────────────────────────────────────────────",
            f"AI_RETRY_ATTEMPTS  = {cfg.AI_RETRY_ATTEMPTS}",
            f"AI_RETRY_BACKOFF   = {cfg.AI_RETRY_BACKOFF}",
            "",
        ]
        CONFIG_PATH.write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        logging.warning(f"[CONFIG] Could not persist settings: {e}")


if not CONFIG_PATH.exists():
    bundled_config = install_path("config.py")
    if bundled_config.exists() and bundled_config.resolve() != CONFIG_PATH.resolve():
        try:
            shutil.copy2(bundled_config, CONFIG_PATH)
        except Exception:
            _save_config(config)
    else:
        _save_config(config)

# ─────────────────────────────────────────────
# PIPELINE TASK TRACKING
# ─────────────────────────────────────────────
# Tracks running pipeline tasks so pages can restore status after navigation.
# Keys: task name (e.g. "pdf", "nlp", "ranking", "scheduling", "reports")
# Values: {"status": "running"|"done"|"error", "started": timestamp, "result": {...}}
TASK_STATE_FILE = OUTPUT_FOLDER / "task_state.json"

def _load_tasks():
    if TASK_STATE_FILE.exists():
        try:
            return json.loads(TASK_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_tasks():
    try:
        TASK_STATE_FILE.write_text(
            json.dumps(pipeline_tasks, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception:
        pass

pipeline_tasks = _load_tasks()

# Clear stale "running" tasks from a previous crash / unclean shutdown
for _k in list(pipeline_tasks):
    if isinstance(pipeline_tasks[_k], dict) and pipeline_tasks[_k].get("status") == "running":
        pipeline_tasks[_k]["status"] = "error"
        pipeline_tasks[_k]["error"] = "Interrupted (app restarted)"
_save_tasks()

# ─────────────────────────────────────────────
# AUTH — LOGIN / LOGOUT
# ─────────────────────────────────────────────

from functools import wraps

def login_required(f):
    """Decorator: redirect to /login if login is enabled and user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if config.LOGIN_ENABLED and not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    # If login is disabled, skip straight to dashboard
    if not config.LOGIN_ENABLED:
        session["logged_in"] = True
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == HR_USERNAME and password == HR_PASSWORD:
            session["logged_in"] = True
            session["username"]  = username
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid credentials. Please try again."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─────────────────────────────────────────────
# ROUTES — PAGES
# ─────────────────────────────────────────────
# These routes serve the HTML pages that make up the 7-step recruitment
# pipeline sidebar.  Each page route typically:
#   1. Reads pipeline output folder(s) to count what has been processed.
#   2. Loads the latest result file (ranking/schedule/etc.) for display.
#   3. Renders the corresponding Jinja2 template with the data.
# ─────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    # Collect counts for every pipeline stage to show on the dashboard
    pdf_count       = len([f for f in RESUMES_FOLDER.iterdir()
                           if f.is_file() and f.suffix.lower() in [".pdf",".png",".jpg",".jpeg"]])
    txt_count       = len(list((OUTPUT_FOLDER / "txt").glob("*.txt")))
    nlp_count       = len(list((OUTPUT_FOLDER / "nlp").glob("*_nlp.json")))
    has_ranking     = len(list((OUTPUT_FOLDER / "ranking").glob("ranking_scores*.json"))) > 0
    has_schedule    = len(list((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"))) > 0
    interview_count = len(list((OUTPUT_FOLDER / "interviews").glob("interview_*.json")))
    report_count    = len(list((OUTPUT_FOLDER / "reports").glob("report_*.json")))
    return render_template("dashboard.html",
                           pdf_count=pdf_count, txt_count=txt_count,
                           nlp_count=nlp_count, has_ranking=has_ranking,
                           has_schedule=has_schedule, interview_count=interview_count,
                           report_count=report_count)

@app.route("/upload")
@login_required
def upload():
    # Show how many resumes have been uploaded vs converted to text already
    txt_count = len(list((OUTPUT_FOLDER / "txt").glob("*.txt")))
    pdf_count = len(list(RESUMES_FOLDER.glob("*.pdf"))) + \
                len(list(RESUMES_FOLDER.glob("*.png"))) + \
                len(list(RESUMES_FOLDER.glob("*.jpg")))
    return render_template("upload.html", pdf_count=pdf_count, txt_count=txt_count)

@app.route("/nlp")
@login_required
def nlp():
    # Show txt files waiting to be processed vs JSON files already generated
    txt_count  = len(list((OUTPUT_FOLDER / "txt").glob("*.txt")))
    nlp_count  = len(list((OUTPUT_FOLDER / "nlp").glob("*_nlp.json")))
    return render_template("nlp.html", txt_count=txt_count, nlp_count=nlp_count)

@app.route("/ranking")
@login_required
def ranking():
    nlp_count     = len(list((OUTPUT_FOLDER / "nlp").glob("*_nlp.json")))
    # Load the most recent ranking output (sorted descending by filename timestamp)
    ranking_files = sorted((OUTPUT_FOLDER / "ranking").glob("ranking_scores*.json"), reverse=True)
    latest        = None
    if ranking_files:
        try:
            with open(ranking_files[0]) as f:
                latest = json.load(f)  # pass the full scores dict to the template
        except (IOError, json.JSONDecodeError):
            pass
    return render_template("ranking.html", nlp_count=nlp_count, ranking=latest)

@app.route("/scheduling")
@login_required
def scheduling():
    ranking_files  = sorted((OUTPUT_FOLDER / "ranking").glob("ranking_scores*.json"), reverse=True)
    schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
    latest_schedule = None
    if schedule_files:
        try:
            with open(schedule_files[0]) as f:
                latest_schedule = json.load(f)  # show existing schedule in the UI
        except (IOError, json.JSONDecodeError):
            pass
    has_ranking    = len(ranking_files) > 0  # guards the "Schedule" button in the UI
    cal_status     = check_calendar_auth()   # tell the page whether Google Calendar is connected
    return render_template("scheduling.html",
                           has_ranking=has_ranking,
                           schedule=latest_schedule,
                           cal_status=cal_status)

@app.route("/interview")
@login_required
def interview():
    # Build the list of confirmed candidates from the latest schedule
    schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
    confirmed  = []
    job_title  = ""
    if schedule_files:
        try:
            with open(schedule_files[0]) as f:
                data = json.load(f)
            # Only show candidates whose slot has been confirmed (not SKIPPED or PENDING)
            confirmed  = [c for c in data.get("schedule", []) if c["status"] == "CONFIRMED"]
            job_title  = data.get("job_title", "")
        except (IOError, json.JSONDecodeError):
            pass
    # Identify interviews already completed so the UI can disable their button
    done_interviews = [f.stem for f in (OUTPUT_FOLDER / "interviews").glob("interview_*.json")]

    # Check hardware availability so the template can show friendly error messages
    mic_status    = check_microphone()
    tts_status    = check_tts()
    webcam_status = check_webcam_available()

    return render_template("interview.html",
                           candidates=confirmed,
                           job_title=job_title,
                           done=done_interviews,
                           mic_available=mic_status['available'],
                           tts_available=tts_status['available'],
                           webcam_available=webcam_status['available'])

@app.route("/rules")
@login_required
def rules():
    return render_template("rules.html")

@app.route("/reports")
@login_required
def reports():
    report_files = sorted((OUTPUT_FOLDER / "reports").glob("report_*.json"), reverse=True)
    reports_data = []
    for rf in report_files:
        try:
            with open(rf) as f:
                data = json.load(f)
                data["_filename"] = rf.name  # pass filename for PDF download link
                reports_data.append(data)
        except (IOError, json.JSONDecodeError, KeyError):
            pass
    summary_files = sorted((OUTPUT_FOLDER / "reports").glob("final_summary_*.json"), reverse=True)
    summary = None
    if summary_files:
        try:
            with open(summary_files[0]) as f:
                summary = json.load(f)
        except (IOError, json.JSONDecodeError):
            pass
    return render_template("reports.html", reports=reports_data, summary=summary)

@app.route("/logs")
@login_required
def logs():
    return render_template("logs.html")

@app.route("/stream-logs")
def stream_logs():
    """Server-Sent Events (SSE) endpoint that streams backend log lines to the browser.

    The browser's EventSource API connects to this URL and receives one
    'data: ...' line per log record.  The generator is a potentially infinite
    loop that blocks on log_queue.get() until a record is available.
    """
    def generate():
        while True:
            line = log_queue.get()  # blocks until a log message is available
            yield f"data: {line}\n\n"  # SSE format: 'data: <content>\n\n'
    return Response(generate(), mimetype="text/event-stream")

@app.route("/about")
@login_required
def about():
    content = (
        "<h2>AI Recruitment System</h2>"
        "<p>This desktop application streamlines the hiring workflow by integrating "
        "automated resume processing, NLP extraction, candidate ranking, scheduling, "
        "interview question generation, and reporting—all in one user-friendly interface.</p>"
        "<p>Key features:</p>"
        "<ol>"
        "<li>Drag-and-drop resume upload with PDF/PNG/JPG support</li>"
        "<li>Automated text extraction and NLP analysis</li>"
        "<li>AI-powered candidate ranking and schedule coordination</li>"
        "<li>Built-in interview bot with <strong>Text</strong> and <strong>Voice</strong> modes</li>"
        "<li>Webcam proctoring with real-time face detection</li>"
        "<li>Google Calendar sync — auto-read free slots and create interview events</li>"
        "<li>Live logging console for monitoring backend activity</li>"
        "<li>Exportable reports and calendar invites</li>"
        "</ol>"
        "<h3>Workflow</h3>"
        "<ol>"
        "<li>Upload resumes from multiple formats.</li>"
        "<li>Process files to plain text and extract NLP data.</li>"
        "<li>Provide a job description to rank candidates automatically.</li>"
        "<li>Schedule interviews — import free slots from Google Calendar.</li>"
        "<li>Conduct interviews via Text or Voice mode with webcam proctoring.</li>"
        "<li>Generate comprehensive reports with AI insights and recommendations.</li>"
        "</ol>"
        "<h3>Fairness &amp; Bias Prevention</h3>"
        "<p>This system is designed to ensure a <strong>standardised and unbiased</strong> hiring process:</p>"
        "<ul>"
        "<li>Candidate ranking is scored <em>exclusively</em> on skills, experience, and education — matched against the job description using AI.</li>"
        "<li>Candidate names, gender, age, and demographic identifiers are <strong>never used</strong> as scoring criteria in any pipeline stage.</li>"
        "<li>Every generated report includes a fairness audit line confirming that demographic data was excluded from scoring.</li>"
        "<li>Interview questions are generated from the job description and candidate domain — not from personal details.</li>"
        "</ul>"
        "<p>Designed for HR teams and recruiters looking to accelerate the talent "
        "acquisition process with AI assistance.</p>"
    )
    return render_template("about.html", about_html=content)

# ─────────────────────────────────────────────
# LAN / WiFi — Local IP helper
# ─────────────────────────────────────────────
def _get_local_ip():
    """Return the machine's local network IP address (e.g. 192.168.x.x)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ─────────────────────────────────────────────
# Self-signed SSL certificate generation
# ─────────────────────────────────────────────
def _ensure_ssl_cert():
    """Generate a self-signed SSL cert/key pair if they don't already exist.

    Returns (cert_path, key_path) for use with Flask's ssl_context.
    Uses the cryptography library to create a certificate valid for 1 year
    with SANs for localhost, 127.0.0.1, and the LAN IP.
    """
    ssl_dir = data_path("output") / "ssl"
    ssl_dir.mkdir(parents=True, exist_ok=True)
    cert_path = ssl_dir / "cert.pem"
    key_path = ssl_dir / "key.pem"

    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    local_ip = _get_local_ip()
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "ARS Interview Server"),
    ])
    san_list = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    if local_ip != "127.0.0.1":
        san_list.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    return str(cert_path), str(key_path)

# ─────────────────────────────────────────────
# CANDIDATE-FACING INTERVIEW (no login required)
# ─────────────────────────────────────────────
# These routes are accessible over LAN so candidates can open
# their unique link on a phone or laptop and take the interview.
# ─────────────────────────────────────────────

@app.route("/candidate-interview/<token>")
def candidate_interview(token):
    """Serve the standalone interview page for a candidate with a valid token."""
    token_data = get_interview_token(token)
    if not token_data:
        return render_template("candidate_interview.html", error="Invalid interview link."), 404
    if token_data["used"]:
        return render_template("candidate_interview.html", error="This interview link has already been used."), 403
    return render_template(
        "candidate_interview.html",
        error=None,
        token=token,
        candidate_name=token_data["candidate_name"],
        source_file=token_data["source_file"],
        job_title=token_data["job_title"],
        rank=token_data["rank"],
        score=token_data["score"],
    )

@app.route("/api/candidate/interview/start", methods=["POST"])
def api_candidate_interview_start():
    """Start interview from a candidate token link (no login needed)."""
    data = request.json
    token = data.get("token", "")
    token_data = get_interview_token(token)
    if not token_data:
        return jsonify({"error": "Invalid token"}), 404
    if token_data["used"]:
        return jsonify({"error": "This interview link has already been used."}), 403

    source_file = token_data["source_file"]
    job_title = token_data["job_title"]

    nlp_path = OUTPUT_FOLDER / "nlp"
    candidate_data = load_candidate_nlp(source_file, nlp_path)
    questions = generate_questions(candidate_data, job_title)

    session_id = f"{source_file}_{int(time.time())}"
    interview_session[session_id] = {
        "source_file": source_file,
        "job_title": job_title,
        "mode": "text",
        "candidate_data": candidate_data,
        "questions": questions,
        "responses": [],
        "proctor_log": [],
        "webcam_log": [],
        "start_time": time.time(),
        "token": token,
    }

    all_questions = (
        [{**q, "type": "TECHNICAL"} for q in questions.get("technical", [])] +
        [{**q, "type": "BEHAVIORAL"} for q in questions.get("behavioral", [])]
    )

    _save_sessions()
    return jsonify({
        "success": True,
        "session_id": session_id,
        "questions": all_questions,
        "domain": candidate_data.get("domain", "General"),
        "mode": "text"
    })

@app.route("/api/candidate/interview/answer", methods=["POST"])
def api_candidate_interview_answer():
    """Evaluate a single answer from the candidate-facing interview."""
    data = request.json
    session_id = data.get("session_id")
    question = data.get("question")
    answer = data.get("answer")
    q_num = data.get("question_num")
    q_type = data.get("type")
    topic = data.get("topic", "")
    time_taken = data.get("time_taken", 0)

    if session_id not in interview_session:
        return jsonify({"error": "Session not found"}), 404

    sess = interview_session[session_id]
    job_title = sess["job_title"]
    domain = sess["candidate_data"].get("domain", "General")

    evaluation = evaluate_answer(question, answer, job_title, domain)
    proctor = proctor_check(q_num, answer, time_taken)

    sess["responses"].append({
        "question_num": q_num,
        "type": q_type,
        "topic": topic,
        "question": question,
        "answer": answer,
        "time_taken": time_taken,
        "score": evaluation.get("total", 0),
        "evaluation": evaluation,
        "proctor": proctor
    })
    sess["proctor_log"].append(proctor)
    _save_sessions()

    return jsonify({"success": True, "evaluation": evaluation, "proctor": proctor})

@app.route("/api/candidate/interview/finish", methods=["POST"])
def api_candidate_interview_finish():
    """Complete the candidate-facing interview and save results."""
    data = request.json
    session_id = data.get("session_id")

    if session_id not in interview_session:
        return jsonify({"error": "Session not found"}), 404

    sess = interview_session[session_id]
    responses = sess["responses"]
    proctor_log = sess["proctor_log"]
    webcam_log = sess.get("webcam_log", [])

    total_score = sum(r["evaluation"].get("total", 0) for r in responses)
    total_q = len(responses)
    max_score = total_q * 10
    percentage = round((total_score / max_score) * 100, 1) if max_score > 0 else 0
    flagged_count = sum(1 for p in proctor_log if p["flagged"])

    tech_responses = [r for r in responses if r["type"] == "TECHNICAL"]
    beh_responses = [r for r in responses if r["type"] == "BEHAVIORAL"]
    tech_score = sum(r["score"] for r in tech_responses)
    beh_score = sum(r["score"] for r in beh_responses)
    tech_max = len(tech_responses) * 10
    beh_max = len(beh_responses) * 10

    webcam_flags = len(webcam_log)
    total_flags = flagged_count + webcam_flags
    proctor_status = "FLAGGED" if total_flags > 2 else "CLEAN"

    token = sess.get("token", "")
    token_data = get_interview_token(token) if token else None

    result = {
        "candidate_name": token_data["candidate_name"] if token_data else "Unknown",
        "source_file": sess["source_file"],
        "rank": token_data["rank"] if token_data else 0,
        "ranking_score": token_data["score"] if token_data else 0,
        "job_title": sess["job_title"],
        "interview_mode": "text",
        "domain": sess["candidate_data"].get("domain", "General"),
        "interview_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "responses": responses,
        "proctor_log": proctor_log,
        "webcam_log": webcam_log,
        "total_score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        "technical_score": tech_score,
        "technical_max": tech_max,
        "technical_pct": round((tech_score / tech_max * 100), 1) if tech_max > 0 else 0,
        "behavioral_score": beh_score,
        "behavioral_max": beh_max,
        "behavioral_pct": round((beh_score / beh_max * 100), 1) if beh_max > 0 else 0,
        "flagged_count": total_flags,
        "proctoring_status": proctor_status
    }

    output_path = OUTPUT_FOLDER / "interviews"
    output_path.mkdir(exist_ok=True)
    save_interview_result(result, output_path)

    # Mark token as used
    if token:
        mark_token_used(token)

    del interview_session[session_id]
    _save_sessions()

    return jsonify({"success": True, "result": result})

@app.route("/api/candidate/proctor/browser_flag", methods=["POST"])
def api_candidate_browser_flag():
    """Log a browser-based proctor flag from the candidate interview page."""
    data = request.json
    session_id = data.get("session_id")
    flag_type = data.get("type", "UNKNOWN")
    if session_id in interview_session:
        interview_session[session_id].setdefault("webcam_log", []).append({
            "type": flag_type,
            "timestamp": time.time()
        })
        _save_sessions()
    return jsonify({"ok": True})

# Lazy-loaded Haar cascade for remote candidate frame analysis
_haar_cascade = None

def _get_haar_cascade():
    """Load the Haar cascade once and cache it."""
    global _haar_cascade
    if _haar_cascade is None:
        import cv2 as _cv2
        _haar_cascade = _cv2.CascadeClassifier(
            _cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _haar_cascade

@app.route("/api/candidate/proctor/analyze-frame", methods=["POST"])
def api_candidate_analyze_frame():
    """Receive a base64 JPEG frame from the candidate's browser camera,
    run face detection, update proctor state, and return face count + flags."""
    import cv2 as _cv2
    import numpy as _np
    import base64 as _b64

    data = request.json
    session_id = data.get("session_id", "")
    frame_b64 = data.get("frame", "")

    if session_id not in interview_session:
        return jsonify({"error": "Session not found"}), 404
    if not frame_b64:
        return jsonify({"face_count": 0, "flags": [], "flag_count": 0})

    # Strip data-URL prefix if present (e.g. "data:image/jpeg;base64,...")
    if "," in frame_b64:
        frame_b64 = frame_b64.split(",", 1)[1]

    # Decode base64 → numpy → OpenCV BGR image
    try:
        img_bytes = _b64.b64decode(frame_b64)
        arr = _np.frombuffer(img_bytes, dtype=_np.uint8)
        frame = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"face_count": 0, "flags": [], "flag_count": 0})
    except Exception:
        return jsonify({"face_count": 0, "flags": [], "flag_count": 0})

    # Run Haar cascade face detection
    cascade = _get_haar_cascade()
    gray = _cv2.cvtColor(frame, _cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5,
        minSize=(60, 60), flags=_cv2.CASCADE_SCALE_IMAGE
    )
    n_faces = len(faces) if isinstance(faces, _np.ndarray) else 0

    # Update proctor state in the interview session
    sess = interview_session[session_id]
    proctor_state = sess.setdefault("_remote_proctor", {
        "no_face_count": 0,
        "multi_face_count": 0,
    })

    now_str = datetime.now().strftime("%H:%M:%S")
    webcam_log = sess.setdefault("webcam_log", [])

    if n_faces == 0:
        proctor_state["no_face_count"] += 1
        proctor_state["multi_face_count"] = 0
        if proctor_state["no_face_count"] >= 3:  # 3 consecutive checks = flag
            webcam_log.append({
                "type": "NO_FACE_DETECTED",
                "detail": f"Candidate not visible at {now_str}",
                "timestamp": time.time()
            })
            proctor_state["no_face_count"] = 0
    elif n_faces > 1:
        proctor_state["multi_face_count"] += 1
        proctor_state["no_face_count"] = 0
        if proctor_state["multi_face_count"] >= 2:
            webcam_log.append({
                "type": "MULTIPLE_FACES",
                "detail": f"{n_faces} faces detected at {now_str}",
                "timestamp": time.time()
            })
            proctor_state["multi_face_count"] = 0
    else:
        proctor_state["no_face_count"] = 0
        proctor_state["multi_face_count"] = 0

    return jsonify({
        "face_count": n_faces,
        "flags": webcam_log,
        "flag_count": len(webcam_log),
    })

# ─── Ollama model management APIs ───

@app.route("/api/ollama/models")
def api_ollama_models():
    """Return list of locally downloaded Ollama models."""
    try:
        import ollama as _ollama
        models = _ollama.list().get("models", [])
        names = [m["model"] for m in models]
        return jsonify({"models": sorted(names)})
    except Exception as e:
        return jsonify({"error": str(e), "models": []}), 500

@app.route("/api/ollama/pull", methods=["POST"])
def api_ollama_pull():
    """Pull (download) an Ollama model by name."""
    model_name = request.json.get("model", "").strip()
    if not model_name:
        return jsonify({"error": "No model name provided."}), 400
    try:
        import ollama as _ollama
        _ollama.pull(model_name)
        return jsonify({"ok": True, "message": f"Model '{model_name}' pulled successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Email / SMTP APIs ───

@app.route("/api/test-smtp", methods=["POST"])
def api_test_smtp():
    """Test SMTP connection with the currently configured credentials."""
    import smtplib
    import config as cfg
    email = cfg.SMTP_EMAIL
    password = cfg.SMTP_PASSWORD
    host = cfg.SMTP_HOST
    port = cfg.SMTP_PORT
    if not email or not password:
        return jsonify({"error": "SMTP email and password are not configured."}), 400
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(email, password)
        return jsonify({"ok": True, "message": "SMTP connection successful."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/send-emails", methods=["POST"])
def api_send_emails():
    """Send interview invitation emails to all confirmed-but-not-emailed candidates."""
    import config as cfg
    if not cfg.SMTP_EMAIL or not cfg.SMTP_PASSWORD:
        return jsonify({"error": "SMTP email credentials are not configured. Set them in Settings → Email."}), 400

    entries = get_confirmed_not_emailed()
    if not entries:
        return jsonify({"error": "No confirmed candidates pending email."}), 404

    sent = 0
    failed = 0
    errors = []
    email_run_id = create_run("email", {"pending": len(entries)})
    for entry in entries:
        # Look up candidate email from NLP JSON files
        recipient = _lookup_candidate_email(entry["candidate_name"])
        if not recipient:
            failed += 1
            errors.append(f"{entry['candidate_name']}: No email found in resume data.")
            log_email(email_run_id, entry["id"], "", "Interview Invitation", "FAILED", "No email found")
            continue

        ok, err = send_interview_email(
            smtp_host=cfg.SMTP_HOST,
            smtp_port=cfg.SMTP_PORT,
            smtp_email=cfg.SMTP_EMAIL,
            smtp_password=cfg.SMTP_PASSWORD,
            recipient_email=recipient,
            candidate_name=entry["candidate_name"],
            job_title=entry.get("job_title", "Open Position"),
            interview_slot=entry.get("selected_slot", ""),
            hr_name=cfg.HR_DISPLAY_NAME,
            company=cfg.HR_COMPANY,
        )
        if ok:
            mark_email_sent(entry["id"])
            log_email(email_run_id, entry["id"], recipient, "Interview Invitation", "SENT")
            sent += 1
        else:
            failed += 1
            errors.append(f"{entry['candidate_name']}: {err}")
            log_email(email_run_id, entry["id"], recipient, "Interview Invitation", "FAILED", err)

    finish_run(email_run_id, "COMPLETED", {"sent": sent, "failed": failed})
    return jsonify({"success": True, "sent": sent, "failed": failed, "errors": errors})


def _lookup_candidate_email(candidate_name):
    """Try to find a candidate's email from NLP JSON output files."""
    nlp_dir = OUTPUT_FOLDER / "nlp"
    if not nlp_dir.exists():
        return ""
    for f in nlp_dir.glob("*_nlp.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            # NLP JSON nests personal info: {"personal_info": {"name": ..., "email": ...}}
            personal = data.get("personal_info", {})
            name = personal.get("name", "") or data.get("name", "")
            if name and name.lower().strip() == candidate_name.lower().strip():
                return personal.get("email", "") or data.get("email", "")
        except Exception:
            continue
    return ""

@app.route("/api/generate-interview-links", methods=["POST"])
def api_generate_interview_links():
    """Generate unique interview links for all confirmed candidates."""
    schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
    if not schedule_files:
        return jsonify({"error": "No schedule found. Complete scheduling first."}), 404

    try:
        with open(schedule_files[0]) as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError):
        return jsonify({"error": "Could not read schedule file."}), 500

    confirmed = [c for c in data.get("schedule", []) if c["status"] == "CONFIRMED"]
    if not confirmed:
        return jsonify({"error": "No confirmed candidates found."}), 404

    job_title = data.get("job_title", "")
    local_ip = _get_local_ip()
    base_url = f"https://{local_ip}:5000"

    # Clear old tokens and generate fresh ones
    delete_all_tokens()
    links = []
    for c in confirmed:
        token = uuid.uuid4().hex
        create_interview_token(
            token=token,
            candidate_name=c["candidate_name"],
            source_file=c["source_file"],
            job_title=job_title,
            rank=c.get("rank", 0),
            score=c.get("score", 0),
        )
        links.append({
            "candidate_name": c["candidate_name"],
            "token": token,
            "url": f"{base_url}/candidate-interview/{token}",
        })

    return jsonify({"success": True, "links": links, "base_url": base_url})

@app.route("/api/send-interview-links", methods=["POST"])
def api_send_interview_links():
    """Generate interview links and email them to each candidate."""
    import config as cfg
    if not cfg.SMTP_EMAIL or not cfg.SMTP_PASSWORD:
        return jsonify({"error": "SMTP email credentials are not configured. Set them in Settings → Email."}), 400

    # First generate the links
    schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
    if not schedule_files:
        return jsonify({"error": "No schedule found."}), 404

    try:
        with open(schedule_files[0]) as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError):
        return jsonify({"error": "Could not read schedule file."}), 500

    confirmed = [c for c in data.get("schedule", []) if c["status"] == "CONFIRMED"]
    if not confirmed:
        return jsonify({"error": "No confirmed candidates."}), 404

    job_title = data.get("job_title", "")
    local_ip = _get_local_ip()
    base_url = f"https://{local_ip}:5000"

    # Regenerate tokens
    delete_all_tokens()

    sent = 0
    failed = 0
    errors = []
    links = []

    for c in confirmed:
        candidate_name = c["candidate_name"]
        token = uuid.uuid4().hex
        create_interview_token(
            token=token,
            candidate_name=candidate_name,
            source_file=c["source_file"],
            job_title=job_title,
            rank=c.get("rank", 0),
            score=c.get("score", 0),
        )
        interview_url = f"{base_url}/candidate-interview/{token}"
        links.append({"candidate_name": candidate_name, "token": token, "url": interview_url})

        recipient = _lookup_candidate_email(candidate_name)
        if not recipient:
            failed += 1
            errors.append(f"{candidate_name}: No email found in resume data.")
            continue

        ok, err = _send_interview_link_email(
            cfg, recipient, candidate_name, job_title,
            c.get("selected_slot", ""), interview_url
        )
        if ok:
            sent += 1
        else:
            failed += 1
            errors.append(f"{candidate_name}: {err}")

    return jsonify({"success": True, "sent": sent, "failed": failed, "errors": errors, "links": links})

def _send_interview_link_email(cfg, recipient, candidate_name, job_title, slot, interview_url):
    """Send an interview link email to a candidate. Returns (True, '') or (False, error)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    try:
        dt = datetime.strptime(slot, "%Y-%m-%d %H:%M")
        date_display = dt.strftime("%A, %B %d %Y at %I:%M %p")
    except (ValueError, TypeError):
        date_display = slot or "TBD"

    company_line = f" at {cfg.HR_COMPANY}" if cfg.HR_COMPANY else ""
    hr_line = cfg.HR_DISPLAY_NAME or "The Hiring Team"

    subject = f"Interview Link — {job_title}"
    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;">
        <h2 style="color:#18181b;">Your Interview Link</h2>
        <p>Dear <strong>{candidate_name}</strong>,</p>
        <p>You have been shortlisted for <strong>{job_title}</strong>{company_line}.</p>
        <p>Your interview is scheduled for:</p>
        <div style="background:#f4f4f5;padding:16px 20px;border-radius:8px;margin:16px 0;font-size:15px;">
            <strong>{date_display}</strong>
        </div>
        <p>Click the button below to start your interview. Make sure you are connected to the same WiFi network.</p>
        <div style="text-align:center;margin:24px 0;">
            <a href="{interview_url}"
               style="display:inline-block;background:#6366f1;color:#fff;padding:14px 32px;
                      border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">
                Start Interview
            </a>
        </div>
        <p style="font-size:13px;color:#71717a;">
            Or copy this link into your browser:<br>
            <code style="word-break:break-all;">{interview_url}</code>
        </p>
        <p style="margin-top:24px;">Best regards,<br><strong>{hr_line}</strong>{company_line}</p>
        <hr style="border:none;border-top:1px solid #e4e4e7;margin-top:32px;">
        <p style="font-size:12px;color:#a1a1aa;">
            This is an automated message from the AI Recruitment System.
            This link is unique to you and can only be used once.
        </p>
    </div>
    """
    body_text = (
        f"Dear {candidate_name},\n\n"
        f"You have been shortlisted for {job_title}{company_line}.\n\n"
        f"Interview scheduled: {date_display}\n\n"
        f"Start your interview here: {interview_url}\n\n"
        f"This link is unique to you and can only be used once.\n\n"
        f"Best regards,\n{hr_line}{company_line}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.SMTP_EMAIL
    msg["To"] = recipient
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(cfg.SMTP_EMAIL, cfg.SMTP_PASSWORD)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)

@app.route("/api/interview-links", methods=["GET"])
def api_get_interview_links():
    """Return all generated interview tokens/links."""
    tokens = get_all_tokens()
    local_ip = _get_local_ip()
    base_url = f"https://{local_ip}:5000"
    links = []
    for t in tokens:
        links.append({
            "candidate_name": t["candidate_name"],
            "token": t["token"],
            "url": f"{base_url}/candidate-interview/{t['token']}",
            "used": bool(t["used"]),
        })
    return jsonify({"success": True, "links": links, "base_url": base_url})

@app.route("/settings", methods=["GET", "POST"])
def settings():
    import config as cfg
    if request.method == "POST":
        # ── Security / Login ──
        cfg.LOGIN_ENABLED = request.form.get("login_enabled") == "on"
        cfg.HR_USERNAME    = request.form.get("hr_username", cfg.HR_USERNAME).strip()
        new_pw = request.form.get("hr_password", "").strip()
        if new_pw:
            cfg.HR_PASSWORD = new_pw
        # ── Theme ──
        cfg.THEME = request.form.get("theme", "light")
        # ── Profile ──
        cfg.HR_DISPLAY_NAME = request.form.get("display_name", "").strip()
        cfg.HR_EMAIL        = request.form.get("email", "").strip()
        cfg.HR_COMPANY      = request.form.get("company", "").strip()
        # ── Ollama (only update when AI tab form is submitted) ──
        if "ollama_model" in request.form:
            cfg.OLLAMA_MODEL   = request.form.get("ollama_model", cfg.OLLAMA_MODEL).strip()
            cfg.OLLAMA_BASE_URL = request.form.get("ollama_base_url", cfg.OLLAMA_BASE_URL).strip()
        # ── Email / SMTP (only update when Email tab form is submitted) ──
        if "smtp_email" in request.form:
            cfg.SMTP_EMAIL    = request.form.get("smtp_email", cfg.SMTP_EMAIL).strip()
            cfg.SMTP_PASSWORD = request.form.get("smtp_password", cfg.SMTP_PASSWORD).strip()
            cfg.SMTP_HOST     = request.form.get("smtp_host", cfg.SMTP_HOST).strip()
            try:
                cfg.SMTP_PORT = int(request.form.get("smtp_port", cfg.SMTP_PORT))
            except (ValueError, TypeError):
                pass  # keep existing SMTP_PORT if input is invalid
        # ── Persist settings to disk so they survive restarts ──
        _save_config(cfg)
        return redirect(url_for("settings"))
    about_html = (
        "<h2>AI Recruitment System</h2>"
        "<p>This desktop application streamlines the hiring workflow by integrating "
        "automated resume processing, NLP extraction, candidate ranking, scheduling, "
        "interview question generation, and reporting\u2014all in one user-friendly interface.</p>"
        "<p>Key features:</p>"
        "<ol>"
        "<li>Drag-and-drop resume upload with PDF/PNG/JPG support</li>"
        "<li>Automated text extraction and NLP analysis</li>"
        "<li>AI-powered candidate ranking and schedule coordination</li>"
        "<li>Built-in interview bot with <strong>Text</strong> and <strong>Voice</strong> modes</li>"
        "<li>Webcam proctoring with real-time face detection</li>"
        "<li>Google Calendar sync \u2014 auto-read free slots and create interview events</li>"
        "<li>Live logging console for monitoring backend activity</li>"
        "<li>Exportable reports and calendar invites</li>"
        "</ol>"
        "<h3>Workflow</h3>"
        "<ol>"
        "<li>Upload resumes from multiple formats.</li>"
        "<li>Process files to plain text and extract NLP data.</li>"
        "<li>Provide a job description to rank candidates automatically.</li>"
        "<li>Schedule interviews \u2014 import free slots from Google Calendar.</li>"
        "<li>Conduct interviews via Text or Voice mode with webcam proctoring.</li>"
        "<li>Generate comprehensive reports with AI insights and recommendations.</li>"
        "</ol>"
        "<h3>Fairness &amp; Bias Prevention</h3>"
        "<p>This system is designed to ensure a <strong>standardised and unbiased</strong> hiring process:</p>"
        "<ul>"
        "<li>Candidate ranking is scored <em>exclusively</em> on skills, experience, and education \u2014 matched against the job description using AI.</li>"
        "<li>Candidate names, gender, age, and demographic identifiers are <strong>never used</strong> as scoring criteria in any pipeline stage.</li>"
        "<li>Every generated report includes a fairness audit line confirming that demographic data was excluded from scoring.</li>"
        "<li>Interview questions are generated from the job description and candidate domain \u2014 not from personal details.</li>"
        "</ul>"
        "<p>Designed for HR teams and recruiters looking to accelerate the talent "
        "acquisition process with AI assistance.</p>"
    )
    return render_template("settings.html", cfg=cfg, about_html=about_html)

# ─────────────────────────────────────────────
# API — LIVE STATS (used for real-time polling)
# ─────────────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
def api_stats():
    """
    Return live file counts for all pipeline stages.

    The sidebar in each page polls this endpoint every few seconds to update
    the badge numbers (e.g. '5 PDFs uploaded, 3 converted to TXT').
    All counts are derived directly from the filesystem so they are always
    accurate even if files were added outside the app.
    """
    pdf_count  = len([f for f in RESUMES_FOLDER.iterdir()
                      if f.is_file() and f.suffix.lower() in [".pdf", ".png", ".jpg", ".jpeg"]])
    txt_count  = len(list((OUTPUT_FOLDER / "txt").glob("*.txt")))
    nlp_count  = len(list((OUTPUT_FOLDER / "nlp").glob("*_nlp.json")))
    rank_files = sorted((OUTPUT_FOLDER / "ranking").glob("ranking_scores*.json"), reverse=True)
    ranked     = len(rank_files) > 0
    sched_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
    scheduled  = len(sched_files) > 0
    interview_count = len(list((OUTPUT_FOLDER / "interviews").glob("interview_*.json")))
    report_count    = len(list((OUTPUT_FOLDER / "reports").glob("report_*.json")))
    return jsonify({
        "pdf_count":       pdf_count,
        "txt_count":       txt_count,
        "nlp_count":       nlp_count,
        "pending_txt":     pdf_count - txt_count,
        "pending_nlp":     txt_count - nlp_count,
        "has_ranking":     ranked,
        "has_schedule":    scheduled,
        "interview_count": interview_count,
        "report_count":    report_count,
        "tasks":           pipeline_tasks,
    })

@app.route("/api/task-status", methods=["GET"])
def api_task_status():
    """Return the current pipeline task states for all steps."""
    return jsonify(pipeline_tasks)

# ─────────────────────────────────────────────
# API — RESET PIPELINE
# ─────────────────────────────────────────────

import shutil

@app.route("/api/reset-pipeline", methods=["POST"])
def api_reset_pipeline():
    """
    Delete all pipeline output except raw TXT files.

    Clears: nlp/, ranking/, scheduling/, interviews/, reports/
    Keeps:  txt/ (so the user doesn't need to re-upload PDFs)

    Useful for starting a new recruitment cycle without re-processing PDFs.
    """
    deleted = 0
    folders_to_clear = ["nlp", "ranking", "scheduling", "interviews", "reports"]
    for folder_name in folders_to_clear:
        folder = OUTPUT_FOLDER / folder_name
        if folder.exists():
            for f in folder.iterdir():
                if f.is_file():
                    f.unlink()
                    deleted += 1
                elif f.is_dir():
                    shutil.rmtree(f)
                    deleted += 1
    pipeline_tasks.clear()
    _save_tasks()
    return jsonify({"success": True, "deleted": deleted,
                    "message": f"Cleared {deleted} item(s) from pipeline. TXT files kept."})

@app.route("/api/open-output-folder", methods=["POST"])
def api_open_output_folder():
    """Open the output folder in Windows Explorer."""
    try:
        os.startfile(str(OUTPUT_FOLDER))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ─────────────────────────────────────────────
# API — UPLOAD
# ─────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    Accept one or more resume files from the drag-and-drop upload form.

    Expected: multipart/form-data with a field named 'resumes'.
    Files are saved as-is into RESUMES_FOLDER (overwrite allowed).
    Returns: {success, saved: [filename, ...], count}
    """
    files = request.files.getlist("resumes")
    saved = []
    for file in files:
        if file.filename:  # skip the empty slot Flask adds for empty multipart fields
            dest = RESUMES_FOLDER / file.filename
            file.save(dest)  # overwrites if same filename is uploaded again
            saved.append(file.filename)
    return jsonify({"success": True, "saved": saved, "count": len(saved)})


@app.route("/api/process-pdfs", methods=["POST"])
def api_process_pdfs():
    """
    Convert all uploaded PDF/PNG/JPG resumes to plain .txt files.

    For each file in RESUMES_FOLDER, calls pdf_process_file():
      - If a .txt already exists for that file: categorised as 'skipped' (idempotent).
      - If conversion succeeds (new file): categorised as 'success'.
      - On exception: categorised as 'failed' with the error message.
    Returns: {success: [], skipped: [], failed: [{file, error}]}
    """
    input_path  = RESUMES_FOLDER
    output_path = OUTPUT_FOLDER / "txt"
    files = [f for f in input_path.iterdir()
             if f.is_file() and f.suffix.lower() in [".pdf", ".png", ".jpg", ".jpeg"]]
    results = {"success": [], "skipped": [], "failed": []}  # categorised results for the UI
    for f in files:
        try:
            is_new = pdf_process_file(f, output_path)  # returns True if a new .txt was created
            if is_new:
                results["success"].append(f.name)
            else:
                results["skipped"].append(f.name)
        except Exception as e:
            results["failed"].append({"file": f.name, "error": str(e)})
    return jsonify(results)

# ─────────────────────────────────────────────
# API — NLP
# ─────────────────────────────────────────────

@app.route("/api/process-nlp", methods=["POST"])
def api_process_nlp():
    """
    Parse all .txt resume files with the AI NLP extractor.

    For each .txt in output/txt/, calls nlp_process_file() which uses the
    local Ollama LLM to extract structured candidate data into a JSON file.
    Returns: {success: [], skipped: [], failed: [{file, error}]}
    """
    input_path  = OUTPUT_FOLDER / "txt"
    output_path = OUTPUT_FOLDER / "nlp"
    txt_files   = list(input_path.glob("*.txt"))  # all plain-text resumes to process
    results     = {"success": [], "skipped": [], "failed": []}
    run_id = create_run("nlp", {"file_count": len(txt_files)})
    for txt_file in txt_files:
        try:
            is_new = nlp_process_file(txt_file, output_path)
            if is_new:
                results["success"].append(txt_file.name)
                # Save candidate to DB from the newly created NLP JSON
                nlp_json = output_path / (txt_file.stem + "_nlp.json")
                if nlp_json.exists():
                    try:
                        ndata = json.loads(nlp_json.read_text(encoding="utf-8"))
                        pi = ndata.get("personal_info", {})
                        upsert_candidate(
                            run_id=run_id,
                            name=pi.get("name", txt_file.stem),
                            email=pi.get("email", ""),
                            source_file=txt_file.name,
                            skills=ndata.get("skills", {}).get("technical_skills", []),
                        )
                    except Exception:
                        pass
            else:
                results["skipped"].append(txt_file.name)
        except Exception as e:
            results["failed"].append({"file": txt_file.name, "error": str(e)})
    finish_run(run_id, "COMPLETED", results)

    pipeline_tasks["nlp"] = {"status": "done", "result": results}
    _save_tasks()
    return jsonify(results)

# ─────────────────────────────────────────────
# API — RANKING
# ─────────────────────────────────────────────

@app.route("/api/rank", methods=["POST"])
def api_rank():
    """
    Score and rank all candidates against a provided Job Description.

    Request body (JSON):
      jd_text  — the full job description text entered by the HR user

    Flow:
      1. AI parses the JD text into structured field requirements.
      2. All NLP candidate JSON files are loaded.
      3. Each candidate is scored in parallel (ThreadPoolExecutor, 5 workers).
      4. Sorted ranked list is saved as ranking_scores_<timestamp>.json
         and a human-readable leaderboard .txt file.

    Returns: {success, job_title, ranked: [{candidate, scores...}]}
    """
    data    = request.json
    jd_text = data.get("jd_text", "").strip()
    if not jd_text:
        return jsonify({"error": "No JD provided"}), 400

    pipeline_tasks["ranking"] = {"status": "running", "started": time.time()}
    _save_tasks()

    nlp_path    = OUTPUT_FOLDER / "nlp"
    output_path = OUTPUT_FOLDER / "ranking"
    output_path.mkdir(exist_ok=True)

    jd_data = call_ai(build_jd_prompt(jd_text))  # parse the JD into structured requirements
    if not jd_data:
        return jsonify({"error": "Failed to parse JD"}), 500

    candidates = load_candidates(nlp_path)
    if not candidates:
        return jsonify({"error": "No candidates found"}), 404

    scored = []
    # Score all candidates in parallel — each call_ollama is I/O-bound (network to Ollama)
    # so 5 concurrent threads provides a significant speed-up over sequential scoring
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(score_candidate, c, jd_data): c for c in candidates}
        for future in as_completed(futures):
            result = future.result()
            if result:
                scored.append(result)

    # Sort descending by total_score so rank 1 = best candidate
    ranked = sorted(scored, key=lambda x: x.get("total_score", 0), reverse=True)
    save_leaderboard_txt(ranked, jd_data, output_path)
    save_scores_json(ranked, jd_data, output_path)

    # Update candidate scores in DB
    run_id = create_run("ranking", {"job_title": jd_data.get("job_title"), "count": len(ranked)})
    for r in ranked:
        upsert_candidate(
            run_id=run_id,
            name=r.get("candidate", ""),
            score=r.get("total_score", 0),
        )
    finish_run(run_id, "COMPLETED")

    pipeline_tasks["ranking"] = {"status": "done", "result": {"count": len(ranked), "job_title": jd_data.get("job_title")}}
    _save_tasks()

    return jsonify({"success": True, "job_title": jd_data.get("job_title"), "ranked": ranked})

# ─────────────────────────────────────────────
# API — SCHEDULING
# ─────────────────────────────────────────────

@app.route("/api/schedule", methods=["POST"])
def api_schedule():
    """
    Assign interview time slots to the top-ranked candidates.

    Request body (JSON):
      job_title  — used in calendar invite titles
      hr_name    — used in .ics organiser field
      slots      — list of 'YYYY-MM-DD HH:MM' strings for available time slots

    Flow:
      1. Load top candidates from the latest ranking JSON.
      2. Rotate available slots fairly across candidates.
      3. Generate one .ics calendar invite per confirmed candidate.
      4. Save a schedule summary JSON and set status to CONFIRMED.

    Returns: {success, scheduled: [{candidate_name, slot, status, ...}]}
    """
    data      = request.json
    job_title = data.get("job_title", "Open Position")
    hr_name   = data.get("hr_name", "Hiring Manager")
    slots_raw = data.get("slots", [])

    pipeline_tasks["scheduling"] = {"status": "running", "started": time.time()}
    _save_tasks()

    ranking_path = OUTPUT_FOLDER / "ranking"
    output_path  = OUTPUT_FOLDER / "scheduling"
    output_path.mkdir(exist_ok=True)

    top_candidates = load_top_candidates(ranking_path, 10)
    if not top_candidates:
        return jsonify({"error": "No ranked candidates found"}), 404

    try:
        hr_slots = [datetime.strptime(s, "%Y-%m-%d %H:%M") for s in slots_raw]
    except ValueError as e:
        return jsonify({"error": f"Invalid slot format: {e}"}), 400

    session_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scheduled     = assign_slots_to_candidates(top_candidates, hr_slots, SLOTS_TO_OFFER)

    for entry in scheduled:
        if entry["offered_slots"]:
            entry["selected_slot"] = entry["offered_slots"][0]
            entry["status"]        = "CONFIRMED"

    for entry in scheduled:
        generate_ics(entry, output_path, hr_name, job_title, session_stamp)

    save_schedule_summary(scheduled, output_path, job_title)

    # Persist to SQLite
    sched_run_id = create_run("scheduling", {"job_title": job_title, "count": len(scheduled)})
    db_save_schedule(sched_run_id, scheduled, job_title)
    finish_run(sched_run_id, "COMPLETED")

    pipeline_tasks["scheduling"] = {"status": "done"}
    _save_tasks()

    return jsonify({"success": True, "scheduled": scheduled})

@app.route("/api/update-slot", methods=["POST"])
def api_update_slot():
    """
    Update the selected time slot for a specific candidate in the schedule.

    Used when the HR user manually changes a candidate's slot from the UI
    (e.g. if a candidate requested a different time).

    Request body (JSON):
      candidate_name  — must match exactly the name stored in the schedule
      selected_slot   — new 'YYYY-MM-DD HH:MM' string
    Returns: {success: True}
    """
    data           = request.json
    candidate_name = data.get("candidate_name")
    selected_slot  = data.get("selected_slot")

    schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
    if not schedule_files:
        return jsonify({"error": "No schedule found"}), 404

    try:
        with open(schedule_files[0]) as f:
            schedule_data = json.load(f)
    except (IOError, json.JSONDecodeError):
        return jsonify({"error": "Schedule file is corrupted"}), 500

    # Linear search for the candidate and update in-place
    for entry in schedule_data["schedule"]:
        if entry["candidate_name"] == candidate_name:
            entry["selected_slot"] = selected_slot
            entry["status"]        = "CONFIRMED"
            break  # stop after first match (names should be unique)

    with open(schedule_files[0], "w") as f:
        json.dump(schedule_data, f, indent=4)  # persist the updated schedule

    return jsonify({"success": True})

# ─────────────────────────────────────────────
# API — GOOGLE CALENDAR
# ─────────────────────────────────────────────

@app.route("/api/calendar/status", methods=["GET"])
def api_calendar_status():
    """Return whether the user has completed Google Calendar OAuth2 authentication."""
    return jsonify(check_calendar_auth())

@app.route("/api/calendar/auth", methods=["POST"])
def api_calendar_auth():
    """Trigger the browser-based OAuth2 flow to link Google Calendar."""
    result = trigger_auth_flow()
    return jsonify(result)

@app.route("/api/calendar/free-slots", methods=["GET"])
def api_calendar_free_slots():
    """
    Fetch the HR user's free time slots from Google Calendar.

    Query param: days (int, default 14) — how many days ahead to look.
    Returns a list of available slot strings (formatted for the scheduling UI).
    """
    days    = request.args.get("days", 14)
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 14
    result  = get_free_slots(days_ahead=days)
    return jsonify(result)

@app.route("/api/calendar/create-events", methods=["POST"])
def api_calendar_create_events():
    """Create Google Calendar events for all confirmed candidates."""
    data      = request.json
    job_title = data.get("job_title", "Open Position")
    hr_name   = data.get("hr_name", "Hiring Manager")
    hr_email  = data.get("hr_email", "")

    schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
    if not schedule_files:
        return jsonify({"error": "No schedule found"}), 404

    try:
        with open(schedule_files[0]) as f:
            schedule_data = json.load(f)
    except (IOError, json.JSONDecodeError):
        return jsonify({"error": "Schedule file is corrupted"}), 500

    scheduled = schedule_data.get("schedule", [])
    result    = create_bulk_interview_events(scheduled, job_title, hr_name, hr_email)
    return jsonify({"success": True, **result})

# ─────────────────────────────────────────────
# API — INTERVIEW (TEXT MODE)
# ─────────────────────────────────────────────
# The interview flow has three endpoints called in sequence:
#   1. /api/interview/start  — creates a session, returns all questions
#   2. /api/interview/answer — called once per question, stores the evaluated answer
#   3. /api/interview/finish — computes final scores, saves transcript, cleans up session
# ─────────────────────────────────────────────

@app.route("/api/interview/start", methods=["POST"])
def api_interview_start():
    """
    Initialise a new interview session for a specific candidate.

    Request body (JSON):
      source_file  — filename stem matching the candidate's NLP JSON
      job_title    — used to tailor the questions to the role
      mode         — 'text' (default) or 'voice'

    Returns all generated questions plus a unique session_id.
    The session_id must be included in every subsequent /api/interview/* call.
    """
    data         = request.json
    source_file  = data.get("source_file")
    job_title    = data.get("job_title")
    mode         = data.get("mode", "text")  # 'text' or 'voice'

    nlp_path       = OUTPUT_FOLDER / "nlp"
    candidate_data = load_candidate_nlp(source_file, nlp_path)  # structured resume data from NLP step
    questions      = generate_questions(candidate_data, job_title)  # AI-generated technical + behavioral questions

    # Use source_file + timestamp as session_id to avoid collisions in parallel interviews
    session_id = f"{source_file}_{int(time.time())}"
    interview_session[session_id] = {
        "source_file":    source_file,
        "job_title":      job_title,
        "mode":           mode,
        "candidate_data": candidate_data,
        "questions":      questions,
        "responses":      [],    # populated by /api/interview/answer calls
        "proctor_log":    [],    # AI text-based proctor flags per question
        "webcam_log":     [],    # webcam face-detection flags (added on finish)
        "start_time":     time.time()
    }

    # Flatten technical + behavioral into one ordered list for the frontend
    all_questions = (
        [{**q, "type": "TECHNICAL"}  for q in questions.get("technical",  [])] +
        [{**q, "type": "BEHAVIORAL"} for q in questions.get("behavioral", [])]
    )

    _save_sessions()
    return jsonify({
        "success":    True,
        "session_id": session_id,
        "questions":  all_questions,
        "domain":     candidate_data.get("domain", "General"),
        "mode":       mode
    })

@app.route("/api/interview/answer", methods=["POST"])
def api_interview_answer():
    """
    Evaluate a single interview answer and store it in the session.

    Request body (JSON):
      session_id    — from /api/interview/start
      question      — the question text that was asked
      answer        — the candidate's answer text
      question_num  — 1-based question index
      type          — 'TECHNICAL' or 'BEHAVIORAL'
      topic         — question topic for the report (optional)
      time_taken    — seconds the candidate spent answering

    Returns the AI evaluation scores and proctor flags for this answer.
    """
    data       = request.json
    session_id = data.get("session_id")
    question   = data.get("question")
    answer     = data.get("answer")
    q_num      = data.get("question_num")
    q_type     = data.get("type")
    topic      = data.get("topic", "")
    time_taken = data.get("time_taken", 0)

    if session_id not in interview_session:
        return jsonify({"error": "Session not found"}), 404

    session    = interview_session[session_id]
    job_title  = session["job_title"]
    domain     = session["candidate_data"].get("domain", "General")

    evaluation = evaluate_answer(question, answer, job_title, domain)  # AI scores: relevance/depth/clarity/correctness
    proctor    = proctor_check(q_num, answer, time_taken)               # rule-based suspicion flags (copy-paste, too fast, etc.)

    session["responses"].append({
        "question_num": q_num,
        "type":         q_type,
        "topic":        topic,
        "question":     question,
        "answer":       answer,
        "time_taken":   time_taken,
        "score":        evaluation.get("total", 0),
        "evaluation":   evaluation,
        "proctor":      proctor
    })
    session["proctor_log"].append(proctor)
    _save_sessions()

    return jsonify({"success": True, "evaluation": evaluation, "proctor": proctor})

@app.route("/api/interview/finish", methods=["POST"])
def api_interview_finish():
    """
    Complete the interview: compute final scores, save transcript, delete session.

    Request body (JSON):
      session_id  — from /api/interview/start
      candidate   — dict with candidate_name, source_file, rank, score

    Computes:
      - Aggregate interview score (sum of per-question scores)
      - Technical vs behavioural breakdown
      - Proctor flag count (text-based + webcam combined)
      - Final proctoring status (CLEAN / FLAGGED)

    Saves the full transcript JSON and frees the in-memory session.
    Returns the complete result dict for display in the UI.
    """
    data         = request.json
    session_id   = data.get("session_id")
    candidate    = data.get("candidate")

    if session_id not in interview_session:
        return jsonify({"error": "Session not found"}), 404

    session     = interview_session[session_id]
    responses   = session["responses"]   # list of per-question result dicts
    proctor_log = session["proctor_log"] # text-based proctor flags
    webcam_log  = session.get("webcam_log", [])  # face-detection flags appended on /api/webcam/stop

    total_score    = sum(r["evaluation"].get("total", 0) for r in responses)
    total_q        = len(responses)
    max_score      = total_q * 10  # each question is worth 10 points
    percentage     = round((total_score / max_score) * 100, 1) if max_score > 0 else 0
    flagged_count  = sum(1 for p in proctor_log if p["flagged"])  # text-proctor flags

    # Separate technical and behavioral for the detailed breakdown section of the report
    tech_responses = [r for r in responses if r["type"] == "TECHNICAL"]
    beh_responses  = [r for r in responses if r["type"] == "BEHAVIORAL"]
    tech_score     = sum(r["score"] for r in tech_responses)
    beh_score      = sum(r["score"] for r in beh_responses)
    tech_max       = len(tech_responses) * 10
    beh_max        = len(beh_responses)  * 10

    # Merge webcam flags into proctoring status
    # More than 2 combined flags (text + webcam) = FLAGGED for HR review
    webcam_flags  = len(webcam_log)
    total_flags   = flagged_count + webcam_flags
    proctor_status = "FLAGGED" if total_flags > 2 else "CLEAN"

    result = {
        "candidate_name":    candidate.get("candidate_name", "Unknown"),
        "source_file":       candidate.get("source_file", ""),
        "rank":              candidate.get("rank", 0),
        "ranking_score":     candidate.get("score", 0),
        "job_title":         session["job_title"],
        "interview_mode":    session.get("mode", "text"),
        "domain":            session["candidate_data"].get("domain", "General"),
        "interview_date":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "responses":         responses,
        "proctor_log":       proctor_log,
        "webcam_log":        webcam_log,
        "total_score":       total_score,
        "max_score":         max_score,
        "percentage":        percentage,
        "technical_score":   tech_score,
        "technical_max":     tech_max,
        "technical_pct":     round((tech_score / tech_max * 100), 1) if tech_max > 0 else 0,
        "behavioral_score":  beh_score,
        "behavioral_max":    beh_max,
        "behavioral_pct":    round((beh_score / beh_max * 100), 1) if beh_max > 0 else 0,
        "flagged_count":     total_flags,
        "proctoring_status": proctor_status
    }

    output_path = OUTPUT_FOLDER / "interviews"
    output_path.mkdir(exist_ok=True)
    save_interview_result(result, output_path)  # writes interview_<name>.json
    del interview_session[session_id]           # free memory; transcript is safely on disk
    _save_sessions()                            # update session_state.json to reflect deletion

    return jsonify({"success": True, "result": result})

# ─────────────────────────────────────────────
# API — VOICE INTERVIEW
# ─────────────────────────────────────────────
# Voice mode runs on top of the same text interview flow: the same session_id
# is shared between /api/interview/* and /api/voice/*.  The voice endpoints
# add TTS output and microphone input around each question-answer cycle.
# ─────────────────────────────────────────────

@app.route("/api/voice/check", methods=["GET"])
def api_voice_check():
    """Check if microphone and TTS are available on this machine."""
    mic    = check_microphone()
    tts    = check_tts()
    return jsonify({
        "mic": mic,
        "tts": tts,
        "voice_ready": mic["available"] and tts["available"]
    })

@app.route("/api/voice/start", methods=["POST"])
def api_voice_start():
    """Initialize a voice session: start the TTS engine and calibrate the microphone."""
    data           = request.json
    session_id     = data.get("session_id")
    candidate_name = data.get("candidate_name")
    job_title      = data.get("job_title")

    if session_id not in interview_session:
        return jsonify({"error": "Interview session not found"}), 404

    # sr_ok = True if the microphone was calibrated successfully
    sr_ok = create_voice_session(session_id, candidate_name, job_title)
    return jsonify({"success": True, "mic_available": sr_ok})

@app.route("/api/voice/speak-question", methods=["POST"])
def api_voice_speak_question():
    """
    Speak the current question out loud using the TTS engine.

    The question is prefixed with its number and type (e.g. 'Question 3 of 10 — Technical:').
    The browser waits for this call to return before enabling the 'Listen' button.
    """
    data       = request.json
    session_id = data.get("session_id")
    q_num      = data.get("q_num", 1)
    total      = data.get("total", 1)
    q_type     = data.get("q_type", "")
    question   = data.get("question", "")

    speak_question(session_id, q_num, total, q_type, question)
    return jsonify({"success": True})

@app.route("/api/voice/listen", methods=["POST"])
def api_voice_listen():
    """
    Listen for the candidate's spoken answer.

    This is a BLOCKING call: it waits for the candidate to speak and then
    returns the transcribed text.  Times out after SPEECH_TIMEOUT seconds
    if the candidate stays silent.  Falls back to CMU Sphinx if Google is
    unavailable.
    """
    data       = request.json
    session_id = data.get("session_id")

    result = listen_answer(session_id)
    return jsonify(result)

@app.route("/api/voice/end", methods=["POST"])
def api_voice_end():
    """End the voice session: speak a farewell message and shut down the TTS engine."""
    data       = request.json
    session_id = data.get("session_id")
    end_voice_session(session_id)
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# API — BROWSER PROCTORING
# ─────────────────────────────────────────────
# The frontend JavaScript detects tab-switching (visibilitychange event),
# window blur, or right-click menu events and POSTs a browser flag here.
# This complements the webcam proctor with browser-level integrity checks.
# ─────────────────────────────────────────────

@app.route("/api/proctor/browser_flag", methods=["POST"])
def api_proctor_browser_flag():
    data = request.json
    session_id = data.get("session_id")
    flag_type = data.get("type", "UNKNOWN_BROWSER_FLAG")
    
    if session_id in interview_session:
        # Append the browser flag as a pseudo proctor event so it
        # appears alongside text-proctor and webcam flags in the report
        event = {
            "question_num": "BROWSER",
            "time_taken_seconds": 0,
            "flags": [flag_type],
            "flagged": True
        }
        interview_session[session_id]["proctor_log"].append(event)
        _save_sessions()
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# API — WEBCAM PROCTORING
# ─────────────────────────────────────────────
# Each webcam endpoint delegates to the webcam_proctor module's session store.
# The /api/webcam/frame polling endpoint is called by the frontend every
# ~500ms to display the live webcam feed in the corner of the interview UI.
# ─────────────────────────────────────────────

@app.route("/api/webcam/check", methods=["GET"])
def api_webcam_check():
    """Check if a working webcam is connected before starting the interview."""
    return jsonify(check_webcam_available())

@app.route("/api/webcam/start", methods=["POST"])
def api_webcam_start():
    """Start webcam face-detection proctoring for the given interview session."""
    data       = request.json
    session_id = data.get("session_id")
    result     = start_proctoring(session_id)
    return jsonify(result)

@app.route("/api/webcam/frame", methods=["GET"])
def api_webcam_frame():
    """Return latest webcam frame as base64 JPEG."""
    session_id = request.args.get("session_id", "")
    frame      = get_frame(session_id)
    if frame:
        return jsonify({"success": True, "frame": frame})
    return jsonify({"success": False, "frame": None})

@app.route("/api/webcam/status", methods=["GET"])
def api_webcam_status():
    """Return current proctor status (face count, flags)."""
    session_id = request.args.get("session_id", "")
    return jsonify(get_proctor_status(session_id))

@app.route("/api/webcam/stop", methods=["POST"])
def api_webcam_stop():
    """Stop webcam proctoring and attach the summary to the interview session."""
    data       = request.json
    session_id = data.get("session_id")

    summary = stop_proctoring(session_id)

    # Move webcam flag events into the interview session so they are included
    # in the transcript saved by /api/interview/finish
    if session_id in interview_session:
        interview_session[session_id]["webcam_log"] = summary.get("events", [])
        _save_sessions()

    return jsonify({"success": True, "summary": summary})

# ─────────────────────────────────────────────
# API — REPORTS
# ─────────────────────────────────────────────

@app.route("/api/generate-reports", methods=["POST"])
def api_generate_reports():
    """
    Generate AI-powered HR reports for all completed interview transcripts.

    For each interview JSON in output/interviews/:
      1. calculate_combined_score()  — 40% resume ranking + 60% interview score
      2. generate_ai_report()        — Ollama LLM produces HR narrative, strengths,
                                       gaps, hire recommendation, and risk level
      3. save_report_txt() + save_report_json()  — write the report to output/reports/

    After processing all transcripts, saves a final_summary JSON that provides
    an at-a-glance ranked table of all candidates for the HR manager.

    Returns: {success, count, reports: [{candidate_name, scores, recommendation, ...}]}
    """
    interviews_path = OUTPUT_FOLDER / "interviews"
    output_path     = OUTPUT_FOLDER / "reports"
    output_path.mkdir(exist_ok=True)

    transcripts = load_interview_transcripts(interviews_path)
    if not transcripts:
        return jsonify({"error": "No interview transcripts found"}), 404

    pipeline_tasks["reports"] = {"status": "running", "started": time.time()}
    _save_tasks()

    all_reports   = []
    success_count = 0

    for transcript in transcripts:
        combined_score = calculate_combined_score(transcript)  # 40% resume + 60% interview
        ai_report      = generate_ai_report(transcript)        # Ollama LLM narrative
        if not ai_report:
            continue  # skip if AI call failed (logged internally)
        save_report_txt(transcript, ai_report, combined_score, output_path)
        save_report_json(transcript, ai_report, combined_score, output_path)
        all_reports.append({
            "candidate_name":      transcript.get("candidate_name", "Unknown"),
            "source_file":         transcript.get("source_file", ""),
            "combined_score":      combined_score,
            "ranking_score":       transcript.get("ranking_score", 0),
            "interview_pct":       transcript.get("percentage", 0),
            "proctoring_status":   transcript.get("proctoring_status", "UNKNOWN"),
            "hire_recommendation": ai_report.get("hire_recommendation", "N/A"),
            "risk_level":          ai_report.get("risk_level", "N/A"),
            "key_strengths":       ai_report.get("key_strengths", []),
            "key_gaps":            ai_report.get("key_gaps", [])
        })
        success_count += 1

    if all_reports:
        save_final_summary(all_reports, output_path)

    pipeline_tasks["reports"] = {"status": "done", "result": {"count": success_count}}
    _save_tasks()

    return jsonify({"success": True, "count": success_count, "reports": all_reports})

# ─────────────────────────────────────────────
# API — PDF REPORT EXPORT
# ─────────────────────────────────────────────

from io import BytesIO

@app.route("/api/report-pdf/<filename>")
@login_required
def api_report_pdf(filename):
    """Generate and return a PDF version of a stored JSON report."""
    import unicodedata
    from fpdf import FPDF

    def _safe(s):
        """Convert any string to Latin-1 safe text for fpdf2 core fonts."""
        if s is None:
            return ""
        s = str(s)
        # Normalise unicode (e.g. smart quotes → plain chars)
        s = unicodedata.normalize("NFKD", s)
        # Drop combining diacritics, replace remaining non-Latin-1 chars
        return s.encode("latin-1", errors="replace").decode("latin-1")

    # Sanitise filename to prevent path traversal
    safe = re.sub(r'[^a-zA-Z0-9_.\-]', '', filename)
    json_path = OUTPUT_FOLDER / "reports" / safe
    if not json_path.exists() or not json_path.suffix == '.json':
        return jsonify({"error": "Report not found"}), 404

    try:
        with open(json_path, encoding="utf-8") as f:
            report = json.load(f)
    except (IOError, json.JSONDecodeError):
        return jsonify({"error": "Report file is corrupted"}), 500

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Post-Interview Evaluation Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    # Metadata
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _safe(f"Candidate    : {report.get('candidate_name', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _safe(f"Job Title    : {report.get('job_title', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _safe(f"Domain       : {report.get('domain', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _safe(f"Interview    : {report.get('interview_date', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _safe(f"Generated    : {report.get('generated_at', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Fairness     : Scoring based on skills/experience only. Name, gender, age NOT used.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Scores
    scores = report.get("scores", {})
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Score Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"  Combined Score      : {scores.get('combined_score', 0)}/100  (40% Resume + 60% Interview)", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"  Resume Ranking      : {scores.get('ranking_score', 0)}/100", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"  Interview           : {scores.get('interview_pct', 0)}%  (Technical: {scores.get('technical_pct', 0)}%  Behavioral: {scores.get('behavioral_pct', 0)}%)", new_x="LMARGIN", new_y="NEXT")
    proctor = report.get("proctoring", {})
    pdf.cell(0, 6, f"  Proctoring          : {proctor.get('status', 'N/A')} ({proctor.get('flagged_count', 0)} flags)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    ai = report.get("ai_report", {})

    # Summary
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Overall Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _safe(ai.get("overall_summary", "N/A")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Technical
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Technical Assessment", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _safe(ai.get("technical_assessment", "N/A")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Behavioral
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Behavioral Assessment", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _safe(ai.get("behavioral_assessment", "N/A")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Strengths
    strengths = ai.get("key_strengths", [])
    if strengths:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Key Strengths", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for s in strengths:
            pdf.cell(0, 6, _safe(f"  + {s}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # Gaps
    gaps = ai.get("key_gaps", [])
    if gaps:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Key Gaps", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for g in gaps:
            pdf.cell(0, 6, _safe(f"  - {g}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # Hire Recommendation
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, _safe(f"Recommendation: {ai.get('hire_recommendation', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _safe(f"Risk Level: {ai.get('risk_level', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(0, 5, _safe(ai.get("hire_justification", "")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Q&A
    responses = report.get("responses", [])
    if responses:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Detailed Q&A Transcript", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        for r in responses:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 5, _safe(f"Q{r.get('question_num','')} [{r.get('type','')}] - {r.get('topic','')}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, _safe(f"Q: {r.get('question','')}"), new_x="LMARGIN", new_y="NEXT")
            pdf.multi_cell(0, 5, _safe(f"A: {r.get('answer','')}"), new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 5, f"Score: {r.get('score',0)}/10  |  Time: {r.get('time_taken',0)}s", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

    # Output
    buf = BytesIO()
    buf.write(pdf.output())
    buf.seek(0)

    candidate = re.sub(r'[^a-zA-Z0-9_]', '_', report.get("candidate_name", "report"))
    return Response(
        buf.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{candidate}.pdf"}
    )


@app.route("/api/save-report-pdf/<filename>")
@login_required
def api_save_report_pdf(filename):
    """Generate PDF, save to output/reports/ and open with system PDF viewer."""
    import os as _os

    # Sanitise filename
    safe = re.sub(r'[^a-zA-Z0-9_.\\-]', '', filename)
    json_path = OUTPUT_FOLDER / "reports" / safe
    if not json_path.exists() or json_path.suffix != '.json':
        return jsonify({"error": "Report not found"}), 404

    try:
        with open(json_path, encoding="utf-8") as f:
            report = json.load(f)
    except (IOError, json.JSONDecodeError):
        return jsonify({"error": "Report file is corrupted"}), 500

    # Build PDF using the same logic as api_report_pdf
    try:
        import unicodedata
        from fpdf import FPDF

        def _safe(s):
            if s is None: return ""
            s = str(s)
            s = unicodedata.normalize("NFKD", s)
            return s.encode("latin-1", errors="replace").decode("latin-1")

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Post-Interview Evaluation Report", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, _safe(f"Candidate    : {report.get('candidate_name','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, _safe(f"Job Title    : {report.get('job_title','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, _safe(f"Domain       : {report.get('domain','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, _safe(f"Interview    : {report.get('interview_date','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, _safe(f"Generated    : {report.get('generated_at','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, "Fairness     : Scoring based on skills/experience only.", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        scores = report.get("scores", {})
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Score Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"  Combined Score      : {scores.get('combined_score',0)}/100  (40% Resume + 60% Interview)", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"  Resume Ranking      : {scores.get('ranking_score',0)}/100", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"  Interview           : {scores.get('interview_pct',0)}%  (Technical: {scores.get('technical_pct',0)}%  Behavioral: {scores.get('behavioral_pct',0)}%)", new_x="LMARGIN", new_y="NEXT")
        proctor = report.get("proctoring", {})
        pdf.cell(0, 6, f"  Proctoring          : {proctor.get('status','N/A')} ({proctor.get('flagged_count',0)} flags)", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        ai = report.get("ai_report", {})
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Overall Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _safe(ai.get("overall_summary","N/A")), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Technical Assessment", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _safe(ai.get("technical_assessment","N/A")), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Behavioral Assessment", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _safe(ai.get("behavioral_assessment","N/A")), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        for label, key in [("Key Strengths","key_strengths"),("Key Gaps","key_gaps")]:
            items = ai.get(key, [])
            if items:
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, label, new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 10)
                prefix = "  + " if "Strength" in label else "  - "
                for item in items:
                    pdf.cell(0, 6, _safe(prefix + item), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, _safe(f"Recommendation: {ai.get('hire_recommendation','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, _safe(f"Risk Level: {ai.get('risk_level','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 5, _safe(ai.get("hire_justification","")), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        responses = report.get("responses", [])
        if responses:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Detailed Q&A Transcript", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            for r in responses:
                pdf.set_font("Helvetica", "B", 10)
                pdf.multi_cell(0, 5, _safe(f"Q{r.get('question_num','')} [{r.get('type','')}] - {r.get('topic','')}"), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(0, 5, _safe(f"Q: {r.get('question','')}"), new_x="LMARGIN", new_y="NEXT")
                pdf.multi_cell(0, 5, _safe(f"A: {r.get('answer','')}"), new_x="LMARGIN", new_y="NEXT")
                score_time = f"Score: {r.get('score',0)}/10  |  Time: {r.get('time_taken',0)}s"
                pdf.cell(0, 5, score_time, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)

        candidate = re.sub(r'[^a-zA-Z0-9_]', '_', report.get("candidate_name", "report"))
        pdf_name = f"report_{candidate}.pdf"
        pdf_path = OUTPUT_FOLDER / "reports" / pdf_name
        pdf.output(str(pdf_path))

    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {e}"}), 500

    # Open with system default PDF viewer
    try:
        _os.startfile(str(pdf_path))
    except Exception:
        pass

    return jsonify({"success": True, "path": str(pdf_path)})

# ─────────────────────────────────────────────
# LAUNCH
# ─────────────────────────────────────────────
# The pywebview desktop window is created on the MAIN thread (required by some
# OS window managers), while Flask runs in a background daemon thread.
# A 1-second sleep gives Flask time to bind its port before the window loads
# http://localhost:5000.  The Api class exposes JavaScript-callable Python
# methods for native window controls (minimize, maximize, close) that the
# custom frameless title bar uses.
# ─────────────────────────────────────────────

def run_flask():
    """Start the Flask development server on all interfaces (0.0.0.0:5000) over HTTPS.

    HTTPS is required so that candidates' browsers allow getUserMedia (camera)
    when accessing the interview page over LAN (non-localhost origins).
    A self-signed certificate is generated on first run.
    """
    cert_path, key_path = _ensure_ssl_cert()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False,
            ssl_context=(cert_path, key_path))

if __name__ == "__main__":
    # Start Flask in a background daemon thread so it dies when the window closes
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    time.sleep(1)  # give Flask time to bind port 5000 before the window loads

    class Api:
        """JavaScript-callable Python class for native window controls.

        pywebview exposes this as window.pywebview.api.minimize() etc.
        in the browser JavaScript.  This gives the frameless window
        its minimize, maximize, and close buttons.
        """
        def minimize(self):
            webview.windows[0].minimize()
        def maximize(self):
            webview.windows[0].toggle_fullscreen()
        def close(self):
            webview.windows[0].destroy()

    api = Api()
    webview.create_window(
        title     = "AI Recruitment System",
        url       = "https://localhost:5000",
        width     = 1280,
        height    = 800,
        min_size  = (1024, 700),
        resizable = True,
        frameless = True,
        js_api=api
    )
    webview.start()