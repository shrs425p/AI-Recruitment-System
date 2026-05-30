import json     # Serialize / deserialize JSON (saving NLP output)
import re       # Regular expressions (used when building prompts)
import time     # Sleep between polling cycles in the watcher loop
from pathlib import Path  # Cross-platform file/folder path handling
import sys
from config import OLLAMA_MODEL            # AI model name from central config
from utils import clean_json_response, call_ollama  # Shared AI calling utilities
from app_paths import data_path

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Input folder — plain .txt resumes produced by pdf_to_txt.py
INPUT_FOLDER           = data_path("output/txt")

# Output folder — extracted NLP JSON + TXT summaries saved here
OUTPUT_FOLDER          = data_path("output/nlp")

# Placeholder used when the AI cannot find the candidate's name in the resume.
# The txt filename is appended so each record stays uniquely identifiable.
UNKNOWN_NAME           = "CANDIDATE_UNKNOWN"

# How often (seconds) the watcher loop polls for new .txt files
WATCH_INTERVAL_SECONDS = 5

# ─────────────────────────────────────────────
# PROMPT TEMPLATE
# ─────────────────────────────────────────────

def build_prompt(resume_text: str) -> str:
    return f"""
You are an expert HR analyst and resume parser. You work across ALL industries including but not limited to:
IT, Software, Finance, Banking, Medical, Healthcare, Law, Legal, Marketing, Sales, HR, Education,
Engineering (Civil, Mechanical, Electrical), Architecture, Design, Research, Science, and more.

Your task is to carefully read the resume below and extract ALL relevant information into a structured JSON format.

STRICT RULES:
- Extract information ONLY from the resume. Do NOT assume or hallucinate any data.
- If a field is not found, set its value to null.
- Skills must be domain-specific and relevant to the candidate's actual field — not generic.
- For experience, calculate total years based on date ranges if mentioned.
- Detect the candidate's domain/industry automatically.
- Return ONLY valid JSON. No explanation, no markdown, no extra text.

RESUME TEXT:
\"\"\"
{resume_text}
\"\"\"

Return EXACTLY this JSON structure:

{{
  "personal_info": {{
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "portfolio_or_github": ""
  }},
  "domain": "",
  "summary": "",
  "total_experience_years": null,
  "skills": {{
    "technical_skills": [],
    "tools_and_technologies": [],
    "soft_skills": [],
    "domain_specific_skills": [],
    "languages_known": []
  }},
  "education": [
    {{
      "degree": "",
      "field_of_study": "",
      "institution": "",
      "year_of_completion": "",
      "grade_or_cgpa": ""
    }}
  ],
  "work_experience": [
    {{
      "job_title": "",
      "company": "",
      "start_date": "",
      "end_date": "",
      "duration": "",
      "responsibilities": [],
      "achievements": []
    }}
  ],
  "projects": [
    {{
      "title": "",
      "description": "",
      "technologies_used": [],
      "outcome": ""
    }}
  ],
  "certifications": [
    {{
      "name": "",
      "issuer": "",
      "year": ""
    }}
  ],
  "awards_and_achievements": [],
  "publications_or_research": [],
  "volunteer_or_extracurricular": [],
  "languages": [],
  "candidate_strength_summary": ""
}}
"""

# ─────────────────────────────────────────────
# CORE: Extract using Ollama model
# ─────────────────────────────────────────────

def extract_with_ai(resume_text: str) -> dict:
    """
    Send the resume text to the AI model and parse the returned JSON.

    temperature=0.0 — deterministic output so extraction is consistent
    num_predict=4096 — allow enough tokens for detailed resume JSON

    Returns an empty dict {} if the AI call fails or JSON is unparseable.
    Callers should always check `if not extracted_data:` before using the result.
    """
    system = (
        "You are a precise resume parser that extracts structured data "
        "from resumes of ALL professional domains. Always return valid JSON only."
    )
    # call_ollama handles retries; clean_json_response strips markdown fences
    raw = call_ollama(system, build_prompt(resume_text), temperature=0.0, num_predict=4096)
    return clean_json_response(raw) if raw else {}

# ─────────────────────────────────────────────
# SAVE NLP OUTPUT
# ─────────────────────────────────────────────

