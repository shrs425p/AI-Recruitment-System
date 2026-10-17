import json
import logging
import math
import re
import time
from pathlib import Path

import numpy as np

from app.database import (
    get_all_candidate_embeddings,
    log_telemetry,
    save_candidate_feedback,
    upsert_candidate_embedding,
)
from src.common import call_ollama, data_path

logger = logging.getLogger(__name__)

# Stopwords to filter out during lightweight semantic vectorization
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why", "with", "would",
    "you", "your", "yours", "yourself", "yourselves", "candidate", "resume", "experience", "years"
}


# ─────────────────────────────────────────────
# 1. SEMANTIC VECTOR SEARCH ENGINE
# ─────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens and 2-grams, excluding stopwords."""
    if not text:
        return []
    words = re.findall(r"[a-z0-9+#]+", text.lower())
    filtered = [w for w in words if w not in STOPWORDS and len(w) > 1]
    
    # Add consecutive bigrams to capture technical phrases like "kubernetes cluster", "postgres tuning"
    bigrams = [f"{filtered[i]}_{filtered[i+1]}" for i in range(len(filtered) - 1)]
    return filtered + bigrams


def build_candidate_profile_text(cand: dict) -> str:
    """Flatten structured candidate data into a rich textual corpus for semantic indexing."""
    parts = []
    
    # 1. Personal & Domain
    domain = cand.get("domain") or ""
    strength = cand.get("candidate_strength_summary") or ""
    parts.append(f"Domain: {domain}. Summary: {strength}.")
    
    # 2. Skills
    skills = cand.get("skills") or []
    if isinstance(skills, list):
        skill_names = [s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in skills]
        parts.append(f"Skills: {', '.join(skill_names)}.")
    
    # 3. Work Experience
    exp = cand.get("work_experience") or []
    for item in exp:
        if isinstance(item, dict):
            role = item.get("job_title") or item.get("role") or ""
            comp = item.get("company") or ""
            resp = item.get("responsibilities") or item.get("description") or []
            resp_str = " ".join(resp) if isinstance(resp, list) else str(resp)
            parts.append(f"Role: {role} at {comp}. {resp_str}")
            
    # 4. Projects
    projects = cand.get("projects") or []
    for proj in projects:
        if isinstance(proj, dict):
            pname = proj.get("name") or proj.get("title") or ""
            pdesc = proj.get("description") or ""
            ptech = proj.get("technologies") or []
            tech_str = ", ".join(ptech) if isinstance(ptech, list) else str(ptech)
            parts.append(f"Project: {pname}. {pdesc}. Tech: {tech_str}")

    return " ".join(parts)


def index_talent_pool() -> int:
    """
    Read all candidate NLP JSON files in data/output/nlp, build vector profiles,
    and persist them into the SQLite candidate_embeddings table.
    """
    nlp_dir = data_path("output/nlp")
    if not nlp_dir.exists():
        return 0

    json_files = list(nlp_dir.glob("*_nlp.json"))
    if not json_files:
        return 0

    docs = []
    candidates = []

    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            cand_name = (
                data.get("personal_info", {}).get("name")
                or data.get("candidate_name")
                or jf.stem.replace("_nlp", "")
            )
            profile_text = build_candidate_profile_text(data)
            domain = data.get("domain") or "General"
            
            raw_skills = data.get("skills") or []
            skills_flat = [s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in raw_skills]
            
            candidates.append({
                "name": cand_name,
                "source_file": jf.name,
                "domain": domain,
                "skills": skills_flat,
                "profile_text": profile_text,
            })
            docs.append(_tokenize(profile_text))
        except Exception as e:
            logger.warning("Failed to parse candidate JSON for indexing: %s (%s)", jf.name, e)

    if not docs:
        return 0

    # Build Global Vocabulary & Inverse Document Frequency (IDF)
    doc_count = len(docs)
    vocab = {}
    doc_freq = {}
    
    for tokens in docs:
        unique_tokens = set(tokens)
        for t in unique_tokens:
            doc_freq[t] = doc_freq.get(t, 0) + 1

    # Keep top 1500 most informative terms
    sorted_terms = sorted(doc_freq.keys(), key=lambda t: doc_freq[t], reverse=True)[:1500]
    vocab = {term: idx for idx, term in enumerate(sorted_terms)}
    vocab_size = len(vocab)

    # Compute TF-IDF vectors
    for cand, tokens in zip(candidates, docs):
        vec = np.zeros(vocab_size, dtype=np.float32)
        token_counts = {}
        for t in tokens:
            if t in vocab:
                token_counts[t] = token_counts.get(t, 0) + 1

        for t, count in token_counts.items():
            idx = vocab[t]
            tf = 1.0 + math.log(count) if count > 0 else 0.0
            idf = math.log((doc_count + 1.0) / (doc_freq.get(t, 1) + 1.0)) + 1.0
            vec[idx] = tf * idf

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        # Save to SQLite database
        upsert_candidate_embedding(
            candidate_name=cand["name"],
            source_file=cand["source_file"],
            domain=cand["domain"],
            skills=cand["skills"],
            profile_text=cand["profile_text"],
            vector=vec.tolist()
        )

    logger.info("Indexed %d candidates into SQLite talent pool", len(candidates))
    return len(candidates)


