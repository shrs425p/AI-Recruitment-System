import json  # JSON serialisation for report files
import re  # Regex — sanitise filenames
from datetime import datetime  # Timestamps for file names
from pathlib import Path  # Cross-platform path handling

from app.utils import call_ollama
from app.utils import clean_json_response as clean_json  # AI utilities

from app.app_paths import data_path

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Folder where interview transcript JSON files are stored
INTERVIEWS_FOLDER = data_path("output/interviews")

# Folder where generated reports and summary files are saved
OUTPUT_FOLDER     = data_path("output/reports")

# ─────────────────────────────────────────────
# HELPER: Call AI model
# ─────────────────────────────────────────────

def call_ai(system_msg: str, user_msg: str) -> str:
    """
    Wrapper that calls the Ollama model with temperature=0.0 (deterministic)
    and a 4096-token budget to allow detailed reports.
    """
    return call_ollama(system_msg, user_msg, 0.0, 4096)

# ─────────────────────────────────────────────
# STEP 1: LOAD INTERVIEW TRANSCRIPTS
# ─────────────────────────────────────────────

def load_interview_transcripts(interviews_folder: Path) -> list:
    """
    Scan the interviews/ folder and load all interview_*.json files.

    Each file is a complete interview transcript saved by interview_bot.py.
    A '_source_file' key (the filename) is added to each dict so the report
    can reference back to the original interview file.

    Returns [] if no transcripts are found (reports stage cannot proceed).
    """
    json_files = sorted(interviews_folder.glob("interview_*.json"))  # sorted alphabetically

    if not json_files:
        print(f"[ERROR] No interview transcripts found in '{interviews_folder}'.")
        print("  Run interview_bot.py first.")
        return []

    print(f"> Found {len(json_files)} interview transcript(s).")
    transcripts = []

    for jf in json_files:
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
            data["_source_file"] = jf.name  # track which file this came from
            transcripts.append(data)
        except Exception as e:
            print(f"  [WARNING] Could not load {jf.name}: {e}")

    return transcripts

# ─────────────────────────────────────────────
# STEP 2: GENERATE AI REPORT FOR ONE CANDIDATE
# ─────────────────────────────────────────────

def generate_ai_report(transcript: dict) -> dict:
    """
    Send the interview transcript to the AI model and return a structured
    HR assessment report.

    The prompt includes:
      - Candidate name, job title, domain
      - All scores (ranking, interview, technical, behavioural)
      - Proctoring status and flag count
      - Full Q&A with per-question feedback

    The AI returns a JSON with:
      overall_summary, technical_assessment, behavioral_assessment,
      key_strengths, key_gaps, proctoring_remarks, risk_level,
      combined_score, hire_recommendation, hire_justification,
      suggested_next_steps

    Returns {} if the AI call fails (caller should skip that candidate).
    """

    system_msg = "You are a senior HR analyst. Always return valid JSON only."

    # Build a condensed Q&A summary — the AI doesn't need the full raw data
    qa_summary = []
    for r in transcript.get("responses", []):
        qa_summary.append({
            "question":   r.get("question", ""),
            "answer":     r.get("answer", ""),
            "type":       r.get("type", ""),
            "topic":      r.get("topic", ""),
            "score":      r.get("score", 0),
            "feedback":   r.get("evaluation", {}).get("feedback", ""),
            "weak_points": r.get("evaluation", {}).get("weak_points", []),
            "strong_points": r.get("evaluation", {}).get("strong_points", [])
        })

    user_msg = (
        f"Analyze this interview transcript and generate a comprehensive HR report.\n\n"
        f"CANDIDATE     : {transcript.get('candidate_name', 'Unknown')}\n"
        f"JOB TITLE     : {transcript.get('job_title', 'Unknown')}\n"
        f"DOMAIN        : {transcript.get('domain', 'Unknown')}\n"
        f"RANKING SCORE : {transcript.get('ranking_score', 0)}/100\n"
        f"INTERVIEW SCORE: {transcript.get('total_score', 0)}/{transcript.get('max_score', 0)} "
        f"({transcript.get('percentage', 0)}%)\n"
        f"TECHNICAL SCORE: {transcript.get('technical_score', 0)}/{transcript.get('technical_max', 0)} "
        f"({transcript.get('technical_pct', 0)}%)\n"
        f"BEHAVIORAL SCORE: {transcript.get('behavioral_score', 0)}/{transcript.get('behavioral_max', 0)} "
        f"({transcript.get('behavioral_pct', 0)}%)\n"
        f"PROCTORING    : {transcript.get('proctoring_status', 'UNKNOWN')} "
        f"({transcript.get('flagged_count', 0)} flags)\n\n"
        f"Q&A RESPONSES:\n{json.dumps(qa_summary, indent=2)}\n\n"
        f"Based on the above, generate a detailed HR report. Return ONLY valid JSON:\n"
        f'{{'
        f'"overall_summary": "",'
        f'"technical_assessment": "",'
        f'"behavioral_assessment": "",'
        f'"key_strengths": [],'
        f'"key_gaps": [],'
        f'"proctoring_remarks": "",'
        f'"risk_level": "LOW/MEDIUM/HIGH",'
        f'"combined_score": 0,'
        f'"combined_score_explanation": "",'
        f'"hire_recommendation": "STRONGLY RECOMMEND/RECOMMEND/NEUTRAL/NOT RECOMMEND",'
        f'"hire_justification": "",'
        f'"suggested_next_steps": []'
        f'}}'
    )

    raw = call_ai(system_msg, user_msg)
    if not raw:
        return {}

    result = clean_json(raw)
    # clean_json returns {} on parse failure; empty dict is truthy so check explicitly
    return result if result else {}