def save_output(data: dict, output_file: Path, stem: str):
    """
    Persist the AI-extracted candidate data in two formats:
      1. JSON  — machine-readable, used by ranking_engine.py
      2. TXT   — human-readable summary for recruiter review

    Uses a temp-file strategy for atomic writes:
      - Writes to .tmp_json / .tmp_txt first.
      - Only renames to the final names after BOTH writes succeed.
      - If anything fails, temp files are deleted so no partial output exists.
    """
    # Final output file paths
    json_file    = output_file.with_suffix(".json")
    summary_file = output_file.with_suffix(".txt")

    # Temporary files written to first (prevents corrupted output on crash/error)
    tmp_json     = output_file.with_suffix(".tmp_json")
    tmp_txt      = output_file.with_suffix(".tmp_txt")

    try:
        # ── Step 1: Write JSON to a temp file ──
        # ensure_ascii=False keeps non-ASCII characters (e.g. accented names) intact
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # ── Step 2: Write a human-readable TXT summary to a temp file ──
        with open(tmp_txt, "w", encoding="utf-8") as f:
            f.write(f"=== NLP EXTRACTION RESULT: {stem} ===\n\n")

            # Use 'or {}' to handle cases where AI returns null for personal_info
            # (some AI models set the field to null instead of an empty object)
            pi = data.get("personal_info") or {}
            f.write(f"NAME             : {pi.get('name', 'N/A')}\n")
            f.write(f"EMAIL            : {pi.get('email', 'N/A')}\n")
            f.write(f"PHONE            : {pi.get('phone', 'N/A')}\n")
            f.write(f"LOCATION         : {pi.get('location', 'N/A')}\n")
            f.write(f"LINKEDIN         : {pi.get('linkedin', 'N/A')}\n")
            f.write(f"PORTFOLIO/GITHUB  : {pi.get('portfolio_or_github', 'N/A')}\n")
            f.write(f"\nDOMAIN           : {data.get('domain', 'N/A')}\n")
            f.write(f"EXPERIENCE (yrs) : {data.get('total_experience_years', 'N/A')}\n")
            f.write(f"\nSUMMARY:\n{data.get('summary', 'N/A')}\n")

            skills = data.get("skills") or {}
            f.write(f"\nSKILLS:\n")
            for category, items in skills.items():
                if items:
                    # str(i) safely converts non-string skill items (e.g. ints) to text
                    f.write(f"  {category.upper()}: {', '.join(str(i) for i in items)}\n")

            education = data.get("education") or []
            f.write(f"\nEDUCATION:\n")
            for edu in education:
                f.write(f"  - {edu.get('degree', '')} in {edu.get('field_of_study', '')} "
                        f"from {edu.get('institution', '')} ({edu.get('year_of_completion', '')})\n")

            experience = data.get("work_experience") or []
            f.write(f"\nWORK EXPERIENCE:\n")
            for exp in experience:
                f.write(f"  - {exp.get('job_title', '')} at {exp.get('company', '')} "
                        f"[{exp.get('start_date', '')} - {exp.get('end_date', '')}]\n")
                for resp in exp.get("responsibilities", [])[:3]:
                    f.write(f"      . {resp}\n")

            projects = data.get("projects") or []
            if projects:
                f.write(f"\nPROJECTS:\n")
                for proj in projects:
                    desc = proj.get('description', '') or ''
                    f.write(f"  - {proj.get('title', '')}: {desc[:100]}...\n")

            certifications = data.get("certifications") or []
            if certifications:
                f.write(f"\nCERTIFICATIONS:\n")
                for cert in certifications:
                    f.write(f"  - {cert.get('name', '')} by {cert.get('issuer', '')} ({cert.get('year', '')})\n")

            awards = data.get("awards_and_achievements") or []
            if awards:
                f.write(f"\nAWARDS & ACHIEVEMENTS:\n")
                for award in awards:
                    f.write(f"  - {award}\n")

            publications = data.get("publications_or_research") or []
            if publications:
                f.write(f"\nPUBLICATIONS / RESEARCH:\n")
                for pub in publications:
                    f.write(f"  - {pub}\n")

            strength = data.get("candidate_strength_summary", "") or ""
            if strength:
                f.write(f"\nCANDIDATE STRENGTH SUMMARY:\n{strength}\n")

        # ── Step 3: Atomically rename temp files to final names ──
        # Only reached if both writes above succeeded — prevents partial outputs
        tmp_json.rename(json_file)
        tmp_txt.rename(summary_file)

    except Exception as e:
        # Clean up temp files so a failed run does not leave behind partial files
        if tmp_json.exists():
            tmp_json.unlink()
        if tmp_txt.exists():
            tmp_txt.unlink()
        raise e  # Re-raise so process_file() can log the error correctly