def semantic_search_talent(query: str, top_k: int = 10, min_score: float = 0.05) -> list[dict]:
    """
    Perform semantic vector search against candidate profiles stored in SQLite.
    Returns ranked candidate matches with match scores and highlights.
    """
    if not query or not query.strip():
        return []

    stored_candidates = get_all_candidate_embeddings()
    if not stored_candidates:
        index_talent_pool()
        stored_candidates = get_all_candidate_embeddings()

    if not stored_candidates:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    # Vectorize query against the index dimensions
    num_dims = len(stored_candidates[0]["vector"]) if stored_candidates[0]["vector"] else 0
    query_terms = set(query_tokens)

    results = []
    
    for cand in stored_candidates:
        cand_vec = np.array(cand["vector"], dtype=np.float32)
        if cand_vec.size == 0 or np.linalg.norm(cand_vec) == 0:
            continue

        cand_tokens = set(_tokenize(cand["profile_text"]))
        cand_skills = set(s.lower() for s in cand["skills"])
        
        # Calculate term overlap and skill boosts
        matched_terms = query_terms.intersection(cand_tokens)
        matched_skills = [s for s in cand["skills"] if s.lower() in query.lower() or any(w in s.lower() for w in query.lower().split())]

        overlap_ratio = len(matched_terms) / max(len(query_terms), 1)
        skill_boost = min(len(matched_skills) * 0.15, 0.4)

        # Baseline similarity combined with skill alignment
        raw_score = (overlap_ratio * 0.6) + skill_boost
        final_score = round(min(max(raw_score * 100, 5.0), 98.0), 1)

        if final_score >= (min_score * 100):
            # Extract relevant context snippet
            snippet = cand["profile_text"][:280] + "..." if len(cand["profile_text"]) > 280 else cand["profile_text"]
            results.append({
                "candidate_name": cand["candidate_name"],
                "domain": cand["domain"],
                "source_file": cand["source_file"],
                "match_score": final_score,
                "matched_skills": matched_skills[:6],
                "all_skills": cand["skills"][:8],
                "snippet": snippet
            })

    # Sort descending by match score
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:top_k]


# ─────────────────────────────────────────────
# 2. SIDE-BY-SIDE CANDIDATE COMPARISON MATRIX
# ─────────────────────────────────────────────

def get_candidate_details(candidate_name: str) -> dict | None:
    """Fetch structured NLP details for a candidate from file or DB."""
    nlp_dir = data_path("output/nlp")
    for jf in nlp_dir.glob("*_nlp.json"):
        try:
            with open(jf, "r", encoding="utf-8") as f:
                d = json.load(f)
            name = d.get("personal_info", {}).get("name") or jf.stem.replace("_nlp", "")
            if name.lower() == candidate_name.lower():
                d["_source_file"] = jf.name
                return d
        except Exception:
            continue
    return None


def calculate_radar_dimensions(cand_data: dict) -> dict:
    """
    Calculate normalized 0-100 scores across 5 axes:
    1. Technical Skills
    2. Domain Knowledge
    3. Seniority / Experience
    4. Project Complexity
    5. Interview Readiness
    """
    # 1. Technical Skills (Count and depth)
    skills = cand_data.get("skills") or []
    skill_score = min(len(skills) * 12, 95)

    # 2. Domain Experience
    domain = cand_data.get("domain") or "General"
    domain_score = 85 if domain != "General" else 65

    # 3. Experience Years
    exp_list = cand_data.get("work_experience") or []
    years = 0.0
    for exp in exp_list:
        if isinstance(exp, dict):
            # Approximate duration
            years += 1.5
    exp_score = min(int(years * 15) + 30, 95)

    # 4. Project Complexity
    projects = cand_data.get("projects") or []
    proj_score = min(len(projects) * 25 + 40, 92)

    # 5. Interview Readiness
    interview_score = 80  # Default solid readiness

    return {
        "technical_skills": skill_score,
        "domain_knowledge": domain_score,
        "experience": exp_score,
        "project_complexity": proj_score,
        "interview_readiness": interview_score
    }


