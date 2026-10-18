import logging

logger = logging.getLogger(__name__)
import hmac
import json
import os
import re
import secrets
import time
import uuid

from flask import jsonify, render_template, request

from app.core import OUTPUT_FOLDER
from app.database import create_interview_token, get_all_tokens, get_interview_token
from app.rate_limiter import SimpleRateLimiter
from app.utils import login_required
from src.interview_bot import (
    evaluate_answer,
    generate_adaptive_followup,
    generate_interview_question,
    is_tech_role,
    proctor_check,
    should_probe_further,
)
from src.webcam_proctor import start_proctoring as start_proctoring_session
from src.webcam_proctor import stop_proctoring

rate_limiter = SimpleRateLimiter(requests_per_minute=30)

# Global state for candidate interview sessions
interview_session: dict = {}
candidate_tokens: dict = {}
active_token_sessions: dict = {}

TECHNICAL_INTERVIEW_PLAN = [
    ("TECHNICAL", "Introduction"),
    ("TECHNICAL", "Problem Solving"),
    ("TECHNICAL", "System Design"),
    ("BEHAVIORAL", "Teamwork"),
    ("BEHAVIORAL", "Conflict Resolution"),
]

NON_TECHNICAL_INTERVIEW_PLAN = [
    ("DOMAIN EXPERTISE", "Introduction"),
    ("DOMAIN EXPERTISE", "Problem Solving & Scenarios"),
    ("DOMAIN EXPERTISE", "Strategy & Execution"),
    ("BEHAVIORAL", "Teamwork"),
    ("BEHAVIORAL", "Conflict Resolution"),
]

TECH_TOPICS = [
    "Introduction",
    "Problem Solving",
    "System Design",
    "Data Structures & Algorithms",
    "Debugging & Architecture",
    "Code Quality & Testing",
    "Performance Optimization",
    "Security & Threat Modeling",
    "DevOps & Cloud Systems",
    "Trade-offs & Scalability",
]

NON_TECH_TOPICS = [
    "Introduction",
    "Problem Solving & Scenarios",
    "Strategy & Execution",
    "Stakeholder & Client Management",
    "Project Prioritization & Roadmapping",
    "Operational Efficiency & Process",
    "Data-Driven Decision Making",
    "Negotiation & Influence",
    "Change Management",
    "Quality & Compliance",
]

BEHAVIORAL_TOPICS = [
    "Teamwork",
    "Conflict Resolution",
    "Adaptability & Managing Ambiguity",
    "Leadership & Ownership",
    "Time Management & High-Pressure Delivery",
]

INTERVIEW_PLAN = TECHNICAL_INTERVIEW_PLAN


def get_interview_plan_for_role(
    job_title: str = "",
    domain: str = "",
    tech_count: int | None = None,
    beh_count: int | None = None,
) -> list[tuple[str, str]]:
    """Determine the optimal interview plan based on role context and settings."""
    import config as cfg

    t_count = tech_count if tech_count is not None else getattr(cfg, "INTERVIEW_TECH_QUESTIONS", 3)
    b_count = beh_count if beh_count is not None else getattr(cfg, "INTERVIEW_BEH_QUESTIONS", 2)
    t_count = max(1, min(10, t_count))
    b_count = max(1, min(5, b_count))

    tech_flag = is_tech_role(job_title, domain)
    topic_pool = TECH_TOPICS if tech_flag else NON_TECH_TOPICS
    type_name = "TECHNICAL" if tech_flag else "DOMAIN EXPERTISE"

    selected_tech = [(type_name, topic_pool[i % len(topic_pool)]) for i in range(t_count)]
    selected_beh = [("BEHAVIORAL", BEHAVIORAL_TOPICS[i % len(BEHAVIORAL_TOPICS)]) for i in range(b_count)]

    return selected_tech + selected_beh

SESSION_TTL_SECONDS = 7200  # 2 hours


