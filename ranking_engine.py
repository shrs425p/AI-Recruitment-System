import json    # JSON serialisation for candidate data and output files
import re      # Regex (used when building AI prompts)
from pathlib import Path       # Cross-platform path handling
from datetime import datetime  # Timestamps in output filenames
from concurrent.futures import ThreadPoolExecutor, as_completed  # Parallel scoring
from config import OLLAMA_MODEL            # AI model name from central config
import sys
from utils import clean_json_response, call_ollama  # Shared AI utilities
from app_paths import data_path

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Folder where NLP JSON files produced by nlp_extractor.py are stored
NLP_FOLDER        = data_path("output/nlp")

# Folder where ranking output files (leaderboard + scores JSON) are saved
OUTPUT_FOLDER     = data_path("output/ranking")

# How many candidates to score at the same time.
# Increase if the Ollama server / cloud API can handle parallel requests.
# Lower this if you see timeout errors.
MAX_WORKERS       = 5

# ─────────────────────────────────────────────
# SCORING WEIGHTS (must add up to 100)
# ─────────────────────────────────────────────

# Each key maps to a maximum number of points the AI can award.
# The AI is instructed to score only up to this maximum for each criterion.
# Change these values to re-weight the importance of different factors.
WEIGHTS = {
    "domain_match":      20,  # Most important — wrong domain = wrong hire
    "skills_match":      35,  # Highest weight — skills directly match the job
    "experience_years":  20,  # Years of relevant work experience
    "education":         15,  # Degree level and field of study
    "certifications":    10,  # Industry certifications (bonus points)
}

# ─────────────────────────────────────────────
# PROMPT: Parse Job Description
# ─────────────────────────────────────────────

def build_jd_prompt(jd_text: str) -> str:
    return f"""
You are an expert HR analyst. Read the Job Description below and extract key requirements.
Return ONLY valid JSON. No explanation, no markdown, no extra text.

JD TEXT:
\"\"\"
{jd_text}
\"\"\"

Return EXACTLY this JSON:
{{
  "job_title": "",
  "domain": "",
  "required_experience_years": null,
  "required_education": "",
  "required_skills": [],
  "preferred_skills": [],
  "required_certifications": [],
  "job_summary": ""
}}
"""

# ─────────────────────────────────────────────
# PROMPT: Score a Candidate Against JD
# ─────────────────────────────────────────────

def build_scoring_prompt(candidate: dict, jd: dict) -> str:
    return f"""
You are a senior HR evaluator. Your job is to objectively score a candidate against a Job Description.

SCORING CRITERIA AND WEIGHTS:
- domain_match      : {WEIGHTS['domain_match']} points  — Does candidate domain/industry match the JD?
- skills_match      : {WEIGHTS['skills_match']} points  — How well do candidate skills cover JD required + preferred skills?
- experience_years  : {WEIGHTS['experience_years']} points  — Does candidate experience meet or exceed JD requirement?
- education         : {WEIGHTS['education']} points  — Does candidate education meet JD requirement?
- certifications    : {WEIGHTS['certifications']} points  — Does candidate have relevant certifications?

TOTAL POSSIBLE SCORE: 100 points

STRICT RULES:
- Score each category out of its maximum points ONLY.
- Base scores ONLY on what is present in the candidate data.
- Do NOT assume or hallucinate missing information.
- Provide a short reason for each score (1 sentence).
- Return ONLY valid JSON. No explanation, no markdown, no extra text.

JOB DESCRIPTION:
{json.dumps(jd, indent=2)}

CANDIDATE DATA:
{json.dumps(candidate, indent=2)}

Return EXACTLY this JSON:
{{
  "candidate_name": "",
  "scores": {{
    "domain_match":     {{"score": 0, "max": {WEIGHTS['domain_match']}, "reason": ""}},
    "skills_match":     {{"score": 0, "max": {WEIGHTS['skills_match']}, "reason": ""}},
    "experience_years": {{"score": 0, "max": {WEIGHTS['experience_years']}, "reason": ""}},
    "education":        {{"score": 0, "max": {WEIGHTS['education']}, "reason": ""}},
    "certifications":   {{"score": 0, "max": {WEIGHTS['certifications']}, "reason": ""}}
  }},
  "total_score": 0,
  "percentage": 0,
  "overall_verdict": "",
  "strengths": [],
  "gaps": [],
  "hire_recommendation": ""
}}
"""

# ─────────────────────────────────────────────
# CALL AI MODEL
# ─────────────────────────────────────────────

def call_ai(prompt: str) -> dict:
    """
    Wrapper that sends a single-string prompt to the AI and returns parsed JSON.
    Uses a strict system message to minimise non-JSON output from the model.
    """
    raw = call_ollama(
        "You are a precise HR analyst. Always return valid JSON only.",
        prompt
    )
    return clean_json_response(raw) if raw else {}

