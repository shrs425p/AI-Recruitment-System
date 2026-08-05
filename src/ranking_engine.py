import hashlib  # Hash-based candidate deduplication
import json  # JSON serialisation for candidate data and output files
from concurrent.futures import ThreadPoolExecutor, as_completed  # Parallel scoring
from datetime import datetime  # Timestamps in output filenames
from pathlib import Path  # Cross-platform path handling

from app.utils import call_ollama, clean_json_response  # Shared AI utilities

from app.app_paths import data_path

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
    # Pull all skill lists from the rich NLP schema into one flat list for the prompt
    skills_raw = candidate.get("skills") or {}
    if isinstance(skills_raw, dict):
        all_skills = (
            skills_raw.get("technical_skills", []) +
            skills_raw.get("tools_and_technologies", []) +
            skills_raw.get("domain_specific_skills", [])
        )
    else:
        all_skills = skills_raw if isinstance(skills_raw, list) else []

    exp_years = candidate.get("total_experience_years") or 0
    edu_list  = candidate.get("education") or []
    edu_str   = ", ".join(
        f"{e.get('degree', '')} {e.get('field_of_study', '')}" for e in edu_list
    ) if isinstance(edu_list, list) else str(edu_list)
    certs_raw = candidate.get("certifications") or []
    certs_str = ", ".join(
        c.get("name", str(c)) if isinstance(c, dict) else str(c)
        for c in certs_raw
    )

    return f"""
You are a senior HR evaluator. Score this candidate against the Job Description using STRICT rubrics.

SCORING RUBRICS (follow exactly — do not deviate):

domain_match ({WEIGHTS['domain_match']} pts max):
  {WEIGHTS['domain_match']} pts — Candidate domain/industry is a direct match to the JD domain
  {round(WEIGHTS['domain_match'] * 0.65)} pts — Related domain (e.g. Software Dev for an AI role, Finance for a FinTech role)
  {round(WEIGHTS['domain_match'] * 0.3)} pts — Adjacent domain (STEM, Engineering for a tech role)
  0 pts   — Completely unrelated domain

skills_match ({WEIGHTS['skills_match']} pts max):
  Score proportionally based on what % of required_skills are present.
  Also give partial credit for related skills (e.g. PyTorch counts for a TensorFlow requirement).
  Group related skills together: ML/DL/AI frameworks are equivalent, SQL/NoSQL are equivalent.
  {WEIGHTS['skills_match']} pts — 80%+ of required skills present
  {round(WEIGHTS['skills_match'] * 0.7)} pts — 50–80% of required skills present
  {round(WEIGHTS['skills_match'] * 0.45)} pts — 25–50% of required skills present
  {round(WEIGHTS['skills_match'] * 0.2)} pts — < 25% of required skills present
  0 pts   — No relevant skills

experience_years ({WEIGHTS['experience_years']} pts max):
  Use these EXACT bands — do not deviate:
  {WEIGHTS['experience_years']} pts — 5+ years of relevant experience
  {round(WEIGHTS['experience_years'] * 0.9)} pts — 2–5 years of relevant experience
  {round(WEIGHTS['experience_years'] * 0.7)} pts — 0–2 years of relevant experience
  {round(WEIGHTS['experience_years'] * 0.5)} pts — Fresher / experience not mentioned (do NOT give 0)
  0 pts   — Clearly irrelevant experience only

education ({WEIGHTS['education']} pts max):
  {WEIGHTS['education']} pts — PhD or Doctorate
  {round(WEIGHTS['education'] * 0.8)} pts — Masters / M.Tech / MBA
  {round(WEIGHTS['education'] * 0.6)} pts — Bachelors / B.Tech / B.E.
  {round(WEIGHTS['education'] * 0.33)} pts — Diploma / Associate
  0 pts   — No education information

certifications ({WEIGHTS['certifications']} pts max):
  {WEIGHTS['certifications']} pts — 3+ relevant certifications
  {round(WEIGHTS['certifications'] * 0.6)} pts — 1–2 relevant certifications
  0 pts   — No certifications

STRICT RULES:
- Follow rubric bands exactly.
- Base scores ONLY on the candidate data provided.
- Do NOT assume or hallucinate missing information.
- Provide a 1-sentence reason for each score.
- Return ONLY valid JSON — no markdown, no explanation.

JOB DESCRIPTION:
{json.dumps(jd, indent=2)}

CANDIDATE:
- Domain: {candidate.get('domain', 'Unknown')}
- Skills: {', '.join(all_skills[:20]) or 'None listed'}
- Experience: {exp_years} years
- Education: {edu_str or 'Not mentioned'}
- Certifications: {certs_str or 'None'}
- Source file: {candidate.get('_source_file', '')}

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
    Load all *_nlp.json files from the NLP folder, deduplicating by
    name+domain hash to prevent the same resume being scored twice.

    Returns a list of unique candidate dicts, or [] if the folder is empty.
    """
    candidates = []
    seen_ids: set[str] = set()
    json_files = list(nlp_folder.glob("*_nlp.json"))

    if not json_files:
        print(f"[ERROR] No NLP JSON files found in '{nlp_folder}'.")
        print("  Run nlp_extractor.py first.")
        return []

    dupes = 0
    for jf in json_files:
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)

            # Build a dedup key from name + domain + top skills
            name_raw   = ((data.get("personal_info") or {}).get("name") or "").lower().strip()
            domain_raw = (data.get("domain") or "").lower().strip()
            skills_raw = data.get("skills") or {}
            if isinstance(skills_raw, dict):
                flat_skills = (
                    skills_raw.get("technical_skills", []) +
                    skills_raw.get("tools_and_technologies", [])
                )
            else:
                flat_skills = skills_raw if isinstance(skills_raw, list) else []
            skills_key = "|".join(sorted(s.lower().strip() for s in flat_skills[:5]))
            dedup_key  = hashlib.sha256(
                f"{name_raw}|{domain_raw}|{skills_key}".encode()
            ).hexdigest()[:16]

            if dedup_key in seen_ids:
                print(f"  [SKIP] Duplicate resume skipped: {jf.name} (same as a previously loaded candidate)")
                dupes += 1
                continue

            seen_ids.add(dedup_key)
            data["_source_file"] = jf.stem
            data["_dedup_id"]    = dedup_key
            candidates.append(data)

        except Exception as e:
            print(f"  [WARNING] Could not load {jf.name}: {e}")

    total = len(candidates)
    if dupes:
        print(f"> Found {total + dupes} file(s) — {dupes} duplicate(s) removed — ranking {total} unique candidate(s).")
    else:
        print(f"> Found {total} candidate(s) to rank.")

    return candidates

