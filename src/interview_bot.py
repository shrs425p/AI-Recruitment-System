import json    # JSON I/O for schedule files and transcripts
import re      # Regex — used to sanitise filenames
import time    # time.time() for measuring answer duration (proctoring)
from pathlib import Path       # Cross-platform path handling
from datetime import datetime  # Timestamp for output filenames
import sys
from utils import clean_json_response as clean_json, call_ollama  # AI utilities
from app_paths import data_path

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Folders used to locate input data and save results
SCHEDULING_FOLDER    = data_path("output/scheduling")
NLP_FOLDER           = data_path("output/nlp")
OUTPUT_FOLDER        = data_path("output/interviews")

# Number of questions to ask in each category per candidate
TECHNICAL_QUESTIONS  = 5    # Questions testing domain / coding / technical knowledge
BEHAVIORAL_QUESTIONS = 3    # Questions using STAR format (Situation, Task, Action, Result)

# Maximum allowed time (seconds) per answer before the proctoring flag is raised
ANSWER_TIME_LIMIT    = 120

# ─────────────────────────────────────────────
# HELPER: Call AI model
# ─────────────────────────────────────────────

def call_ai(system_msg: str, user_msg: str, temperature: float = 0.0) -> str:
    """
    Thin wrapper around call_ollama with a fixed token budget of 2048.
    Used internally by all question/evaluation functions in this module.
    """
    return call_ollama(system_msg, user_msg, temperature, num_predict=2048)

# ─────────────────────────────────────────────
# STEP 1: LOAD CONFIRMED CANDIDATES
# ─────────────────────────────────────────────

def load_scheduled_candidates(scheduling_folder: Path):
    """Load latest schedule and return only CONFIRMED candidates."""

    schedule_files = sorted(scheduling_folder.glob("schedule_*.json"), reverse=True)

    if not schedule_files:
        print(f"[ERROR] No schedule file found in '{scheduling_folder}'.")
        print("  Run scheduling.py first.")
        return [], ""

    latest = schedule_files[0]
    print(f"> Loading schedule from: {latest.name}")

    with open(latest, "r", encoding="utf-8") as f:
        data = json.load(f)

    confirmed = [c for c in data.get("schedule", []) if c["status"] == "CONFIRMED"]
    job_title = data.get("job_title", "Open Position")

    print(f"> Confirmed candidates  : {len(confirmed)}")
    return confirmed, job_title

# ─────────────────────────────────────────────
# STEP 2: LOAD CANDIDATE NLP DATA
# ─────────────────────────────────────────────

def load_candidate_nlp(source_file: str, nlp_folder: Path) -> dict:
    """
    Load the NLP JSON for one candidate so the question generator can
    create personalised, domain-specific questions based on that candidate's
    actual skills, experience, and project history.

    Returns {} if the file does not exist (interview can still continue
    with generic questions).
    """
    nlp_file = nlp_folder / f"{source_file}.json"
    if not nlp_file.exists():
        return {}  # No NLP data — questions will be generic
    with open(nlp_file, "r", encoding="utf-8") as f:
        return json.load(f)

# ─────────────────────────────────────────────
# STEP 3: GENERATE PERSONALIZED QUESTIONS
# ─────────────────────────────────────────────

def generate_questions(candidate_data: dict, job_title: str) -> dict:
    """Generate personalized technical + behavioral questions using AI."""

    system_msg = "You are an expert HR interviewer. Always return valid JSON only."

    user_msg = (
        f"Generate exactly {TECHNICAL_QUESTIONS} technical and {BEHAVIORAL_QUESTIONS} behavioral "
        f"interview questions for a candidate applying for: {job_title}\n\n"
        f"CANDIDATE PROFILE:\n{json.dumps(candidate_data, indent=2)}\n\n"
        f"RULES:\n"
        f"- Technical questions must be specific to candidate domain, skills, and experience.\n"
        f"- Behavioral questions must follow STAR format.\n"
        f"- Vary difficulty: easy, medium, hard.\n"
        f"- Return ONLY valid JSON, no explanation, no markdown.\n\n"
        f"Return EXACTLY this JSON:\n"
        f'{{"technical": [{{"id": 1, "question": "", "difficulty": "easy/medium/hard", "topic": ""}}],'
        f'"behavioral": [{{"id": 1, "question": "", "type": "behavioral"}}]}}'
    )

    try:
        raw = call_ai(system_msg, user_msg, temperature=0.3)
        if not raw:
            return {"technical": [], "behavioral": []}
        return clean_json(raw)
    except Exception as e:
        print(f"  [ERROR] Question generation failed: {e}")
        return {"technical": [], "behavioral": []}