# ─────────────────────────────────────────────
# LOAD ALL CANDIDATE JSON FILES
# ─────────────────────────────────────────────

def load_candidates(nlp_folder: Path) -> list:
    """
    Load all *_nlp.json files from the NLP folder.

    Each file represents one candidate's extracted resume data.
    A '_source_file' key is injected into each dict so downstream
    stages (scoring, scheduling) can trace back to the original file.

    Returns a list of candidate dicts, or [] if the folder is empty.
    """
    candidates = []
    json_files = list(nlp_folder.glob("*_nlp.json"))  # only NLP output files

    if not json_files:
        print(f"[ERROR] No NLP JSON files found in '{nlp_folder}'.")
        print("  Run nlp_extractor.py first.")
        return []

    print(f"> Found {len(json_files)} candidate(s) to rank.")

    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Attach the source filename so we can display it in the leaderboard
            data["_source_file"] = jf.stem
            candidates.append(data)
        except Exception as e:
            print(f"  [WARNING] Could not load {jf.name}: {e}")

    return candidates

# ─────────────────────────────────────────────
# SCORE A SINGLE CANDIDATE (used in parallel)
# ─────────────────────────────────────────────

def score_candidate(candidate: dict, jd: dict):
    """
    Score a single candidate against the parsed Job Description.
    Designed to run in a ThreadPoolExecutor so many candidates are
    scored concurrently.

    Safety measures applied after the AI response:
      - Caps each sub-score to its defined max weight (prevents AI hallucination
        that gives e.g. 40/35 for skills_match).
      - Recalculates total_score from clamped sub-scores for consistency.
      - Fills in candidate_name from NLP data if AI left it blank.

    Returns None if the AI call failed, so callers can skip failed candidates.
    """
    # Safely extract candidate name — personal_info may be null in some NLP outputs
    name = (candidate.get("personal_info") or {}).get("name") or candidate.get("_source_file", "Unknown")

    try:
        prompt       = build_scoring_prompt(candidate, jd)
        score_result = call_ai(prompt)

        if not score_result:
            print(f"  [FAILED]  {name}")
            return None

        # Ensure candidate_name is populated even if AI returned an empty string
        if not score_result.get("candidate_name") or score_result["candidate_name"] == "":
            score_result["candidate_name"] = name

        # Carry the source filename through to output (needed by scheduling stage)
        score_result["_source_file"] = candidate.get("_source_file", "")

        # Clamp each sub-score between 0 and its maximum weight
        # This prevents over-inflated totals if the AI hallucinates high scores
        scores = score_result.get("scores") or {}
        for key, val in scores.items():
            max_val      = WEIGHTS.get(key, 0)
            val["score"] = min(max(val.get("score", 0), 0), max_val)  # clamp to [0, max]

        # Recalculate total from the now-clamped sub-scores (safety check)
        total = sum(v.get("score", 0) for v in scores.values())
        score_result["total_score"] = total
        score_result["percentage"]  = round(total, 1)  # total is already out of 100

        print(f"  [DONE]    {str(name):<40} Score: {total}/100")
        return score_result

    except Exception as e:
        print(f"  [ERROR]   {name} — {e}")
        return None

# ─────────────────────────────────────────────
# SAVE LEADERBOARD TXT
# ─────────────────────────────────────────────

def save_leaderboard_txt(ranked: list, jd: dict, output_path: Path):
    stamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_file  = output_path / f"leaderboard_{stamp}.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("       AI RECRUITMENT RANKING LEADERBOARD\n")
        f.write("=" * 60 + "\n")
        f.write(f"Generated        : {timestamp}\n")
        f.write(f"Job Title        : {jd.get('job_title', 'N/A')}\n")
        f.write(f"Domain           : {jd.get('domain', 'N/A')}\n")
        f.write(f"Total Candidates : {len(ranked)}\n")
        f.write("=" * 60 + "\n\n")

        for rank, candidate in enumerate(ranked, start=1):
            scores  = candidate.get("scores") or {}
            name    = candidate.get("candidate_name") or "Unknown"
            source  = candidate.get("_source_file", "")
            display = f"{name} ({source})" if source else name
            total   = candidate.get("total_score", 0)
            percent = candidate.get("percentage", 0)
            verdict = candidate.get("overall_verdict", "")
            hire    = candidate.get("hire_recommendation", "")

            f.write(f"RANK #{rank}  —  {display}\n")
            f.write(f"{'─' * 40}\n")
            f.write(f"  Total Score     : {total}/100  ({percent}%)\n")
            f.write(f"  Verdict         : {verdict}\n")
            f.write(f"  Hire Recommend  : {hire}\n\n")

            f.write("  SCORE BREAKDOWN:\n")
            for criterion, data in scores.items():
                f.write(f"    {criterion.upper():<20}: {data.get('score', 0)}/{data.get('max', 0)}\n")
                f.write(f"    {'':20}  -> {data.get('reason', '')}\n")

            strengths = candidate.get("strengths") or []
            if strengths:
                f.write(f"\n  STRENGTHS:\n")
                for s in strengths:
                    f.write(f"    + {s}\n")

            gaps = candidate.get("gaps") or []
            if gaps:
                f.write(f"\n  GAPS:\n")
                for g in gaps:
                    f.write(f"    - {g}\n")

            f.write("\n" + "=" * 60 + "\n\n")

    print(f"> Leaderboard saved : {txt_file}")