# ─────────────────────────────────────────────
# SCORE A SINGLE CANDIDATE (used in parallel)
# ─────────────────────────────────────────────

def score_candidate(candidate: dict, jd: dict):
    """
    Score a single candidate against the parsed Job Description.

    Post-processing applied after AI response:
      - Sub-scores are clamped to their defined max weight.
      - Total is recalculated from clamped sub-scores.
      - hire_recommendation is overridden when the AI verdict disagrees
        with the numeric score by more than one tier — the score wins.
      - Domain and confidence are carried forward from the NLP data.
    """
    name = (candidate.get("personal_info") or {}).get("name") or candidate.get("_source_file", "Unknown")

    # Extract domain from NLP for display
    domain = (candidate.get("domain") or "").strip() or "General"

    # Compute data-completeness confidence
    skills_raw = candidate.get("skills") or {}
    if isinstance(skills_raw, dict):
        all_skills = (
            skills_raw.get("technical_skills", []) +
            skills_raw.get("tools_and_technologies", []) +
            skills_raw.get("domain_specific_skills", [])
        )
    else:
        all_skills = skills_raw if isinstance(skills_raw, list) else []

    edu_list = candidate.get("education") or []
    exp_val  = candidate.get("total_experience_years") or 0
    conf_score = sum([
        1 if name and name.lower() not in ("unknown", "none", "") else 0,
        1 if len(all_skills) >= 3 else 0,
        1 if domain and domain != "General" else 0,
        1 if edu_list else 0,
        1 if float(exp_val or 0) > 0 else 0,
    ])
    confidence = "High" if conf_score >= 4 else "Medium" if conf_score >= 2 else "Low"

    try:
        prompt       = build_scoring_prompt(candidate, jd)
        score_result = call_ai(prompt)

        if not score_result:
            print(f"  [FAILED]  {name}")
            return None

        # Fill candidate_name if AI left it blank
        if not score_result.get("candidate_name"):
            score_result["candidate_name"] = name

        # Carry source file, domain, and confidence into result
        score_result["_source_file"] = candidate.get("_source_file", "")
        score_result["domain"]       = domain
        score_result["confidence"]   = confidence

        # Clamp each sub-score to [0, max_weight]
        scores = score_result.get("scores") or {}
        for key, val in scores.items():
            max_val      = WEIGHTS.get(key, 0)
            val["score"] = min(max(int(val.get("score", 0)), 0), max_val)

        # Recalculate total from clamped sub-scores
        total = sum(v.get("score", 0) for v in scores.values())
        score_result["total_score"] = total
        score_result["percentage"]  = round(total, 1)

        # Override hire_recommendation when it contradicts the numeric score.
        # The score is computed from rubrics and is more reliable than free-text AI.
        score_result["hire_recommendation"] = _score_to_recommendation(total)

        print(f"  [DONE]    {str(name):<40} Score: {total}/100  [{confidence} confidence]")
        return score_result

    except Exception as e:
        print(f"  [ERROR]   {name} — {e}")
        return None


def _score_to_recommendation(total: int) -> str:
    """Map a numeric score to a consistent recommendation label."""
    if total >= 75:
        return "Strongly Recommend"
    elif total >= 58:
        return "Recommend"
    elif total >= 40:
        return "Neutral"
    else:
        return "Not Recommend"

# ─────────────────────────────────────────────
# SAVE LEADERBOARD TXT
# ─────────────────────────────────────────────

def save_leaderboard_txt(ranked: list, jd: dict, output_path: Path):
    stamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_file  = output_path / f"leaderboard_{stamp}.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    output_path.mkdir(parents=True, exist_ok=True)
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
                f.write("\n  STRENGTHS:\n")
                for s in strengths:
                    f.write(f"    + {s}\n")

            gaps = candidate.get("gaps") or []
            if gaps:
                f.write("\n  GAPS:\n")
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
    output_path.mkdir(parents=True, exist_ok=True)
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
    print("  RANKING COMPLETE — TOP CANDIDATES")
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