# ─────────────────────────────────────────────
# STEP 4: EVALUATE CANDIDATE ANSWER
# ─────────────────────────────────────────────

def evaluate_answer(question: str, answer: str, job_title: str, domain: str) -> dict:
    """Evaluate candidate answer using AI and return score + feedback."""

    system_msg = "You are a precise HR evaluator. Always return valid JSON only."

    user_msg = (
        f"Evaluate this interview answer objectively.\n\n"
        f"Job Title : {job_title}\n"
        f"Domain    : {domain}\n"
        f"Question  : {question}\n"
        f"Answer    : {answer}\n\n"
        f"Score on these criteria (STRICTNESS LEVEL: 4 out of 5):\n"
        f"- relevance   : 0-3 (Does the answer directly address the question? 0 for irrelevant or non-answers)\n"
        f"- depth       : 0-3 (Does it show strong technical/domain understanding? 0 for superficial/blank)\n"
        f"- clarity     : 0-2 (Is the answer structured and professional? 0 for fragmented/unclear)\n"
        f"- correctness : 0-2 (Is it technically accurate? 0 if fundamentally wrong)\n\n"
        f"If the candidate did not answer the question, or gave an irrelevant/gibberish response, give 0 on all.\n"
        f"Return ONLY valid JSON:\n"
        f'{{"relevance": 0, "depth": 0, "clarity": 0, "correctness": 0, "total": 0, '
        f'"feedback": "", "strong_points": [], "weak_points": []}}'
    )

    try:
        raw = call_ai(system_msg, user_msg, temperature=0.0)
        if not raw:
            raise ValueError("Empty response from AI")

        result = clean_json(raw)

        # Safety: recalculate total and clamp each score to max
        result["relevance"]   = min(max(result.get("relevance",   0), 0), 3)
        result["depth"]       = min(max(result.get("depth",       0), 0), 3)
        result["clarity"]     = min(max(result.get("clarity",     0), 0), 2)
        result["correctness"] = min(max(result.get("correctness", 0), 0), 2)
        result["total"]       = (
            result["relevance"] + result["depth"] +
            result["clarity"]   + result["correctness"]
        )
        return result

    except Exception as e:
        print(f"  [ERROR] Evaluation failed: {e}")
        return {
            "relevance": 0, "depth": 0, "clarity": 0,
            "correctness": 0, "total": 0,
            "feedback": "Evaluation failed.", "strong_points": [], "weak_points": []
        }

# ─────────────────────────────────────────────
# STEP 5: PROCTORING (GUI-less basic checks)
# ─────────────────────────────────────────────

def proctor_check(question_num: int, answer: str, time_taken: float) -> dict:
    """
    Apply basic rule-based proctoring checks on a single answer.

    Flags raised:
      VERY_SHORT_ANSWER          — fewer than 10 characters (likely skipped)
      SUSPICIOUSLY_FAST_ANSWER   — >100 chars typed in under 5 seconds (copy-paste?)
      EXCESSIVELY_LONG_ANSWER    — more than 2000 characters (unlikely genuine)
      SKIPPED_QUESTION           — answer is blank, 'skip', or 's'
      TIME_LIMIT_EXCEEDED        — took longer than ANSWER_TIME_LIMIT seconds

    For full webcam-based proctoring, see webcam_proctor.py which runs
    face detection in a background thread during GUI interviews.

    Returns:
      dict with 'flagged' bool and 'flags' list for the interview transcript.
    """
    flags = []

    if len(answer.strip()) < 10:
        flags.append("VERY_SHORT_ANSWER")

    # A long answer typed in < 5s is suspicious — probably pasted from elsewhere
    if time_taken < 5 and len(answer.strip()) > 100:
        flags.append("SUSPICIOUSLY_FAST_ANSWER")

    if len(answer.strip()) > 2000:
        flags.append("EXCESSIVELY_LONG_ANSWER")

    # Explicit skip commands — candidate chose not to answer
    if answer.strip().lower() in ["", "skip", "s"]:
        flags.append("SKIPPED_QUESTION")

    # Time limit enforcement — answer took longer than the allowed seconds
    if time_taken > ANSWER_TIME_LIMIT:
        flags.append("TIME_LIMIT_EXCEEDED")

    return {
        "question_num":       question_num,
        "time_taken_seconds": round(time_taken, 1),
        "flags":              flags,
        "flagged":            len(flags) > 0  # True if any flag was raised
    }