def _cleanup_expired_sessions():
    """Remove expired interview sessions from memory and SQLite."""
    try:
        from app.database import cleanup_expired_interview_sessions

        cleanup_expired_interview_sessions(SESSION_TTL_SECONDS)
    except Exception as e:
        logger.warning("Failed cleaning expired DB sessions: %s", e)

    now = time.time()
    expired = [
        sid
        for sid, sess in interview_session.items()
        if now - (sess.get("started_at") or sess.get("created_at", now)) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        token = interview_session[sid].get("token")
        if token and active_token_sessions.get(token) == sid:
            active_token_sessions.pop(token, None)
        interview_session.pop(sid, None)


def _save_sessions():
    """Persist all active in-memory sessions to SQLite."""
    try:
        from app.database import save_interview_session

        for sid, sess in interview_session.items():
            save_interview_session(sid, sess)
    except Exception as e:
        logger.warning("Failed persisting sessions: %s", e)


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
    if not session_id:
        return None, (jsonify({"error": "Missing session_id"}), 400)

    session_data = interview_session.get(session_id)
    if not session_data:
        # Attempt recovery from SQLite (e.g. following process restart)
        from app.database import get_interview_session

        session_data = get_interview_session(session_id)
        if session_data:
            interview_session[session_id] = session_data
            token = session_data.get("token")
            if token:
                active_token_sessions[token] = session_id

    if not session_data:
        return None, (jsonify({"error": "Session expired or invalid"}), 404)

    now = time.time()
    session_start = session_data.get("started_at") or session_data.get("created_at", now)
    if now - session_start > SESSION_TTL_SECONDS:
        interview_session.pop(session_id, None)
        try:
            from app.database import delete_interview_session

            delete_interview_session(session_id)
        except Exception:
            pass
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


def _question_payload(question_text: str, q_num: int, plan: list[tuple[str, str]] | None = None):
    active_plan = plan or INTERVIEW_PLAN
    if 1 <= q_num <= len(active_plan):
        q_type, topic = active_plan[q_num - 1]
    else:
        q_type, topic = "GENERAL", "Wrap-up"
    return {"question": question_text, "type": q_type, "topic": topic, "question_num": q_num}


def _resolve_candidate_job_context(token_data: dict) -> tuple[str, str, list]:
    """Resolve true job_title, domain, and candidate skills, avoiding 'Open Position' fallbacks."""
    job_title = (token_data.get("job_title") or "").strip()
    domain = ""
    skills = []

    source_file = token_data.get("source_file", "")
    nlp_path = OUTPUT_FOLDER / "nlp"
    nlp_candidates = []
    if source_file:
        nlp_candidates.extend([nlp_path / f"{source_file}.json", nlp_path / f"{source_file}_nlp.json"])
    c_name = token_data.get("candidate_name", "").lower()
    if nlp_path.exists():
        for p in nlp_path.glob("*_nlp.json"):
            nlp_candidates.append(p)

    for nf in nlp_candidates:
        if nf.exists():
            try:
                with open(nf, encoding="utf-8") as fh:
                    ndata = json.load(fh)
                name = ndata.get("personal_info", {}).get("name", "").lower()
                if not c_name or name == c_name or c_name in name:
                    domain = ndata.get("domain", "")
                    sdict = ndata.get("skills", {})
                    if isinstance(sdict, dict):
                        tech = sdict.get("technical_skills") or []
                        tools = sdict.get("tools_and_technologies") or []
                        skills = list(tech) + [t for t in tools if t not in tech]
                    elif isinstance(sdict, list):
                        skills = sdict
                    break
            except Exception:
                pass

    if not job_title or job_title in ("Open Position", "Interview"):
        ranking_path = OUTPUT_FOLDER / "ranking"
        rfiles = sorted(ranking_path.glob("ranking_scores*.json"), reverse=True)
        if rfiles:
            try:
                with open(rfiles[0], encoding="utf-8") as fh:
                    rdata = json.load(fh)
                    jd = rdata.get("job_description", {})
                    job_title = jd.get("job_title") or job_title
                    if not domain:
                        domain = jd.get("domain") or domain
            except Exception:
                pass

        if not job_title or job_title in ("Open Position", "Interview"):
            jd_path = OUTPUT_FOLDER / "jd"
            jfiles = sorted(jd_path.glob("jd_*.json"), reverse=True)
            if jfiles:
                try:
                    with open(jfiles[0], encoding="utf-8") as fh:
                        jd_data = json.load(fh)
                        job_title = jd_data.get("job_title") or job_title
                        if not domain:
                            domain = jd_data.get("domain") or domain
                except Exception:
                    pass

    if not job_title or job_title in ("Open Position", "Interview"):
        job_title = "Open Position"

    return job_title, domain, skills


def is_token_valid_and_active(token: str, max_age_hours: int = 72) -> tuple[bool, dict | None, str]:
    """Validate interview token existence, one-time status, and expiration.
    Returns (is_valid, token_data, rejection_reason).
    """
    if not token or not isinstance(token, str):
        return False, None, "Interview token is missing or invalid."
    token_data = get_interview_token(token)
    if not token_data:
        return False, None, "Invalid or nonexistent interview link."
    if token_data.get("used") == 1:
        return False, token_data, "This interview has already been completed or the token was used."
    created_str = token_data.get("created_at")
    if created_str:
        try:
            from datetime import datetime, timezone
            clean_str = created_str.replace("Z", "+00:00")
            created_dt = datetime.fromisoformat(clean_str)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if (now - created_dt).total_seconds() > (max_age_hours * 3600):
                return False, token_data, "This interview link has expired. Please contact HR for a new link."
        except Exception as e:
            logger.warning("Failed parsing token created_at: %s", e)
    return True, token_data, ""


def _get_lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe_target = os.environ.get("ROUTING_PROBE_HOST", "dns.google")
        s.connect((probe_target, 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def register_candidate_interview_routes(app):
    """Register strictly candidate-facing interview routes."""
    if "candidate_interview" in app.view_functions:
        return

    @app.route("/candidate-interview/<token>")
    def candidate_interview(token):
        valid, token_data, reason = is_token_valid_and_active(token)
        if not valid or not token_data:
            from flask import render_template_string
            return render_template_string(f"""
            <html><head><title>Interview Link Inactive</title>
            <style>body{{font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; background:#f9fafb;}}</style>
            </head><body>
            <div style="text-align:center; padding:40px; background:white; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="color:#ef4444; margin-top:0;">Invalid or Expired Link</h2>
            <p style="color:#6b7280;">{reason}</p>
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

        data = request.json or {}
        token = data.get("token")
        consent = data.get("consent")

        valid, token_data, reason = is_token_valid_and_active(token)
        if not valid or not token_data:
            return jsonify({"error": reason or "Unauthorized"}), 401

        if not consent:
            return jsonify({
                "error": "Candidate consent is required to proceed with the interview.",
                "code": 400,
            }), 400

        from app.database import get_active_session_by_token, save_interview_session

        if token in active_token_sessions and active_token_sessions[token] in interview_session:
            return jsonify({"error": "Interview already in progress for this token."}), 409

        existing_sid, existing_sess = get_active_session_by_token(token)
        if existing_sid and existing_sess:
            now = time.time()
            if now - (existing_sess.get("started_at") or existing_sess.get("created_at", now)) < SESSION_TTL_SECONDS:
                return jsonify({"error": "Interview already in progress for this token."}), 409

        job_title, domain, skills = _resolve_candidate_job_context(token_data)
        plan = get_interview_plan_for_role(job_title, domain)
        import config as cfg
        time_limit = getattr(cfg, "INTERVIEW_TIME_LIMIT_SECONDS", 120)
        session_id = f"S_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        session_key = secrets.token_urlsafe(32)
        fingerprint = _client_fingerprint()
        interview_session[session_id] = {
            "session_id":        session_id,
            "token":             token,
            "session_key":       session_key,
            "remote_addr":       fingerprint["remote_addr"],
            "user_agent":        fingerprint["user_agent"],
            "candidate_name":    token_data["candidate_name"],
            "source_file":       token_data["source_file"],
            "job_title":         job_title,
            "domain":            domain,
            "skills":            skills,
            "ranking_score":     token_data["score"],
            "consent_given":     True,
            "consent_timestamp": time.time(),
            "responses":         [],
            "started_at":        time.time(),
            "webcam_log":        [],
            "browser_log":       [],
            "interview_plan":    plan,
            "time_limit":        time_limit,
        }
        active_token_sessions[token] = session_id

        start_proctoring_session(session_id)

        first_q = generate_interview_question(
            candidate_name=token_data["candidate_name"],
            job_title=job_title,
            topic=plan[0][1],
            q_num=1,
            q_type=plan[0][0],
            transcript="",
            skills=skills,
            domain=domain,
        )
        interview_session[session_id]["pending_question"] = first_q
        interview_session[session_id]["pending_topic"]    = plan[0][1]
        interview_session[session_id]["pending_q_type"]   = plan[0][0]
        interview_session[session_id]["question_issued_at"] = time.time()
        save_interview_session(session_id, interview_session[session_id])

        return jsonify({
            "success":         True,
            "session_id":      session_id,
            "session_key":     session_key,
            "first_q":         first_q,
            "questions":       [_question_payload(first_q, 1, plan=plan)],
            "total_questions": len(plan),
            "time_limit":      time_limit,
        })

    @app.route("/api/candidate/interview/answer", methods=["POST"])
    def api_candidate_interview_answer():
        client_ip = request.remote_addr or "127.0.0.1"
        if not rate_limiter.is_allowed(client_ip):
            return jsonify({"error": "Rate limit exceeded. Please wait before retrying."}), 429

        data       = request.get_json(silent=True) or {}
        answer     = data.get("answer", "").strip()
        q_num      = int(data.get("question_num", 1))

        session_data, error = _get_candidate_session(data)
        if error:
            return error
        expected_q_num = len(session_data["responses"]) + 1
        is_followup_turn = bool(session_data.get("is_followup", False))

        # If previous turn was an un-answered follow-up probe and client advances to next question,
        # finalize the previous question with its initial evaluation.
        if is_followup_turn and q_num == expected_q_num + 1:
            prev_q_num = expected_q_num
            prev_topic = session_data.get("pending_topic", "General")
            prev_q_type = session_data.get("pending_q_type", "TECHNICAL")
            initial_q = session_data.get("initial_question", "")
            initial_ans = session_data.get("initial_answer", "")
            initial_eval = session_data.get("initial_evaluation") or evaluate_answer(
                question=initial_q,
                answer=initial_ans,
                job_title=session_data.get("job_title", "Technical Role"),
                domain=session_data.get("domain") or prev_topic,
            )
            session_data["responses"].append({
                "question_num": prev_q_num,
                "type": prev_q_type,
                "topic": prev_topic,
                "question": initial_q,
                "answer": initial_ans,
                "was_probed": True,
                "score": initial_eval.get("total", 0),
                "evaluation": initial_eval,
                "answer_flags": [],
                "time_taken": 0,
                "server_verified_time": 0.0,
            })
            session_data["is_followup"] = False
            session_data.pop("initial_question", None)
            session_data.pop("initial_answer", None)
            session_data.pop("initial_evaluation", None)
            expected_q_num = len(session_data["responses"]) + 1
            is_followup_turn = False

        if q_num != expected_q_num:
            return jsonify({"error": f"Expected question {expected_q_num}, got {q_num}"}), 409

        question = session_data.get("pending_question", "")
        topic    = session_data.get("pending_topic", "General")
        q_type   = session_data.get("pending_q_type", "TECHNICAL")

        now = time.time()
        issued_at = session_data.get("question_issued_at") or session_data.get("started_at") or now
        server_time_taken = max(0.5, round(now - issued_at, 1))

        # Server-side verification of answer latency bounds and typing speed
        server_proctor_flags = []
        if server_time_taken < 2.0 and len(answer.split()) > 5:
            server_proctor_flags.append("INSTANT_PASTE_DETECTED")
        elif len(answer) > 80 and (len(answer) / server_time_taken) > 25.0:
            server_proctor_flags.append("UNREALISTIC_TYPING_SPEED")

        if server_time_taken > 300.0:
            server_proctor_flags.append("PROLONGED_RESPONSE_DELAY")

        is_followup_turn = bool(session_data.get("is_followup", False))

        if is_followup_turn:
            initial_q = session_data.get("initial_question", question)
            initial_ans = session_data.get("initial_answer", "")
            followup_q = session_data.get("pending_question", question)

            if answer.upper() == "SKIP":
                full_answer = initial_ans
            else:
                full_answer = f"{initial_ans}\n\n[Candidate Follow-Up Elaboration]: {answer}"

            evaluation = evaluate_answer(
                question=initial_q,
                answer=full_answer,
                job_title=session_data.get("job_title", "Technical Role"),
                domain=session_data.get("domain") or topic,
            )
            score = evaluation.get("total", 0)
            answer_flags = proctor_check(q_num, answer, server_time_taken)
            all_flags = list(dict.fromkeys(answer_flags.get("flags", []) + server_proctor_flags))
            answer_flags["flags"] = all_flags
            answer_flags["flagged"] = len(all_flags) > 0
            answer_flags["server_verified_time"] = server_time_taken

            session_data["responses"].append({
                "question_num":        q_num,
                "type":                q_type,
                "topic":               topic,
                "question":            initial_q,
                "followup_question":   followup_q,
                "answer":              full_answer,
                "was_probed":          True,
                "score":               score,
                "evaluation":          evaluation,
                "answer_flags":        all_flags,
                "time_taken":          int(server_time_taken),
                "server_verified_time": server_time_taken,
            })

            session_data["is_followup"] = False
            session_data.pop("initial_question", None)
            session_data.pop("initial_answer", None)
        else:
            evaluation = evaluate_answer(
                question=question,
                answer=answer,
                job_title=session_data.get("job_title", "Technical Role"),
                domain=session_data.get("domain") or topic,
            )
            score = evaluation.get("total", 0)
            answer_flags = proctor_check(q_num, answer, server_time_taken)
            all_flags = list(dict.fromkeys(answer_flags.get("flags", []) + server_proctor_flags))
            answer_flags["flags"] = all_flags
            answer_flags["flagged"] = len(all_flags) > 0
            answer_flags["server_verified_time"] = server_time_taken

            probed_questions = session_data.get("probed_questions", [])
            if q_num not in probed_questions and should_probe_further(evaluation, answer):
                followup_q = generate_adaptive_followup(
                    question=question,
                    answer=answer,
                    job_title=session_data.get("job_title", "Technical Role"),
                    domain=session_data.get("domain") or topic,
                )
                session_data["is_followup"] = True
                session_data["initial_question"] = question
                session_data["initial_answer"] = answer
                session_data["initial_evaluation"] = evaluation
                session_data["pending_question"] = followup_q
                session_data["probed_questions"] = probed_questions + [q_num]
                session_data["question_issued_at"] = time.time()

                from app.database import save_interview_session
                save_interview_session(session_data.get("session_id", data.get("session_id")), session_data)

                return jsonify({
                    "success":           True,
                    "is_followup":       True,
                    "done":              False,
                    "followup_question": followup_q,
                    "original_question": question,
                    "question_num":      q_num,
                    "q_type":            q_type,
                    "topic":             topic,
                    "evaluation":        evaluation,
                    "proctor":           answer_flags,
                })

            session_data["responses"].append({
                "question_num":        q_num,
                "type":                q_type,
                "topic":               topic,
                "question":            question,
                "answer":              answer,
                "was_probed":          False,
                "score":               score,
                "evaluation":          evaluation,
                "answer_flags":        all_flags,
                "time_taken":          int(server_time_taken),
                "server_verified_time": server_time_taken,
            })

        plan = session_data.get("interview_plan") or get_interview_plan_for_role(
            session_data.get("job_title", ""),
            session_data.get("domain", ""),
        )

        if q_num >= len(plan):
            from app.database import save_interview_session
            save_interview_session(session_data.get("session_id", data.get("session_id")), session_data)
            return jsonify({
                "success":    True,
                "is_followup": False,
                "done":       True,
                "evaluation": evaluation,
                "proctor":    answer_flags,
            })

        next_q_num  = q_num + 1
        next_q_type, next_topic = plan[next_q_num - 1]

        t_str = ""
        for r in session_data["responses"]:
            t_str += f"Q: {r['question']}\nA: {r['answer']}\n\n"

        next_q = generate_interview_question(
            candidate_name=session_data["candidate_name"],
            job_title=session_data["job_title"],
            topic=next_topic,
            q_num=next_q_num,
            q_type=next_q_type,
            transcript=t_str,
            skills=session_data.get("skills", []),
            domain=session_data.get("domain", "")
        )

        from app.database import save_interview_session

        session_data["pending_question"] = next_q
        session_data["pending_topic"]    = next_topic
        session_data["pending_q_type"]   = next_q_type
        session_data["question_issued_at"] = time.time()
        save_interview_session(session_data.get("session_id", data.get("session_id")), session_data)

        return jsonify({
            "success":       True,
            "is_followup":   False,
            "done":          False,
            "next_q":        next_q,
            "next_question": _question_payload(next_q, next_q_num, plan=plan),
            "q_num":         next_q_num,
            "q_type":        next_q_type,
            "topic":         next_topic,
            "evaluation":    evaluation,
            "proctor":       answer_flags,
        })

    @app.route("/api/candidate/interview/finish", methods=["POST"])
    def api_candidate_interview_finish():
        data = request.get_json(silent=True) or {}
        session_data, error = _get_candidate_session(data)
        if error:
            return error
        session_id = data.get("session_id")
        token      = session_data["token"]

        from app.database import delete_interview_session, mark_token_used
        mark_token_used(token)
        delete_interview_session(session_id)

        summary = stop_proctoring(session_id)
        session_data["webcam_log"] = summary.get("events", [])

        answer_flagged = sum(len(r.get("answer_flags", [])) for r in session_data["responses"])
        browser_flagged = len(session_data.get("browser_log", []))
        flagged = len(summary.get("events", [])) + browser_flagged + answer_flagged
        session_data["proctoring_status"] = "PASSED" if flagged < 3 else "SUSPICIOUS"
        session_data["flagged_count"] = flagged

        total_score = sum(r["score"] for r in session_data["responses"])
        max_score   = len(session_data["responses"]) * 10
        score_pct   = round((total_score / max_score) * 100, 1) if max_score else 0.0

        session_data["total_score"] = total_score
        session_data["max_score"]   = max_score
        session_data["percentage"]  = score_pct
        session_data["ended_at"]    = time.time()

        int_output = OUTPUT_FOLDER / "interviews"
        int_output.mkdir(exist_ok=True)

        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', session_data["candidate_name"])
        ts = int(time.time())
        t_path = int_output / f"interview_{safe_name}_{ts}.json"

        with open(t_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=4)

        # Trigger HR notification
        try:
            from app.database import create_hr_notification
            cand_name = session_data.get("candidate_name", "Candidate")
            cand_job = session_data.get("job_title", "Open Position")
            create_hr_notification(
                title=f"Interview Completed: {cand_name}",
                message=f"{cand_name} has completed the interview for {cand_job}. Score: {score_pct}%. Report is ready.",
                candidate_name=cand_name,
                job_title=cand_job,
                notif_type="interview_completed",
                link="/reports",
            )
        except Exception as ne:
            logger.warning("Could not create completion notification: %s", ne)

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
                "total_score":       total_score,
                "max_score":         max_score,
                "percentage":        score_pct,
                "technical_pct":     round((technical_score / technical_max) * 100, 1) if technical_max else 0,
                "behavioral_pct":    round((behavioral_score / behavioral_max) * 100, 1) if behavioral_max else 0,
                "flagged_count":     flagged,
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
            "type":      data.get("type", "BROWSER_FLAG"),
            "detail":    data.get("detail", ""),
            "timestamp": time.time(),
        }
        session_data.setdefault("browser_log", []).append(event)
        from app.database import save_interview_session
        save_interview_session(data.get("session_id"), session_data)
        return jsonify({"success": True, "event": event})

    @app.route("/api/candidate/proctor/analyze-frame", methods=["POST"])
    def api_candidate_proctor_analyze_frame():
        data = request.json or {}
        _, error = _get_candidate_session(data)
        if error:
            return error
        return jsonify({"success": True, "face_count": 1, "flag_count": 0, "flags": []})


def register_hr_interview_routes(app):
    """Register HR-only interview management routes."""
    if "interview" in app.view_functions:
        return

    @app.route("/interview")
    @login_required
    def interview():
        from src.voice_interview import check_microphone, check_tts
        from src.webcam_proctor import check_webcam_available

        tokens = get_all_tokens()

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

    @app.route("/api/generate-interview-links", methods=["POST"])
    @login_required
    def api_generate_interview_links():
        schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
        if not schedule_files:
            return jsonify({"error": "No schedule found. Complete scheduling first."}), 404
        try:
            with open(schedule_files[0], encoding="utf-8") as f:
                sdata = json.load(f)
        except Exception:
            return jsonify({"error": "Corrupted schedule summary"}), 500

        from app.database import get_all_tokens
        existing_tokens = get_all_tokens()
        cand_to_token = {t["candidate_name"]: t for t in existing_tokens}

        host_url = request.host_url
        if "127.0.0.1" in host_url or "localhost" in host_url:
            lan_ip = _get_lan_ip()
            from flask import current_app
            cand_port = current_app.config.get("CANDIDATE_PORT", 5000)
            host_url = f"https://{lan_ip}:{cand_port}/"

        links = []
        for entry in sdata.get("schedule", []):
            if entry.get("status") == "CONFIRMED":
                cand_name = entry["candidate_name"]
                if cand_name in cand_to_token:
                    token_record = cand_to_token[cand_name]
                    token = token_record["token"]
                    used = token_record["used"]
                    token = f"T_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                    cand_ctx = {"candidate_name": cand_name, "source_file": entry["source_file"], "job_title": sdata.get("job_title", "")}
                    resolved_title, _, _ = _resolve_candidate_job_context(cand_ctx)
                    create_interview_token(
                        token=token,
                        candidate_name=cand_name,
                        source_file=entry["source_file"],
                        job_title=resolved_title,
                        rank=entry.get("rank", 0),
                        score=entry.get("score", 0)
                    )
                    used = 0

                links.append({
                    "candidate_name": cand_name,
                    "url": host_url + f"candidate-interview/{token}",
                    "used": used,
                    "email": entry.get("email", "")
                })
        return jsonify({"success": True, "links": links})

    @app.route("/api/send-interview-links", methods=["POST"])
    @login_required
    def api_send_interview_links():
        links_res = api_generate_interview_links().get_json()
        if "error" in links_res:
            return jsonify({"error": links_res["error"]}), 400
        links = links_res.get("links", [])

        import config as cfg
        smtp_host = getattr(cfg, "SMTP_HOST", "").strip()
        smtp_port = int(getattr(cfg, "SMTP_PORT", 587) or 587)
        smtp_email = getattr(cfg, "SMTP_EMAIL", "").strip()
        smtp_password = getattr(cfg, "SMTP_PASSWORD", "").strip()
        hr_name = getattr(cfg, "HR_DISPLAY_NAME", "").strip()
        company = getattr(cfg, "HR_COMPANY", "").strip()

        if not smtp_host or not smtp_email or not smtp_password:
            return jsonify({"error": "SMTP not configured. Go to Settings → Email."}), 400

        schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
        try:
            with open(schedule_files[0], encoding="utf-8") as f:
                sdata = json.load(f)
        except Exception:
            sdata = {}

        job_title = sdata.get("job_title", "Open Position")
        cand_slots = {e.get("candidate_name"): (e.get("selected_slot", "") or (e.get("offered_slots") or [""])[0]) for e in sdata.get("schedule", [])}

        from src.email_sender import send_interview_email
        sent = 0
        failed = 0
        errors = []

        for link_data in links:
            cand_name = link_data["candidate_name"]
            url = link_data["url"]
            email = link_data.get("email", "")

            if not email:
                nlp_path = OUTPUT_FOLDER / "nlp"
                if nlp_path.exists():
                    for nlp_file in nlp_path.glob("*_nlp.json"):
                        try:
                            import json as _json
                            with open(nlp_file, encoding="utf-8") as nf:
                                ndata = _json.load(nf)
                            found_name = ndata.get("personal_info", {}).get("name", "")
                            if found_name and cand_name.lower() in found_name.lower():
                                email = ndata.get("personal_info", {}).get("email", "")
                                break
                        except Exception:
                            continue

            if not email:
                failed += 1
                errors.append(f"{cand_name}: No email found.")
                continue

            slot = cand_slots.get(cand_name, "TBD")

            ok, err = send_interview_email(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_email=smtp_email,
                smtp_password=smtp_password,
                recipient_email=email,
                candidate_name=cand_name,
                job_title=job_title,
                interview_slot=slot,
                hr_name=hr_name,
                company=company,
                interview_url=url,
            )

            if ok:
                sent += 1
            else:
                failed += 1
                errors.append(f"{cand_name}: {err}")

        return jsonify({"success": True, "links": links, "sent": sent, "failed": failed, "errors": errors})

    @app.route("/api/interview-links", methods=["GET"])
    @login_required
    def api_interview_links():
        tokens = get_all_tokens()
        host_url = request.host_url
        if "127.0.0.1" in host_url or "localhost" in host_url:
            lan_ip = _get_lan_ip()
            from flask import current_app
            cand_port = current_app.config.get("CANDIDATE_PORT", 5000)
            host_url = f"https://{lan_ip}:{cand_port}/"

        links = []
        for t in tokens:
            links.append({
                "candidate_name": t["candidate_name"],
                "url": host_url + f"candidate-interview/{t['token']}",
                "used": t["used"]
            })
        return jsonify({"links": links})

    @app.route("/api/interviews/list", methods=["GET"])
    @login_required
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


def register_interview_routes(app):
    """Register all interview routes (candidate + HR)."""
    register_candidate_interview_routes(app)
    register_hr_interview_routes(app)
