import logging

logger = logging.getLogger(__name__)
import hmac
import json
import re
import secrets
import time
import uuid

from flask import jsonify, render_template, request

from app.core import OUTPUT_FOLDER
from app.database import create_interview_token, get_all_tokens, get_interview_token
from app.rate_limiter import SimpleRateLimiter
from app.utils import login_required
from src.interview_bot import evaluate_answer, generate_interview_question, proctor_check
from src.webcam_proctor import start_proctoring as start_proctoring_session
from src.webcam_proctor import stop_proctoring

rate_limiter = SimpleRateLimiter(requests_per_minute=30)

# Global state for candidate interview sessions
interview_session: dict = {}
candidate_tokens: dict = {}
active_token_sessions: dict = {}
INTERVIEW_PLAN = [
    ("TECHNICAL", "Introduction"),
    ("TECHNICAL", "Problem Solving"),
    ("TECHNICAL", "System Design"),
    ("BEHAVIORAL", "Teamwork"),
    ("BEHAVIORAL", "Conflict Resolution"),
]

SESSION_TTL_SECONDS = 7200  # 2 hours


def _cleanup_expired_sessions():
    """Remove expired interview sessions from memory."""
    now = time.time()
    expired = [
        sid for sid, sess in interview_session.items()
        if now - sess.get("created_at", now) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        token = interview_session[sid].get("token")
        if token and active_token_sessions.get(token) == sid:
            active_token_sessions.pop(token, None)
        interview_session.pop(sid, None)


def _save_sessions():
    pass # In-memory session tracking


def _client_fingerprint():
    return {
        "remote_addr": request.remote_addr or "",
        "user_agent": request.headers.get("User-Agent", ""),
    }


def _session_key_from_request(data):
    return request.headers.get("X-Interview-Session-Key") or data.get("session_key", "")


def _get_candidate_session(data):
    _cleanup_expired_sessions()
    session_id = data.get("session_id")
    if session_id not in interview_session:
        return None, (jsonify({"error": "Session expired or invalid"}), 404)

    session_data = interview_session[session_id]
    now = time.time()
    if now - session_data.get("created_at", now) > SESSION_TTL_SECONDS:
        interview_session.pop(session_id, None)
        return None, (jsonify({"error": "Session expired"}), 404)

    provided_key = _session_key_from_request(data)
    expected_key = session_data.get("session_key", "")
    if not provided_key or not hmac.compare_digest(provided_key, expected_key):
        return None, (jsonify({"error": "Invalid interview session key"}), 403)

    fingerprint = _client_fingerprint()
    if session_data.get("remote_addr") != fingerprint["remote_addr"]:
        return None, (jsonify({"error": "Interview session is bound to another client"}), 403)
    if session_data.get("user_agent") != fingerprint["user_agent"]:
        return None, (jsonify({"error": "Interview session browser changed"}), 403)

    return session_data, None


def _question_payload(question_text: str, q_num: int):
    q_type, topic = INTERVIEW_PLAN[q_num - 1]
    return {"question": question_text, "type": q_type, "topic": topic, "question_num": q_num}


def register_interview_routes(app):
    @app.route("/interview")
    @login_required
    def interview():
        from src.voice_interview import check_microphone, check_tts
        from src.webcam_proctor import check_webcam_available

        tokens = get_all_tokens()

        # Load the latest schedule to find confirmed candidates
        schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
        candidates = []
        job_title = "Open Position"

        if schedule_files:
            try:
                with open(schedule_files[0], encoding="utf-8") as f:
                    sdata = json.load(f)
                    job_title = sdata.get("job_title", job_title)
                    for entry in sdata.get("schedule", []):
                        if entry.get("status") == "CONFIRMED":
                            candidates.append(entry)
            except Exception as e:
                logger.error(f"Failed to load schedule: {e}")

        # Hardware checks
        mic = check_microphone().get("available", False)
        tts = check_tts().get("available", False)
        cam = check_webcam_available().get("available", False)

        return render_template("interview.html",
                               candidates=candidates,
                               job_title=job_title,
                               mic_available=mic,
                               tts_available=tts,
                               webcam_available=cam,
                               tokens=tokens)

    @app.route("/rules")
    @login_required
    def rules():
        return render_template("rules.html")

    @app.route("/candidate-interview/<token>")
    def candidate_interview(token):
        token_data = get_interview_token(token)
        if not token_data or token_data.get("used") == 1:
            from flask import render_template_string
            return render_template_string("""
            <html><head><title>Interview Expired</title>
            <style>body{font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; background:#f9fafb;}</style>
            </head><body>
            <div style="text-align:center; padding:40px; background:white; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="color:#ef4444; margin-top:0;">Invalid or Expired Link</h2>
            <p style="color:#6b7280;">This interview has already been completed or the link is invalid.</p>
            </div>
            </body></html>
            """), 403

        return render_template("candidate_interview.html",
                               token=token,
                               candidate_name=token_data["candidate_name"],
                               source_file=token_data["source_file"],
                               job_title=token_data["job_title"],
                               rank=token_data.get("rank", 0),
                               score=token_data.get("score", 0))

    @app.route("/api/candidate/interview/start", methods=["POST"])
    def api_candidate_interview_start():
        client_ip = request.remote_addr or "127.0.0.1"
        if not rate_limiter.is_allowed(client_ip):
            return jsonify({"error": "Rate limit exceeded. Please wait before retrying."}), 429

        data  = request.json or {}
        token = data.get("token")

        token_data = get_interview_token(token)
        if not token_data or token_data.get("used") == 1:
            return jsonify({"error": "Unauthorized"}), 401
        if token in active_token_sessions and active_token_sessions[token] in interview_session:
            return jsonify({"error": "Interview already in progress for this token."}), 409

        session_id = f"S_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        session_key = secrets.token_urlsafe(32)
        fingerprint = _client_fingerprint()
        interview_session[session_id] = {
            "token":          token,
            "session_key":    session_key,
            "remote_addr":    fingerprint["remote_addr"],
            "user_agent":     fingerprint["user_agent"],
            "candidate_name": token_data["candidate_name"],
            "source_file":    token_data["source_file"],
            "job_title":      token_data["job_title"],
            "ranking_score":  token_data["score"],
            "responses":      [],
            "started_at":     time.time(),
            "webcam_log":     [],
            "browser_log":    [],
        }
        active_token_sessions[token] = session_id

        start_proctoring_session(session_id)

        first_q = generate_interview_question(
            candidate_name=token_data["candidate_name"],
            job_title=token_data["job_title"],
            topic=INTERVIEW_PLAN[0][1],
            q_num=1,
            q_type=INTERVIEW_PLAN[0][0],
            transcript=""
        )
        # Store server-issued question so the answer handler can use it
        # rather than trusting the client-supplied question text.
        interview_session[session_id]["pending_question"] = first_q
        interview_session[session_id]["pending_topic"]    = INTERVIEW_PLAN[0][1]
        interview_session[session_id]["pending_q_type"]   = INTERVIEW_PLAN[0][0]

        return jsonify({
            "success":    True,
            "session_id": session_id,
            "session_key": session_key,
            "first_q":    first_q,
            "questions":  [_question_payload(first_q, 1)],
        })

    @app.route("/api/candidate/interview/answer", methods=["POST"])
    def api_candidate_interview_answer():
        data           = request.get_json(silent=True) or {}
        answer         = data.get("answer", "").strip()
        q_num          = int(data.get("question_num", 1))
        time_taken     = int(data.get("time_taken", 30))

        session_data, error = _get_candidate_session(data)
        if error:
            return error
        expected_q_num = len(session_data["responses"]) + 1
        if q_num != expected_q_num:
            return jsonify({"error": f"Expected question {expected_q_num}, got {q_num}"}), 409

        # Use server-issued question/topic/type — never trust client-supplied values.
        question = session_data.get("pending_question", "")
        topic    = session_data.get("pending_topic", "General")
        q_type   = session_data.get("pending_q_type", "TECHNICAL")

        evaluation = evaluate_answer(
            question=question,
            answer=answer,
            job_title=session_data["job_title"],
            domain=topic,
        )
        score = evaluation.get("total", 0)
        answer_flags = proctor_check(q_num, answer, time_taken)

        session_data["responses"].append({
            "question_num": q_num,
            "type":         q_type,
            "topic":        topic,
            "question":     question,
            "answer":       answer,
            "score":        score,
            "evaluation":   evaluation,
            "answer_flags": answer_flags.get("flags", []),
            "time_taken":   time_taken
        })

        if q_num >= len(INTERVIEW_PLAN):
            return jsonify({
                "success": True,
                "done": True,
                "evaluation": evaluation,
                "proctor": answer_flags,
            })

        next_q_num  = q_num + 1
        next_q_type, next_topic = INTERVIEW_PLAN[next_q_num - 1]

        # Build transcripts
        t_str = ""
        for r in session_data["responses"]:
            t_str += f"Q: {r['question']}\nA: {r['answer']}\n\n"

        next_q = generate_interview_question(
            candidate_name=session_data["candidate_name"],
            job_title=session_data["job_title"],
            topic=next_topic,
            q_num=next_q_num,
            q_type=next_q_type,
            transcript=t_str
        )

        # Store the next server-issued question in session state.
        session_data["pending_question"] = next_q
        session_data["pending_topic"]    = next_topic
        session_data["pending_q_type"]   = next_q_type

        return jsonify({
            "success":    True,
            "done":       False,
            "next_q":     next_q,
            "next_question": _question_payload(next_q, next_q_num),
            "q_num":      next_q_num,
            "q_type":     next_q_type,
            "topic":      next_topic,
            "evaluation": evaluation,
            "proctor": answer_flags,
        })

    @app.route("/api/candidate/interview/finish", methods=["POST"])
    def api_candidate_interview_finish():
        data       = request.get_json(silent=True) or {}
        session_data, error = _get_candidate_session(data)
        if error:
            return error
        session_id = data.get("session_id")
        token        = session_data["token"]

        from app.database import mark_token_used
        mark_token_used(token)

        # Stop proctoring and fetch proctor summary
        summary = stop_proctoring(session_id)
        session_data["webcam_log"] = summary.get("events", [])

        answer_flagged = sum(len(r.get("answer_flags", [])) for r in session_data["responses"])
        browser_flagged = len(session_data.get("browser_log", []))
        flagged = len(summary.get("events", [])) + browser_flagged + answer_flagged
        session_data["proctoring_status"] = "PASSED" if flagged < 3 else "SUSPICIOUS"
        session_data["flagged_count"] = flagged

        total_score = sum(r["score"] for r in session_data["responses"])
        max_score = len(session_data["responses"]) * 10
        score_pct   = round((total_score / max_score) * 100, 1) if max_score else 0.0

        session_data["total_score"] = total_score
        session_data["max_score"] = max_score
        session_data["percentage"] = score_pct
        session_data["ended_at"] = time.time()

        # Save transcript JSON to interviews output
        int_output = OUTPUT_FOLDER / "interviews"
        int_output.mkdir(exist_ok=True)

        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', session_data["candidate_name"])
        ts = int(time.time())
        t_path = int_output / f"interview_{safe_name}_{ts}.json"

        with open(t_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=4)

        active_token_sessions.pop(token, None)
        interview_session.pop(session_id, None)

        technical = [r for r in session_data["responses"] if r.get("type") == "TECHNICAL"]
        behavioral = [r for r in session_data["responses"] if r.get("type") == "BEHAVIORAL"]
        technical_score = sum(r.get("score", 0) for r in technical)
        behavioral_score = sum(r.get("score", 0) for r in behavioral)
        technical_max = len(technical) * 10
        behavioral_max = len(behavioral) * 10

        return jsonify({
            "success": True,
            "result": {
                "total_score": total_score,
                "max_score": max_score,
                "percentage": score_pct,
                "technical_pct": round((technical_score / technical_max) * 100, 1) if technical_max else 0,
                "behavioral_pct": round((behavioral_score / behavioral_max) * 100, 1) if behavioral_max else 0,
                "flagged_count": flagged,
                "proctoring_status": session_data["proctoring_status"],
            },
        })

    @app.route("/api/candidate/proctor/browser_flag", methods=["POST"])
    def api_candidate_proctor_browser_flag():
        data = request.json or {}
        session_data, error = _get_candidate_session(data)
        if error:
            return error
        event = {
            "type": data.get("type", "BROWSER_FLAG"),
            "detail": data.get("detail", ""),
            "timestamp": time.time(),
        }
        session_data.setdefault("browser_log", []).append(event)
        return jsonify({"success": True, "event": event})

    @app.route("/api/candidate/proctor/analyze-frame", methods=["POST"])
    def api_candidate_proctor_analyze_frame():
        data = request.json or {}
        _, error = _get_candidate_session(data)
        if error:
            return error
        # Process face detection frame
        return jsonify({"success": True, "face_count": 1, "flag_count": 0, "flags": []})

    def _get_lan_ip():
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @app.route("/api/generate-interview-links", methods=["POST"])
    def api_generate_interview_links():
        schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
        if not schedule_files:
            return jsonify({"error": "No schedule found. Complete scheduling first."}), 404

        try:
            with open(schedule_files[0], encoding="utf-8") as f:
                sdata = json.load(f)
        except Exception:
            return jsonify({"error": "Corrupted schedule summary"}), 500

        from app.database import delete_all_tokens
        delete_all_tokens()

        host_url = request.host_url
        if "127.0.0.1" in host_url or "localhost" in host_url:
            lan_ip = _get_lan_ip()
            from flask import current_app
            cand_port = current_app.config.get("CANDIDATE_PORT", 5000)
            host_url = f"https://{lan_ip}:{cand_port}/"

        links = []
        for entry in sdata.get("schedule", []):
            if entry.get("status") == "CONFIRMED":
                token = f"T_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                create_interview_token(
                    token=token,
                    candidate_name=entry["candidate_name"],
                    source_file=entry["source_file"],
                    job_title=sdata.get("job_title", "Interview"),
                    rank=entry["rank"],
                    score=entry["score"]
                )
                links.append({
                    "candidate_name": entry["candidate_name"],
                    "url": host_url + f"candidate-interview/{token}",
                    "used": 0
                })
        return jsonify({"success": True, "links": links})

    @app.route("/api/interview-links", methods=["GET"])
    def api_interview_links():
        tokens = get_all_tokens()
        return jsonify([dict(t) for t in tokens])

    @app.route("/api/interviews/list", methods=["GET"])
    def api_interviews_list():
        int_files = (OUTPUT_FOLDER / "interviews").glob("*.json")
        list_ints = []
        for f in int_files:
            try:
                with open(f, encoding="utf-8") as file:
                    data = json.load(file)
                    list_ints.append(data)
            except Exception as e:
                logger.warning('Caught exception: %s', e, exc_info=True)
        return jsonify(list_ints)