# ─────────────────────────────────────────────
# STEP 6: CONDUCT INTERVIEW
# ─────────────────────────────────────────────

def conduct_interview(candidate: dict, questions: dict, job_title: str, candidate_data: dict) -> dict:
    """
    Conduct interview via terminal input/output.
    GUI VERSION: Replace input/print with voice/video interface.
    """
    name        = candidate.get("candidate_name", "Candidate")
    domain      = candidate_data.get("domain", "General")
    responses   = []
    proctor_log = []

    all_questions = (
        [("TECHNICAL",  q) for q in questions.get("technical",  [])] +
        [("BEHAVIORAL", q) for q in questions.get("behavioral", [])]
    )

    total_q = len(all_questions)

    print(f"\n{'='*55}")
    print(f"  INTERVIEW — {name}")
    print(f"{'='*55}")
    print(f"  Job Title    : {job_title}")
    print(f"  Domain       : {domain}")
    print(f"  Questions    : {total_q} total")
    print(f"  Time Limit   : {ANSWER_TIME_LIMIT}s per question")
    print(f"\n  Instructions:")
    print(f"  - Read each question carefully.")
    print(f"  - Type your answer and press Enter.")
    print(f"  - Type 'SKIP' to skip a question.")
    print(f"{'='*55}")
    input("\n  Press Enter to begin...\n")

    for q_num, (q_type, q_data) in enumerate(all_questions, start=1):
        q_text = q_data.get("question", "")
        topic  = q_data.get("topic", q_data.get("type", ""))

        print(f"\n{'─'*55}")
        print(f"  Q{q_num}/{total_q}  [{q_type}]  {topic}")
        print(f"{'─'*55}")
        print(f"\n  {q_text}\n")

        start_time = time.time()
        answer     = input("  Your Answer: ").strip()
        time_taken = time.time() - start_time

        # Proctoring
        proctor = proctor_check(q_num, answer, time_taken)
        proctor_log.append(proctor)
        if proctor["flagged"]:
            print(f"  [PROCTOR] {', '.join(proctor['flags'])}")

        # Evaluate
        print(f"  Evaluating...", end=" ", flush=True)
        evaluation = evaluate_answer(q_text, answer, job_title, domain)
        print(f"Score: {evaluation['total']}/10  — {evaluation.get('feedback', '')}")

        responses.append({
            "question_num": q_num,
            "type":         q_type,
            "topic":        topic,
            "question":     q_text,
            "answer":       answer,
            "time_taken":   round(time_taken, 1),
            "score":        evaluation.get("total", 0),
            "evaluation":   evaluation,
            "proctor":      proctor
        })

    # Final score calculation
    total_score   = sum(r["evaluation"].get("total", 0) for r in responses)
    max_score     = total_q * 10
    percentage    = round((total_score / max_score) * 100, 1) if max_score > 0 else 0
    flagged_count = sum(1 for p in proctor_log if p["flagged"])

    # Technical vs Behavioral breakdown
    tech_responses = [r for r in responses if r["type"] == "TECHNICAL"]
    beh_responses  = [r for r in responses if r["type"] == "BEHAVIORAL"]
    tech_score     = sum(r["score"] for r in tech_responses)
    beh_score      = sum(r["score"] for r in beh_responses)
    tech_max       = len(tech_responses) * 10
    beh_max        = len(beh_responses)  * 10

    print(f"\n{'='*55}")
    print(f"  INTERVIEW COMPLETE")
    print(f"  Total Score       : {total_score}/{max_score} ({percentage}%)")
    print(f"  Technical Score   : {tech_score}/{tech_max}")
    print(f"  Behavioral Score  : {beh_score}/{beh_max}")
    print(f"  Proctor Flags     : {flagged_count}")
    print(f"{'='*55}\n")

    return {
        "candidate_name":    name,
        "source_file":       candidate.get("source_file", ""),
        "rank":              candidate.get("rank", 0),
        "ranking_score":     candidate.get("score", 0),
        "job_title":         job_title,
        "domain":            domain,
        "interview_date":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "responses":         responses,
        "proctor_log":       proctor_log,
        "total_score":       total_score,
        "max_score":         max_score,
        "percentage":        percentage,
        "technical_score":   tech_score,
        "technical_max":     tech_max,
        "technical_pct":     round((tech_score / tech_max * 100), 1) if tech_max > 0 else 0,
        "behavioral_score":  beh_score,
        "behavioral_max":    beh_max,
        "behavioral_pct":    round((beh_score / beh_max * 100), 1) if beh_max > 0 else 0,
        "flagged_count":     flagged_count,
        "proctoring_status": "FLAGGED" if flagged_count > 2 else "CLEAN"
    }

