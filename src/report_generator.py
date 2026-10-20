import logging

logger = logging.getLogger(__name__)

import json  # JSON serialisation for report files
import re  # Regex — sanitise filenames
import unicodedata
from datetime import datetime  # Timestamps for file names
from pathlib import Path  # Cross-platform path handling

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from src.common import call_ollama, data_path
from src.common import clean_json_response as clean_json  # AI utilities

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

def call_ai(system_msg: str, user_msg: str, candidate_name: str = "") -> str:
    """
    Wrapper that calls the AI model using user-configured settings.
    """
    import config
    is_json = "valid json" in system_msg.lower() or "return only valid json" in user_msg.lower()
    think_setting = getattr(config, "AI_THINKING_INTERVIEW", False)
    return call_ollama(
        system_msg,
        user_msg,
        think=False if is_json else think_setting,
        format="json" if is_json else None,
        candidate_name=candidate_name
    )

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
        logger.info(f"[ERROR] No interview transcripts found in '{interviews_folder}'.")
        logger.info("  Run interview_bot.py first.")
        return []

    logger.info(f"> Found {len(json_files)} interview transcript(s).")
    transcripts = []

    for jf in json_files:
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
            data["_source_file"] = jf.name  # track which file this came from
            transcripts.append(data)
        except Exception as e:
            logger.info(f"  [WARNING] Could not load {jf.name}: {e}")

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

        for idx, r in enumerate(transcript.get("responses", []), start=1):
            q_num = r.get("question_num", idx)
            q_type = r.get("type", "TECHNICAL")
            f.write(f"Q{q_num} [{q_type}] — {r.get('topic', '')}\n")
            f.write("─" * 40 + "\n")
            f.write(f"  Question  : {r.get('question', '')}\n")
            f.write(f"  Answer    : {r.get('answer', '')}\n")
            f.write(f"  Score     : {r.get('score', 0)}/10\n")
            eval_data = r.get("evaluation") or {}
            f.write(f"  Feedback  : {eval_data.get('feedback', '')}\n")
            proctor_info = r.get("proctor") or {}
            if proctor_info.get("flagged"):
                flags = proctor_info.get("flags") or []
                flags_str = ", ".join(str(fl) for fl in flags)
                f.write(f"  FLAGS     : {flags_str}\n")
            f.write(f"  Time      : {r.get('time_taken', 0)}s\n\n")

    logger.info(f"  Report TXT saved: {txt_file.name}")
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

    logger.info(f"  Report JSON saved: {json_file.name}")


# ─────────────────────────────────────────────
# STEP 5B: SAVE REPORT AS PDF (styled document)
# ─────────────────────────────────────────────