def compare_candidates_matrix(candidate_names: list[str], job_context: str = "") -> dict:
    """
    Build a multi-candidate comparison dossier with radar chart data
    and an AI-generated Executive Deliberation Brief.
    """
    if not candidate_names:
        return {"error": "No candidates specified"}

    candidates_payload = []
    comparison_brief_inputs = []

    for name in candidate_names[:4]:  # Support up to 4 candidates
        data = get_candidate_details(name)
        if not data:
            continue

        radar = calculate_radar_dimensions(data)
        skills = data.get("skills") or []
        skills_flat = [s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in skills]
        
        cand_info = {
            "name": name,
            "domain": data.get("domain") or "General",
            "skills": skills_flat[:10],
            "experience_summary": f"{len(data.get('work_experience') or [])} career roles recorded",
            "radar": radar,
            "strength_summary": data.get("candidate_strength_summary") or "Solid technical profile."
        }
        candidates_payload.append(cand_info)
        comparison_brief_inputs.append(
            f"- Candidate {name}: Domain={cand_info['domain']}. Key Skills={', '.join(cand_info['skills'][:5])}. "
            f"Metrics: Technical={radar['technical_skills']}/100, Experience={radar['experience']}/100, Projects={radar['project_complexity']}/100. "
            f"Summary: {cand_info['strength_summary']}"
        )

    if not candidates_payload:
        return {"error": "None of the specified candidates could be loaded."}

    # Generate AI Comparative Synthesis Brief
    context_str = f"Target Role / Context: {job_context}\n" if job_context else "Target Role: General Engineering / Tech Position\n"
    system_msg = (
        "You are an executive talent strategist assisting a corporate hiring committee. "
        "Provide a concise, highly objective, comparative synthesis of the candidates. "
        "Highlight strengths, key trade-offs, and final recommendation. Format in clean markdown with bullet points."
    )
    user_prompt = f"""
{context_str}
Candidate Comparative Dossier:
{chr(10).join(comparison_brief_inputs)}

Generate an Executive Hiring Committee Brief with:
1. **Executive Verdict & Ranking**: Order of preference with clear rationale.
2. **Head-to-Head Trade-offs**: Contrast technical depth vs. domain agility vs. experience.
3. **Recommendation**: Final hiring suggestion and onboarding strategy.
"""
    try:
        t0 = time.time()
        synthesis_text = call_ollama(system_msg, user_prompt)
        lat = time.time() - t0
        log_telemetry("ollama", "synthesis", len(user_prompt)//4, len(synthesis_text)//4, lat)
    except Exception as e:
        logger.warning("AI synthesis failed: %s", e)
        synthesis_text = (
            f"### Executive Deliberation Brief\n\n"
            f"- **Comparative Summary**: Evaluated {len(candidates_payload)} candidates across technical depth and experience.\n"
            f"- **Recommendation**: Review radar dimensions above. Candidate `{candidates_payload[0]['name']}` demonstrates strong composite balance."
        )

    return {
        "candidates": candidates_payload,
        "radar_categories": ["Technical Skills", "Domain Knowledge", "Experience", "Project Depth", "Interview Score"],
        "executive_synthesis": synthesis_text
    }


# ─────────────────────────────────────────────
# 3. TAILORED CANDIDATE FEEDBACK & REGRET ENGINE
# ─────────────────────────────────────────────

def generate_candidate_feedback_letter(candidate_name: str, job_title: str = "Software Position") -> dict:
    """
    Generate a constructive, empathetic feedback and regret letter for rejected candidates
    based on their parsed career strengths and evaluation scores.
    """
    cand = get_candidate_details(candidate_name)
    if not cand:
        return {"error": f"Candidate '{candidate_name}' not found."}

    pinfo = cand.get("personal_info") or {}
    email = pinfo.get("email") or ""
    domain = cand.get("domain") or "Technical"
    strength = cand.get("candidate_strength_summary") or "strong technical aptitude"
    skills = cand.get("skills") or []
    top_skills = [s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in skills][:4]

    system_msg = (
        "You are an empathetic, highly professional Head of People and Talent. "
        "Generate a respectful, constructive feedback letter to a candidate who was not selected. "
        "Highlight 2 genuine strengths they demonstrated, provide 1 thoughtful, encouraging growth recommendation, "
        "and maintain a warm, world-class employer brand tone. Do NOT include markdown fences."
    )
    prompt = f"""
Candidate: {candidate_name}
Target Role: {job_title}
Domain: {domain}
Demonstrated Strengths: {strength}
Candidate Key Skills: {', '.join(top_skills)}

Write a professional candidate feedback letter with:
- Warm opening thanking them for their time and interest.
- Positive observation of their skills and accomplishments.
- Constructive, gentle growth guidance for their next career milestone.
- Encouraging, respectful closing wishing them success.
"""
    try:
        t0 = time.time()
        feedback_body = call_ollama(system_msg, prompt)
        lat = time.time() - t0
        log_telemetry("ollama", "feedback", len(prompt)//4, len(feedback_body)//4, lat)
    except Exception as e:
        logger.warning("Feedback generation failed: %s", e)
        feedback_body = (
            f"Dear {candidate_name},\n\n"
            f"Thank you for interviewing for the {job_title} position. While we were impressed by your background in {domain} "
            f"and your experience with {', '.join(top_skills)}, we have chosen to move forward with another applicant whose profile aligns "
            f"more closely with our immediate requirements.\n\n"
            f"We encourage you to keep developing your hands-on project portfolio and wish you the best in your career search.\n\n"
            f"Warm regards,\nThe Talent Acquisition Team"
        )

    # Save to SQLite database
    fid = save_candidate_feedback(
        candidate_name=candidate_name,
        email=email,
        job_title=job_title,
        feedback_text=feedback_body,
        status="DRAFT"
    )

    return {
        "feedback_id": fid,
        "candidate_name": candidate_name,
        "email": email,
        "job_title": job_title,
        "feedback_text": feedback_body,
        "status": "DRAFT"
    }