# ─────────────────────────────────────────────
# STEP 7: SAVE INTERVIEW TRANSCRIPT
# ─────────────────────────────────────────────

def save_interview_result(result: dict, output_path: Path):
    """
    Persist the completed interview in two formats:
      JSON — used by report_generator.py to produce AI-written reports
      TXT  — human-readable transcript that HR can open in any text editor

    Both filenames include a timestamp so multiple interviews for the same
    candidate (re-takes) don't overwrite each other.
    """
    # Sanitise name to create a safe filename (replace spaces/slashes with underscores)
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', result.get("candidate_name", "unknown"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON transcript (for report generation stage)
    json_file = output_path / f"interview_{safe_name}_{timestamp}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    # TXT transcript (for HR reading)
    txt_file = output_path / f"interview_{safe_name}_{timestamp}.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("          INTERVIEW TRANSCRIPT\n")
        f.write("=" * 60 + "\n")
        f.write(f"Candidate       : {result['candidate_name']} ({result['source_file']})\n")
        f.write(f"Job Title       : {result['job_title']}\n")
        f.write(f"Date            : {result['interview_date']}\n")
        f.write(f"Ranking Score   : {result['ranking_score']}/100\n")
        f.write(f"Interview Score : {result['total_score']}/{result['max_score']} ({result['percentage']}%)\n")
        f.write(f"Technical Score : {result['technical_score']}/{result['technical_max']} ({result['technical_pct']}%)\n")
        f.write(f"Behavioral Score: {result['behavioral_score']}/{result['behavioral_max']} ({result['behavioral_pct']}%)\n")
        f.write(f"Proctoring      : {result['proctoring_status']} ({result['flagged_count']} flags)\n")
        f.write("=" * 60 + "\n\n")

        for r in result["responses"]:
            f.write(f"Q{r['question_num']} [{r['type']}] — {r['topic']}\n")
            f.write(f"{'─'*40}\n")
            f.write(f"Question  : {r['question']}\n")
            f.write(f"Answer    : {r['answer']}\n")
            f.write(f"Score     : {r['evaluation'].get('total', 0)}/10\n")
            f.write(f"Feedback  : {r['evaluation'].get('feedback', '')}\n")

            strong = r["evaluation"].get("strong_points", [])
            weak   = r["evaluation"].get("weak_points",   [])
            if strong:
                f.write(f"Strengths : {', '.join(str(s) for s in strong)}\n")
            if weak:
                f.write(f"Gaps      : {', '.join(str(w) for w in weak)}\n")
            if r["proctor"]["flagged"]:
                f.write(f"FLAGS     : {', '.join(r['proctor']['flags'])}\n")
            f.write(f"Time Taken: {r['time_taken']}s\n\n")

    print(f"  Saved: {json_file.name}")
    print(f"  Saved: {txt_file.name}")

# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def run_interview_bot():
    output_path     = Path(OUTPUT_FOLDER)
    output_path.mkdir(parents=True, exist_ok=True)
    scheduling_path = Path(SCHEDULING_FOLDER)
    nlp_path        = Path(NLP_FOLDER)

    print("=" * 55)
    print("   AI INTERVIEW BOT — LAYER 1 (TEXT MODE)")
    print("=" * 55)

    # Load confirmed candidates
    candidates, job_title = load_scheduled_candidates(scheduling_path)
    if not candidates:
        return

    print(f"> Job Title : {job_title}")
    print(f"> Starting  : {len(candidates)} interviews\n")

    for i, candidate in enumerate(candidates, start=1):
        name = candidate.get("candidate_name", "Unknown")

        print(f"\n{'='*55}")
        print(f"  CANDIDATE {i}/{len(candidates)}: {name}")
        print(f"{'='*55}")

        # Load NLP data for context
        candidate_data = load_candidate_nlp(candidate.get("source_file", ""), nlp_path)

        # Generate questions
        print(f"> Generating questions...", end=" ", flush=True)
        questions = generate_questions(candidate_data, job_title)

        tech_q = len(questions.get("technical",  []))
        behv_q = len(questions.get("behavioral", []))

        if tech_q == 0 and behv_q == 0:
            print("Failed! Skipping.")
            continue

        print(f"Done! ({tech_q} technical + {behv_q} behavioral)")

        # Conduct interview
        result = conduct_interview(candidate, questions, job_title, candidate_data)

        # Save transcript
        print(f"> Saving transcript...")
        save_interview_result(result, output_path)

        # Continue prompt
        if i < len(candidates):
            cont = input(f"\n> Next candidate? (Enter=Yes / 'STOP'=Stop): ").strip()
            if cont.upper() == "STOP":
                print("> Session stopped.")
                break

    print(f"\n{'='*55}")
    print(f"  ALL INTERVIEWS COMPLETE")
    print(f"  Transcripts saved to: {OUTPUT_FOLDER}")
    print(f"{'='*55}")


def generate_interview_question(candidate_name: str, job_title: str, topic: str, q_num: int, q_type: str, transcript: str = "") -> str:
    """Generate a single personalized interview question based on candidate, job title, topic, and transcript history."""
    system_msg = "You are a professional HR interviewer. Return ONLY the question text itself. Do not include any intro, outro, greeting, or conversational filler."
    
    prompt = (
        f"Candidate: {candidate_name}\n"
        f"Job Title: {job_title}\n"
        f"Question Number: {q_num}\n"
        f"Type: {q_type}\n"
        f"Topic: {topic}\n"
    )
    if transcript:
        prompt += f"\nConversation History so far:\n{transcript}\n"
        prompt += "\nBased on the history and the current topic, ask the next logical, deep, and engaging interview question."
    else:
        prompt += f"\nAsk an introductory question testing their alignment and interest in the {job_title} role, specializing in {topic}."

    try:
        from utils import call_ollama
        raw = call_ollama(system_msg, prompt, temperature=0.5, num_predict=512)
        if raw:
            # Strip extra quotes or prefixes if the AI generated them
            cleaned = raw.strip().strip('"').strip("'").strip()
            # If the AI put a prefix like "Q: " or "Question: ", strip it
            cleaned = re.sub(r'^(Q|Question\s*\d*)\s*:\s*', '', cleaned, flags=re.IGNORECASE)
            return cleaned.strip()
    except Exception as e:
        print(f"  [ERROR] Single question generation failed: {e}")
        
    # Fallback questions
    if q_num == 1:
        return f"Welcome, {candidate_name}. To start off, please introduce yourself and tell us what interests you most about the {job_title} position."
    elif q_type == "TECHNICAL":
        return f"Can you explain a complex technical challenge you faced when working with {topic}, and how you solved it?"
    else:
        return f"Can you tell me about a time when you had to work on a team to solve a difficult problem? What was your role and the outcome?"


if __name__ == "__main__":
    run_interview_bot()