# ─────────────────────────────────────────────
# STEP 3: CALCULATE COMBINED SCORE
# ─────────────────────────────────────────────

def calculate_combined_score(transcript: dict) -> float:
    """
    Compute the final combined score used to rank candidates after interviews.

    Formula:
      combined = (ranking_score × 0.40) + (interview_percentage × 0.60)

    Rationale:
      - Resume ranking (40%) rewards candidates with strong backgrounds.
      - Interview performance (60%) is weighted higher because it reflects
        how the candidate actually thinks, communicates, and solves problems.
    """
    ranking_score   = transcript.get("ranking_score",  0)  # 0–100 from ranking_engine
    interview_pct   = transcript.get("percentage",     0)  # 0–100% from interview_bot

    combined = (ranking_score * 0.40) + (interview_pct * 0.60)
    return round(combined, 1)  # round to 1 decimal place for display

# ─────────────────────────────────────────────
# STEP 4: SAVE REPORT AS TXT (HR readable)
# ─────────────────────────────────────────────

def save_report_txt(transcript: dict, ai_report: dict, combined_score: float, output_path: Path):
    """Save comprehensive HR report as human-readable TXT."""

    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', transcript.get("candidate_name", "unknown"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_file  = output_path / f"report_{safe_name}_{timestamp}.txt"

    output_path.mkdir(parents=True, exist_ok=True)
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("=" * 65 + "\n")
        f.write("          POST-INTERVIEW EVALUATION REPORT\n")
        f.write("=" * 65 + "\n")
        f.write(f"Generated       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("Fairness Audit  : Scoring based on skills/experience only. Name, gender, age NOT used.\n")
        f.write(f"Candidate       : {transcript.get('candidate_name', 'N/A')} ({transcript.get('source_file', '')})\n")
        f.write(f"Job Title       : {transcript.get('job_title', 'N/A')}\n")
        f.write(f"Domain          : {transcript.get('domain', 'N/A')}\n")
        f.write(f"Interview Date  : {transcript.get('interview_date', 'N/A')}\n")
        f.write("=" * 65 + "\n\n")

        # ── Score Summary ──
        f.write("SCORE SUMMARY\n")
        f.write("─" * 40 + "\n")
        f.write(f"  Resume Ranking Score  : {transcript.get('ranking_score', 0)}/100\n")
        f.write(f"  Interview Score       : {transcript.get('total_score', 0)}/{transcript.get('max_score', 0)} ({transcript.get('percentage', 0)}%)\n")
        f.write(f"    Technical           : {transcript.get('technical_score', 0)}/{transcript.get('technical_max', 0)} ({transcript.get('technical_pct', 0)}%)\n")
        f.write(f"    Behavioral          : {transcript.get('behavioral_score', 0)}/{transcript.get('behavioral_max', 0)} ({transcript.get('behavioral_pct', 0)}%)\n")
        f.write(f"  Combined Score        : {combined_score}/100  (40% Resume + 60% Interview)\n")
        f.write(f"  Proctoring Status     : {transcript.get('proctoring_status', 'N/A')} ({transcript.get('flagged_count', 0)} flag(s))\n\n")

        # ── AI Analysis ──
        f.write("OVERALL SUMMARY\n")
        f.write("─" * 40 + "\n")
        f.write(f"  {ai_report.get('overall_summary', 'N/A')}\n\n")

        f.write("TECHNICAL ASSESSMENT\n")
        f.write("─" * 40 + "\n")
        f.write(f"  {ai_report.get('technical_assessment', 'N/A')}\n\n")

        f.write("BEHAVIORAL ASSESSMENT\n")
        f.write("─" * 40 + "\n")
        f.write(f"  {ai_report.get('behavioral_assessment', 'N/A')}\n\n")

        # ── Strengths ──
        strengths = ai_report.get("key_strengths", [])
        if strengths:
            f.write("KEY STRENGTHS\n")
            f.write("─" * 40 + "\n")
            for s in strengths:
                f.write(f"  + {s}\n")
            f.write("\n")

        # ── Gaps ──
        gaps = ai_report.get("key_gaps", [])
        if gaps:
            f.write("KEY GAPS\n")
            f.write("─" * 40 + "\n")
            for g in gaps:
                f.write(f"  - {g}\n")
            f.write("\n")

        # ── Proctoring ──
        f.write("PROCTORING REMARKS\n")
        f.write("─" * 40 + "\n")
        f.write(f"  {ai_report.get('proctoring_remarks', 'N/A')}\n\n")

        # ── Hire Recommendation ──
        f.write("=" * 65 + "\n")
        f.write("  HIRE RECOMMENDATION\n")
        f.write("=" * 65 + "\n")
        f.write(f"  Decision      : {ai_report.get('hire_recommendation', 'N/A')}\n")
        f.write(f"  Risk Level    : {ai_report.get('risk_level', 'N/A')}\n")
        f.write(f"  Combined Score: {combined_score}/100\n\n")
        f.write(f"  Justification:\n  {ai_report.get('hire_justification', 'N/A')}\n\n")

        # ── Next Steps ──
        next_steps = ai_report.get("suggested_next_steps", [])
        if next_steps:
            f.write("SUGGESTED NEXT STEPS\n")
            f.write("─" * 40 + "\n")
            for idx, step in enumerate(next_steps, start=1):
                f.write(f"  {idx}. {step}\n")
            f.write("\n")

        # ── Q&A Transcript ──
        f.write("=" * 65 + "\n")
        f.write("  DETAILED Q&A TRANSCRIPT\n")
        f.write("=" * 65 + "\n\n")

        for r in transcript.get("responses", []):
            f.write(f"Q{r['question_num']} [{r['type']}] — {r.get('topic', '')}\n")
            f.write("─" * 40 + "\n")
            f.write(f"  Question  : {r.get('question', '')}\n")
            f.write(f"  Answer    : {r.get('answer', '')}\n")
            f.write(f"  Score     : {r.get('score', 0)}/10\n")
            f.write(f"  Feedback  : {r.get('evaluation', {}).get('feedback', '')}\n")
            if r.get("proctor", {}).get("flagged"):
                f.write(f"  FLAGS     : {', '.join(r['proctor']['flags'])}\n")
            f.write(f"  Time      : {r.get('time_taken', 0)}s\n\n")

    print(f"  Report TXT saved: {txt_file.name}")
    return txt_file

# ─────────────────────────────────────────────
# STEP 5: SAVE REPORT AS JSON (machine readable)
# ─────────────────────────────────────────────

def save_report_json(transcript: dict, ai_report: dict, combined_score: float, output_path: Path):
    """Save full report as JSON for downstream use or GUI display."""

    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', transcript.get("candidate_name", "unknown"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = output_path / f"report_{safe_name}_{timestamp}.json"

    report = {
        "generated_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "candidate_name":    transcript.get("candidate_name", "Unknown"),
        "source_file":       transcript.get("source_file", ""),
        "job_title":         transcript.get("job_title", ""),
        "domain":            transcript.get("domain", ""),
        "interview_date":    transcript.get("interview_date", ""),
        "scores": {
            "ranking_score":     transcript.get("ranking_score", 0),
            "interview_score":   transcript.get("total_score", 0),
            "interview_max":     transcript.get("max_score", 0),
            "interview_pct":     transcript.get("percentage", 0),
            "technical_score":   transcript.get("technical_score", 0),
            "technical_max":     transcript.get("technical_max", 0),
            "technical_pct":     transcript.get("technical_pct", 0),
            "behavioral_score":  transcript.get("behavioral_score", 0),
            "behavioral_max":    transcript.get("behavioral_max", 0),
            "behavioral_pct":    transcript.get("behavioral_pct", 0),
            "combined_score":    combined_score,
        },
        "proctoring": {
            "status":       transcript.get("proctoring_status", "UNKNOWN"),
            "flagged_count": transcript.get("flagged_count", 0),
            "log":          transcript.get("proctor_log", [])
        },
        "ai_report":   ai_report,
        "responses":   transcript.get("responses", [])
    }

    output_path.mkdir(parents=True, exist_ok=True)
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    print(f"  Report JSON saved: {json_file.name}")

# ─────────────────────────────────────────────
# STEP 6: SAVE FINAL SUMMARY LEADERBOARD
# ─────────────────────────────────────────────

def save_final_summary(all_reports: list, output_path: Path):
    """Save a final summary of all candidates ranked by combined score."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_file  = output_path / f"final_summary_{timestamp}.txt"
    json_file = output_path / f"final_summary_{timestamp}.json"

    # Sort by combined score
    sorted_reports = sorted(all_reports, key=lambda x: x["combined_score"], reverse=True)

    # Save TXT summary
    output_path.mkdir(parents=True, exist_ok=True)
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("=" * 65 + "\n")
        f.write("        FINAL HIRING DECISION SUMMARY\n")
        f.write("=" * 65 + "\n")
        f.write(f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Candidates Interviewed : {len(sorted_reports)}\n")
        f.write("=" * 65 + "\n\n")

        for rank, r in enumerate(sorted_reports, start=1):
            f.write(f"RANK #{rank}  —  {r['candidate_name']}\n")
            f.write("─" * 40 + "\n")
            f.write(f"  Combined Score    : {r['combined_score']}/100\n")
            f.write(f"  Ranking Score     : {r['ranking_score']}/100\n")
            f.write(f"  Interview Score   : {r['interview_pct']}%\n")
            f.write(f"  Proctoring        : {r['proctoring_status']}\n")
            f.write(f"  Recommendation    : {r['hire_recommendation']}\n")
            f.write(f"  Risk Level        : {r['risk_level']}\n\n")

    # Save JSON summary
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total":        len(sorted_reports),
            "candidates":   sorted_reports
        }, f, indent=4, ensure_ascii=False)

    print(f"\n> Final Summary TXT  : {txt_file.name}")
    print(f"> Final Summary JSON : {json_file.name}")

# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def run_report_generator():
    output_path    = Path(OUTPUT_FOLDER)
    output_path.mkdir(parents=True, exist_ok=True)
    interviews_path = Path(INTERVIEWS_FOLDER)

    print("=" * 55)
    print("   POST-INTERVIEW REPORT GENERATOR")
    print("=" * 55)

    # Load all transcripts
    transcripts = load_interview_transcripts(interviews_path)
    if not transcripts:
        return

    all_reports   = []
    success_count = 0
    failed_count  = 0

    for i, transcript in enumerate(transcripts, start=1):
        name = transcript.get("candidate_name", "Unknown")
        print(f"\n> [{i}/{len(transcripts)}] Generating report for: {name}...")

        # Calculate combined score
        combined_score = calculate_combined_score(transcript)

        # Generate AI report
        print("  Analyzing with AI...", end=" ", flush=True)
        ai_report = generate_ai_report(transcript)

        if not ai_report:
            print("Failed!")
            failed_count += 1
            continue

        print(f"Done! [{ai_report.get('hire_recommendation', 'N/A')}]")

        # Save individual report
        save_report_txt(transcript, ai_report, combined_score, output_path)
        save_report_json(transcript, ai_report, combined_score, output_path)

        # Collect for final summary
        all_reports.append({
            "candidate_name":    name,
            "source_file":       transcript.get("source_file", ""),
            "combined_score":    combined_score,
            "ranking_score":     transcript.get("ranking_score", 0),
            "interview_pct":     transcript.get("percentage", 0),
            "proctoring_status": transcript.get("proctoring_status", "UNKNOWN"),
            "hire_recommendation": ai_report.get("hire_recommendation", "N/A"),
            "risk_level":        ai_report.get("risk_level", "N/A"),
            "key_strengths":     ai_report.get("key_strengths", []),
            "key_gaps":          ai_report.get("key_gaps", [])
        })

        success_count += 1

    # Save final summary of all candidates
    if all_reports:
        print("\n> Generating final hiring summary...")
        save_final_summary(all_reports, output_path)

    print(f"\n{'='*55}")
    print("  REPORT GENERATION COMPLETE")
    print(f"{'='*55}")
    print(f"  Success  : {success_count}")
    print(f"  Failed   : {failed_count}")
    print(f"  Output   : {OUTPUT_FOLDER}")
    print(f"{'='*55}")


if __name__ == "__main__":
    run_report_generator()