# ─────────────────────────────────────────────
# PROCESS A SINGLE TXT FILE
# ─────────────────────────────────────────────

def process_file(txt_file: Path, output_path: Path) -> bool:
    """
    Run one .txt resume through the full NLP extraction pipeline.

    Steps:
      1. Skip if _nlp.json already exists (idempotent — safe to re-run).
      2. Read the .txt content.
      3. Call the AI model to extract structured data.
      4. Fall back to a filename-based name if AI didn't find the candidate's name.
      5. Save JSON + TXT output files.

    Returns:
      True  — file was newly processed.
      False — skipped (already done) or extraction failed.
    """
    # Check if this file was already processed — avoids duplicate AI calls
    if (output_path / f"{txt_file.stem}_nlp.json").exists():
        return False

    print(f"> Processing: {txt_file.name}...", end=" ", flush=True)

    try:
        # Read the plain-text resume content
        with open(txt_file, "r", encoding="utf-8") as f:
            resume_text = f.read()

        # Guard against empty files (e.g. OCR produced nothing)
        if not resume_text.strip():
            print("> Empty file, skipping.")
            return False

        # Send to AI and parse the structured JSON response
        extracted_data = extract_with_ai(resume_text)

        if not extracted_data:
            print("> No data extracted.")
            return False

        # Ensure personal_info is a dict even if AI returned null for that field
        personal_info = extracted_data.get("personal_info") or {}
        if not personal_info.get("name") or str(personal_info.get("name", "")).strip() == "":
            # Fall back to using the filename as the candidate identifier
            extracted_data["personal_info"] = personal_info
            extracted_data["personal_info"]["name"] = f"{UNKNOWN_NAME}_{txt_file.stem}"
            print(f"\n  [INFO] Name not found — using filename as identifier.", end=" ", flush=True)

        # Build the output path prefix (suffix is added by save_output)
        output_file = output_path / f"{txt_file.stem}_nlp"
        save_output(extracted_data, output_file, txt_file.stem)

        print(f"> Success  [{extracted_data.get('domain', 'Unknown Domain')}]")
        return True

    except Exception as e:
        print(f"> Failed! {e}")
        return False

# ─────────────────────────────────────────────
# MAIN: INFINITE WATCH LOOP
# ─────────────────────────────────────────────

def run_watcher():
    """
    Poll the output/txt/ folder continuously and run AI extraction on
    any new .txt files found.  Runs forever until Ctrl+C is pressed.
    """
    input_path  = Path(INPUT_FOLDER)
    output_path = Path(OUTPUT_FOLDER)

    # Create directories if they do not exist (first-time setup)
    input_path.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("   NLP LIVE WATCHER STARTED")
    print("=" * 50)
    print(f"> Watching folder : {INPUT_FOLDER}/")
    print(f"> Output folder   : {OUTPUT_FOLDER}/")
    print(f"> Model           : {OLLAMA_MODEL}")
    print(f"> Check interval  : every {WATCH_INTERVAL_SECONDS} seconds")
    print(f"> Press Ctrl+C to stop\n")

    processed_count = 0

    while True:
        try:
            txt_files = list(input_path.glob("*.txt"))
            new_files_found = False

            for txt_file in txt_files:
                is_new = process_file(txt_file, output_path)
                if is_new:
                    processed_count += 1
                    new_files_found = True

            if not new_files_found:
                print(f"\r> Watching... (processed so far: {processed_count}) | waiting for new TXT files...", end="", flush=True)

            time.sleep(WATCH_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print(f"\n\n> Watcher stopped safely.")
            print(f"> Total files processed this session: {processed_count}")
            exit(0)

        except Exception as e:
            print(f"\n> [Watcher Error] {e} — retrying in {WATCH_INTERVAL_SECONDS}s...")
            time.sleep(WATCH_INTERVAL_SECONDS)
            continue


if __name__ == "__main__":
    run_watcher()


async def process_file_async(txt_file: Path, output_path: Path) -> bool:
    """Asynchronous wrapper for process_file to run without blocking the event loop."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, process_file, txt_file, output_path)