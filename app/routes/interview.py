import time
import json
import uuid
import re
from flask import request, jsonify, render_template, session
from app.core import OUTPUT_FOLDER
from app.database import get_interview_token, create_interview_token, get_all_tokens
from app.utils import login_required
from interview_bot import generate_interview_question
from webcam_proctor import get_proctor_status, stop_proctoring, start_proctoring as start_proctoring_session
import voice_interview

# Global state for candidate interview sessions
interview_session = {}
candidate_tokens = {}

def _save_sessions():
    pass # In-memory session tracking

def register_interview_routes(app):
    @app.route("/interview")
    @login_required
    def interview():
        tokens = get_all_tokens()
        return render_template("interview.html", tokens=tokens)

    @app.route("/rules")
    @login_required
    def rules():
        return render_template("rules.html")

    @app.route("/candidate-interview/<token>")
    def candidate_interview(token):
        token_data = get_interview_token(token)
        if not token_data or token_data.get("used") == 1:
            return render_template("login.html", error="Invalid or expired interview token.")
        
        return render_template("candidate_interview.html", 
                               token=token, 
                               candidate_name=token_data["candidate_name"],
                               job_title=token_data["job_title"])

    @app.route("/api/candidate/interview/start", methods=["POST"])
    def api_candidate_interview_start():
        data  = request.json
        token = data.get("token")
        
        token_data = get_interview_token(token)
        if not token_data or token_data.get("used") == 1:
            return jsonify({"error": "Unauthorized"}), 401

        session_id = f"S_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        interview_session[session_id] = {
            "token":          token,
            "candidate_name": token_data["candidate_name"],
            "source_file":    token_data["source_file"],
            "job_title":      token_data["job_title"],
            "ranking_score":  token_data["score"],
            "responses":      [],
            "started_at":     time.time(),
            "webcam_log":     []
        }
        
        start_proctoring_session(session_id)
        
        first_q = generate_interview_question(
            candidate_name=token_data["candidate_name"],
            job_title=token_data["job_title"],
            topic="Introduction",
            q_num=1,
            q_type="TECHNICAL",
            transcript=""
        )

        return jsonify({
            "success":    True,
            "session_id": session_id,
            "first_q":    first_q
        })

    @app.route("/api/candidate/interview/answer", methods=["POST"])
    def api_candidate_interview_answer():
        data           = request.json
        session_id     = data.get("session_id")
        answer         = data.get("answer", "").strip()
        question       = data.get("question", "").strip()
        topic          = data.get("topic", "Coding").strip()
        q_type         = data.get("type", "TECHNICAL").strip()
        q_num          = int(data.get("question_num", 1))
        time_taken     = int(data.get("time_taken", 30))

        if session_id not in interview_session:
            return jsonify({"error": "Session expired or invalid"}), 404

        session_data = interview_session[session_id]
        
        # In a real app we'd score the response with LLM
        score = 8.0 # Simulated
        
        session_data["responses"].append({
            "question_num": q_num,
            "type":         q_type,
            "topic":        topic,
            "question":     question,
            "answer":       answer,
            "score":        score,
            "time_taken":   time_taken
        })

        if q_num >= 5:
            return jsonify({"success": True, "done": True})

        next_q_num  = q_num + 1
        next_q_type = "BEHAVIORAL" if next_q_num > 3 else "TECHNICAL"
        next_topic  = "Problem Solving" if next_q_num == 2 else "System Design" if next_q_num == 3 else "Teamwork" if next_q_num == 4 else "Conflict Resolution"
        
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

        return jsonify({
            "success":    True,
            "done":       False,
            "next_q":     next_q,
            "q_num":      next_q_num,
            "q_type":     next_q_type,
            "topic":      next_topic
        })

    @app.route("/api/candidate/interview/finish", methods=["POST"])
    def api_candidate_interview_finish():
        data       = request.json
        session_id = data.get("session_id")
        
        if session_id not in interview_session:
            return jsonify({"error": "Session invalid"}), 404

        session_data = interview_session[session_id]
        token        = session_data["token"]
        
        from app.database import mark_token_used
        mark_token_used(token)

        # Stop proctoring and fetch proctor summary
        summary = stop_proctoring(session_id)
        session_data["webcam_log"] = summary.get("events", [])
        
        flagged = len(summary.get("events", []))
        session_data["proctoring_status"] = "PASSED" if flagged < 3 else "SUSPICIOUS"

        total_score = sum(r["score"] for r in session_data["responses"])
        score_pct   = round((total_score / 50) * 100, 1) if session_data["responses"] else 0.0

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

        return jsonify({"success": True})

    @app.route("/api/candidate/proctor/browser_flag", methods=["POST"])
    def api_candidate_proctor_browser_flag():
        return jsonify({"success": True})

    @app.route("/api/candidate/proctor/analyze-frame", methods=["POST"])
    def api_candidate_proctor_analyze_frame():
        import base64
        data = request.json
        frame_b64 = data.get("frame", "")
        session_id = data.get("session_id", "")
        
        # Process face detection frame
        return jsonify({"success": True, "faces": 1, "flagged": False})

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

        from app.database import delete_all_tokens, create_interview_token
        delete_all_tokens()
        
        created = []
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
                created.append(entry["candidate_name"])
        return jsonify({"success": True, "created": created})

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
            except Exception: pass
        return jsonify(list_ints)