def clean_pdf_text(text) -> str:
    """Sanitize strings for Latin-1 encoding used by FPDF standard fonts."""
    if text is None:
        return ""
    text = str(text)
    replacements = {
        "\u2014": " - ",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "*",
        "\u2026": "...",
        "\u00a0": " ",
        "\u2192": "->",
        "\u2190": "<-",
        "\u2713": "[v]",
        "\u2717": "[x]",
        "\u26a0": "[!]",
        "\u23f1": "",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = unicodedata.normalize("NFKD", text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class EvaluationReportPDF(FPDF):
    """
    Minimalist, Material Design 3 (Material You) Monochrome PDF report.
    Clean black & white / grayscale palette, subtle borders, high contrast.
    """
    def __init__(self, candidate_name="Candidate", job_title="Job"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.candidate_name = clean_pdf_text(candidate_name)
        self.job_title = clean_pdf_text(job_title)
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(15, 15, 15)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 5, f"AI RECRUITMENT SYSTEM  |  {self.candidate_name.upper()}  -  {self.job_title.upper()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_draw_color(220, 220, 220)
            self.set_line_width(0.2)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(130, 130, 130)
        self.set_draw_color(225, 225, 225)
        self.set_line_width(0.2)
        self.line(15, self.get_y() - 1, 195, self.get_y() - 1)
        self.cell(90, 8, "Confidential - AI Recruitment System  |  Fairness & Integrity Audited", align="L")
        self.cell(90, 8, f"Page {self.page_no()} of {{nb}}", align="R")

    def section_heading(self, title):
        self.ln(3)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(20, 20, 20)
        self.cell(0, 5, clean_pdf_text(title.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(210, 210, 210)
        self.set_line_width(0.3)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(3)

    def write_para(self, label, text, bold_label=True, text_color=(35, 35, 35)):
        self.set_x(self.l_margin)
        if label:
            self.set_font("Helvetica", "B" if bold_label else "", 8.5)
            self.set_text_color(80, 80, 80)
            self.cell(0, 4.2, clean_pdf_text(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*text_color)
        self.multi_cell(0, 4.2, clean_pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.5)


def generate_evaluation_pdf(report: dict, output_file: Path | None = None) -> FPDF:
    """Generate a structured, minimalist Material Design 3 monochrome PDF evaluation report."""
    candidate_name = report.get("candidate_name", "Unknown Candidate")
    job_title = report.get("job_title", "Open Position") or "Open Position"
    pdf = EvaluationReportPDF(candidate_name, job_title)
    pdf.alias_nb_pages()
    pdf.add_page()

    # 1. Minimalist Top Header (Clean Black & White Material Style)
    pdf.set_xy(15, 16)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 4.5, "AI RECRUITMENT SYSTEM  /  EVALUATION SUITE", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(0, 8, "Post-Interview Evaluation Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 4.5, "Automated technical scoring, rubric diagnostics, integrity proctoring & hiring assessment.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Hairline divider
    pdf.ln(1)
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)

    # 2. Metadata Grid (Clean Material You Key-Value Layout)
    y_meta = pdf.get_y()
    pdf.set_fill_color(250, 250, 250)
    pdf.set_draw_color(225, 225, 225)
    pdf.rect(15, y_meta, 180, 16, style="FD")

    pdf.set_xy(18, y_meta + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(28, 4.5, "CANDIDATE")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(60, 4.5, clean_pdf_text(candidate_name))

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(24, 4.5, "JOB TITLE")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(64, 4.5, clean_pdf_text(job_title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(18, y_meta + 7.5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(28, 4.5, "EVALUATION DATE")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(60, 4.5, clean_pdf_text(report.get("generated_at", report.get("interview_date", "N/A"))))

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(24, 4.5, "DOMAIN")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(64, 4.5, clean_pdf_text(report.get("domain", "General Engineering") or "General"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(18, y_meta + 12)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(174, 3.5, "Fairness Audit: Scoring based on technical competence and role alignment. Protected demographic characteristics isolated.", align="L")

    pdf.set_xy(15, y_meta + 18)

    # 3. Score Overview Matrix (Minimalist Material Stat Chips)
    pdf.section_heading("EXECUTIVE SCORE SUMMARY")
    scores = report.get("scores") or {}
    proctoring = report.get("proctoring") or {}
    ai_report = report.get("ai_report") or {}
    responses = report.get("responses") or []

    combined = scores.get("combined_score", 0)
    ranking = scores.get("ranking_score", 0)
    interview_pct = scores.get("interview_pct", 0)
    interview_score = scores.get("interview_score", 0)
    interview_max = scores.get("interview_max", 50)
    proc_status = proctoring.get("status", "UNKNOWN")
    proc_flags = proctoring.get("flagged_count", 0)

    # Compute technical / behavioral numbers dynamically
    tech_resp = [r for r in responses if r.get("type", "").upper() == "TECHNICAL"]
    behav_resp = [r for r in responses if r.get("type", "").upper() == "BEHAVIORAL"]

    if tech_resp:
        tech_score = sum(r.get("score", 0) for r in tech_resp)
        tech_max = len(tech_resp) * 10
        tech_pct = round((tech_score / tech_max) * 100, 1) if tech_max else 0
        tech_sub = f"{tech_score}/{tech_max} pts"
    elif scores.get("technical_max"):
        tech_score = scores.get("technical_score", 0)
        tech_max = scores.get("technical_max", 0)
        tech_pct = scores.get("technical_pct", 0)
        tech_sub = f"{tech_score}/{tech_max} pts"
    else:
        tech_pct = scores.get("technical_pct", 0)
        tech_sub = "Technical"

    if behav_resp:
        behav_score = sum(r.get("score", 0) for r in behav_resp)
        behav_max = len(behav_resp) * 10
        behav_pct = round((behav_score / behav_max) * 100, 1) if behav_max else 0
        behav_sub = f"{behav_score}/{behav_max} pts"
    elif scores.get("behavioral_max"):
        behav_score = scores.get("behavioral_score", 0)
        behav_max = scores.get("behavioral_max", 0)
        behav_pct = scores.get("behavioral_pct", 0)
        behav_sub = f"{behav_score}/{behav_max} pts"
    else:
        behav_pct = scores.get("behavioral_pct", 0)
        behav_sub = "Behavioral"

    # 6 Minimalist Grayscale Stat Cards across 180mm
    col_w = 28.5
    gap = 1.8
    h_box = 15
    x_start = pdf.get_x()
    y_start = pdf.get_y()
    cards = [
        ("COMBINED", f"{combined}/100", "40% R + 60% I"),
        ("RESUME", f"{ranking}/100", "Resume Rank"),
        ("INTERVIEW", f"{interview_pct}%", f"{interview_score}/{interview_max} pts"),
        ("TECHNICAL", f"{tech_pct}%", tech_sub),
        ("BEHAVIORAL", f"{behav_pct}%", behav_sub),
        ("PROCTORING", clean_pdf_text(proc_status), f"{proc_flags} flag(s)")
    ]

    for i, (label, val, sub) in enumerate(cards):
        cx = x_start + (i * (col_w + gap))
        pdf.set_xy(cx, y_start)
        pdf.set_fill_color(252, 252, 252)
        pdf.set_draw_color(220, 220, 220)
        pdf.rect(cx, y_start, col_w, h_box, style="FD")

        # Top label
        pdf.set_xy(cx, y_start + 1.2)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(110, 110, 110)
        pdf.cell(col_w, 3.5, label, align="C")

        # Main Value (Crisp Black / High Contrast)
        pdf.set_xy(cx, y_start + 5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(15, 15, 15)
        pdf.cell(col_w, 4.5, val, align="C")

        # Subtitle
        pdf.set_xy(cx, y_start + 10)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(col_w, 3, sub, align="C")

    pdf.set_xy(x_start, y_start + h_box + 3)

    # 4. Hire Recommendation Card (Minimalist B&W Pill Box with No Text Overlap)
    rec = ai_report.get("hire_recommendation", "N/A")
    risk = ai_report.get("risk_level", "N/A")
    justification = ai_report.get("hire_justification", "")

    y_rec = pdf.get_y()
    pdf.set_fill_color(248, 248, 248)
    pdf.set_draw_color(200, 200, 200)
    pdf.rect(15, y_rec, 180, 8, style="FD")

    pdf.set_xy(18, y_rec + 1.5)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(70, 5, f"HIRING DECISION:  {clean_pdf_text(rec).upper()}")

    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(50, 5, f"RISK ASSESSMENT:  {clean_pdf_text(risk).upper()}")

    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(56, 5, f"COMBINED SCORE:  {combined}/100", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(15, y_rec + 10.5)
    if justification:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 4, "HIRING JUSTIFICATION & RATIONALE:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(0, 4.2, clean_pdf_text(justification), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

    # 5. Core Assessments
    pdf.section_heading("AI ASSESSMENT NARRATIVE")

    if ai_report.get("overall_summary"):
        pdf.write_para("Overall Summary:", ai_report.get("overall_summary"))

    if ai_report.get("technical_assessment"):
        pdf.write_para("Technical Assessment:", ai_report.get("technical_assessment"))

    if ai_report.get("behavioral_assessment"):
        pdf.write_para("Behavioral Assessment:", ai_report.get("behavioral_assessment"))

    # Key Strengths & Key Gaps (Minimalist Clean Bullets)
    strengths = ai_report.get("key_strengths") or []
    if isinstance(strengths, list) and strengths:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(20, 20, 20)
        pdf.cell(0, 4.5, "Key Strengths:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(40, 40, 40)
        for s in strengths:
            pdf.multi_cell(0, 3.8, clean_pdf_text(f"[+]  {s}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

    gaps = ai_report.get("key_gaps") or []
    if isinstance(gaps, list) and gaps:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(20, 20, 20)
        pdf.cell(0, 4.5, "Key Gaps (Areas to Improve):", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(40, 40, 40)
        for g in gaps:
            pdf.multi_cell(0, 3.8, clean_pdf_text(f"[-]  {g}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

    # Next Steps & Proctor Remarks
    next_steps = ai_report.get("suggested_next_steps") or []
    if isinstance(next_steps, list) and next_steps:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(20, 20, 20)
        pdf.cell(0, 4.5, "Suggested Next Steps:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(40, 40, 40)
        for idx, ns in enumerate(next_steps, 1):
            pdf.multi_cell(0, 3.8, clean_pdf_text(f"{idx}.  {ns}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

    if ai_report.get("proctoring_remarks"):
        pdf.write_para("Proctoring Remarks & Integrity Observations:", ai_report.get("proctoring_remarks"))

    # 6. Detailed Q&A Transcript
    if responses:
        pdf.section_heading(f"DETAILED QUESTION-BY-QUESTION BREAKDOWN ({len(responses)} QUESTIONS)")

        for r in responses:
            q_num = r.get("question_num", 1)
            q_type = r.get("type", "TECHNICAL")
            q_topic = r.get("topic", "")
            q_score = r.get("score", 0)
            time_taken = r.get("time_taken", 0)
            eval_data = r.get("evaluation") or {}
            ans_flags = r.get("answer_flags") or []

            # Check page break margin so question card starts cleanly
            if pdf.get_y() > 225:
                pdf.add_page()

            # Q Header Bar (Minimalist Light Gray Container)
            y_q = pdf.get_y()
            pdf.set_fill_color(246, 246, 248)
            pdf.set_draw_color(215, 215, 220)
            pdf.rect(15, y_q, 180, 6.5, style="FD")

            pdf.set_xy(17, y_q + 0.8)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(20, 20, 20)
            header_title = f"QUESTION {q_num}  [{q_type}]  -  {clean_pdf_text(q_topic).upper()}"
            pdf.cell(95, 5, header_title)

            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(20, 20, 20)
            pdf.cell(35, 5, f"SCORE: {q_score} / 10", align="C")

            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(110, 110, 110)
            flag_str = f"{len(ans_flags)} flag(s)" if ans_flags else "Clean"
            pdf.cell(46, 5, f"Time: {time_taken}s  |  {flag_str}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_xy(15, y_q + 8)

            # Question Prompt (Indented clean quote block)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(0, 4, "QUESTION PROMPT:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(20, 20, 20)
            pdf.multi_cell(0, 4, clean_pdf_text(r.get("question", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

            # Candidate Answer (Bordered or indented container)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(0, 4, "CANDIDATE'S VERBATIM ANSWER:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(45, 45, 45)
            ans_text = clean_pdf_text(r.get("answer", ""))
            pdf.multi_cell(0, 3.8, ans_text if ans_text else "[No response recorded]", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

            # Score Rubric Breakdown (Minimalist M3 chips in Grayscale)
            if eval_data:
                rel = eval_data.get("relevance", "-")
                dep = eval_data.get("depth", "-")
                cla = eval_data.get("clarity", "-")
                cor = eval_data.get("correctness", "-")

                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(30, 30, 30)
                rubric_str = f"RUBRIC BREAKDOWN:  Relevance: {rel}/3   |   Depth: {dep}/3   |   Clarity: {cla}/2   |   Correctness: {cor}/2"
                pdf.cell(0, 4, rubric_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                feedback = eval_data.get("feedback")
                if feedback:
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(80, 80, 80)
                    pdf.multi_cell(0, 3.6, clean_pdf_text(f"AI Feedback: {feedback}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                sp = eval_data.get("strong_points") or []
                wp = eval_data.get("weak_points") or []
                if isinstance(sp, list) and sp:
                    pdf.set_x(pdf.l_margin)
                    pdf.set_font("Helvetica", "", 7.5)
                    pdf.set_text_color(30, 30, 30)
                    pdf.cell(0, 3.5, f"Strengths: {clean_pdf_text(', '.join(sp))}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                if isinstance(wp, list) and wp:
                    pdf.set_x(pdf.l_margin)
                    pdf.set_font("Helvetica", "", 7.5)
                    pdf.set_text_color(60, 60, 60)
                    pdf.cell(0, 3.5, f"Areas to Lag (Gaps): {clean_pdf_text(', '.join(wp))}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            if ans_flags:
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(20, 20, 20)
                pdf.cell(0, 3.5, f"Integrity Audit Flags: {clean_pdf_text(', '.join(ans_flags))}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.ln(3)

    if output_file:
        pdf.output(str(output_file))

    return pdf


def save_report_pdf(transcript: dict, ai_report: dict, combined_score: float, output_path: Path) -> Path:
    """Save full report as styled PDF."""
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', transcript.get("candidate_name", "unknown"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_file = output_path / f"report_{safe_name}_{timestamp}.pdf"

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
            "status":        transcript.get("proctoring_status", "UNKNOWN"),
            "flagged_count": transcript.get("flagged_count", 0),
            "log":           transcript.get("proctor_log", [])
        },
        "ai_report":   ai_report,
        "responses":   transcript.get("responses", [])
    }

    output_path.mkdir(parents=True, exist_ok=True)
    generate_evaluation_pdf(report, output_file=pdf_file)
    logger.info(f"  Report PDF saved: {pdf_file.name}")
    return pdf_file


# ─────────────────────────────────────────────
# STEP 6: SAVE FINAL SUMMARY LEADERBOARD
# ─────────────────────────────────────────────

def save_final_summary(all_reports: list, output_path: Path):
    """Save a final summary of all candidates ranked by combined score."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_file  = output_path / f"final_summary_{timestamp}.txt"
    json_file = output_path / f"final_summary_{timestamp}.json"

    # Sort by combined score safely
    sorted_reports = sorted(all_reports, key=lambda x: float(x.get("combined_score") or 0.0), reverse=True)

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
            f.write(f"RANK #{rank}  —  {r.get('candidate_name', 'Unknown')}\n")
            f.write("─" * 40 + "\n")
            f.write(f"  Combined Score    : {r.get('combined_score', 0)}/100\n")
            f.write(f"  Ranking Score     : {r.get('ranking_score', 0)}/100\n")
            f.write(f"  Interview Score   : {r.get('interview_pct', 0)}%\n")
            f.write(f"  Proctoring        : {r.get('proctoring_status', 'UNKNOWN')}\n")
            f.write(f"  Recommendation    : {r.get('hire_recommendation', 'N/A')}\n")
            f.write(f"  Risk Level        : {r.get('risk_level', 'N/A')}\n\n")

    # Save JSON summary
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total":        len(sorted_reports),
            "candidates":   sorted_reports
        }, f, indent=4, ensure_ascii=False)

    logger.info(f"\n> Final Summary TXT  : {txt_file.name}")
    logger.info(f"> Final Summary JSON : {json_file.name}")

# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def run_report_generator():
    output_path    = Path(OUTPUT_FOLDER)
    output_path.mkdir(parents=True, exist_ok=True)
    interviews_path = Path(INTERVIEWS_FOLDER)

    logger.info("=" * 55)
    logger.info("   POST-INTERVIEW REPORT GENERATOR")
    logger.info("=" * 55)

    # Load all transcripts
    transcripts = load_interview_transcripts(interviews_path)
    if not transcripts:
        return

    all_reports   = []
    success_count = 0
    failed_count  = 0

    for i, transcript in enumerate(transcripts, start=1):
        name = transcript.get("candidate_name", "Unknown")
        logger.info(f"\n> [{i}/{len(transcripts)}] Generating report for: {name}...")

        # Calculate combined score
        combined_score = calculate_combined_score(transcript)

        # Generate AI report
        logger.info("  Analyzing with AI...")
        ai_report = generate_ai_report(transcript)

        if not ai_report:
            logger.info("Failed!")
            failed_count += 1
            continue

        logger.info(f"Done! [{ai_report.get('hire_recommendation', 'N/A')}]")

        # Save individual report
        save_report_txt(transcript, ai_report, combined_score, output_path)
        save_report_json(transcript, ai_report, combined_score, output_path)
        save_report_pdf(transcript, ai_report, combined_score, output_path)

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
        logger.info("\n> Generating final hiring summary...")
        save_final_summary(all_reports, output_path)

    logger.info(f"\n{'='*55}")
    logger.info("  REPORT GENERATION COMPLETE")
    logger.info(f"{'='*55}")
    logger.info(f"  Success  : {success_count}")
    logger.info(f"  Failed   : {failed_count}")
    logger.info(f"  Output   : {OUTPUT_FOLDER}")
    logger.info(f"{'='*55}")


if __name__ == "__main__":
    run_report_generator()