# ─────────────────────────────────────────────
# SAVE SCORES JSON
# ─────────────────────────────────────────────

def save_scores_json(ranked: list, jd: dict, output_path: Path):
    stamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = output_path / f"ranking_scores_{stamp}.json"
    output    = {
        "job_description":   jd,
        "total_candidates":  len(ranked),
        "generated_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ranked_candidates": ranked
    }
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"> Scores JSON saved : {json_file}")

# ─────────────────────────────────────────────
# MAIN RANKING PIPELINE
# ─────────────────────────────────────────────

def run_ranking():
    """
    Main entry point when running ranking_engine.py directly from the terminal.

    Steps:
      1. Prompt user to paste the Job Description.
      2. Parse JD into structured requirements via AI.
      3. Load all candidate NLP JSON files.
      4. Score candidates IN PARALLEL for speed.
      5. Sort by total score descending.
      6. Save leaderboard.txt and ranking_scores.json.
      7. Print a ranked summary table.
    """
    output_path = Path(OUTPUT_FOLDER)
    output_path.mkdir(parents=True, exist_ok=True)
    nlp_path    = Path(NLP_FOLDER)

    print("=" * 50)
    print("   AI RECRUITMENT RANKING ENGINE")
    print("=" * 50)

    # ── Step 1: Get Job Description from user ──
    print("\n> Paste the Job Description below.")
    print("> When done, type 'END' on a new line and press Enter:\n")

    jd_lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":  # sentinel to end multi-line input
            break
        jd_lines.append(line)

    jd_text = "\n".join(jd_lines).strip()
    if not jd_text:
        print("[ERROR] No Job Description provided. Exiting.")
        return

    # ── Step 2: Parse JD ──
    print("\n> Parsing Job Description with AI...", end=" ", flush=True)
    jd_data = call_ai(build_jd_prompt(jd_text))
    if not jd_data:
        print("[ERROR] Failed to parse JD. Exiting.")
        return
    print(f"Done! [{jd_data.get('job_title', 'Unknown Role')}]")

    # ── Step 3: Load candidates ──
    print()
    candidates = load_candidates(nlp_path)
    if not candidates:
        return

    # ── Step 4: Score candidates IN PARALLEL ──
    # ThreadPoolExecutor creates a pool of MAX_WORKERS threads.
    # Each thread scores one candidate independently — no shared state.
    print(f"\n> Scoring {len(candidates)} candidates in parallel (workers: {MAX_WORKERS})...\n")

    # elapsed defined before try block so it is accessible in the except block
    elapsed           = 0
    start_time        = datetime.now()
    scored_candidates = []

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all scoring tasks simultaneously
            futures = {
                executor.submit(score_candidate, candidate, jd_data): candidate
                for candidate in candidates
            }
            # Collect results as each thread finishes (order may vary)
            for future in as_completed(futures):
                result = future.result()
                if result:  # None means the scoring failed for that candidate
                    scored_candidates.append(result)

        elapsed = (datetime.now() - start_time).seconds

    except Exception as e:
        print(f"\n[ERROR] Parallel scoring failed: {e}")
        elapsed = (datetime.now() - start_time).seconds

    if not scored_candidates:
        print("[ERROR] No candidates were scored. Exiting.")
        return

    print(f"\n> Scored {len(scored_candidates)}/{len(candidates)} candidates in {elapsed}s")

    # ── Step 5: Sort by score ── highest score first
    ranked = sorted(scored_candidates, key=lambda x: x.get("total_score", 0), reverse=True)

    # ── Step 6: Save outputs ──
    print("\n> Saving results...")
    save_leaderboard_txt(ranked, jd_data, output_path)  # human-readable leaderboard
    save_scores_json(ranked, jd_data, output_path)       # machine-readable JSON

    # ── Step 7: Print ranked summary table ──
    print(f"\n{'=' * 55}")
    print(f"  RANKING COMPLETE — TOP CANDIDATES")
    print(f"{'=' * 55}")
    for rank, c in enumerate(ranked, start=1):
        name     = c.get("candidate_name") or "Unknown"
        filename = c.get("_source_file", "")
        display  = f"{name} ({filename})" if filename else name
        print(f"  #{rank:<3} {str(display):<45} {c.get('total_score', 0)}/100")
    print(f"{'=' * 55}")
    print(f"\n> Time taken        : {elapsed} seconds")
    print(f"> Full results saved: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    run_ranking()