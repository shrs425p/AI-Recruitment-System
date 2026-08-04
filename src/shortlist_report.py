import json
from datetime import datetime
from pathlib import Path


def _bucket(score: float) -> str:
    if score >= 75:
        return "Priority interview"
    if score >= 58:
        return "Interview"
    if score >= 40:
        return "Review manually"
    return "Do not schedule"


def _top_items(items, limit=3):
    if not isinstance(items, list):
        return []
    return [str(item) for item in items[:limit] if str(item).strip()]


def build_shortlist_report(ranked: list, jd: dict, top_n: int = 10) -> dict:
    shortlisted = []
    for rank, candidate in enumerate(ranked[:top_n], start=1):
        score = float(candidate.get("total_score") or 0)
        shortlisted.append({
            "rank": rank,
            "candidate_name": candidate.get("candidate_name") or candidate.get("_source_file") or "Unknown",
            "source_file": candidate.get("_source_file", ""),
            "domain": candidate.get("domain", "General"),
            "score": score,
            "confidence": candidate.get("confidence", "Unknown"),
            "decision": _bucket(score),
            "hire_recommendation": candidate.get("hire_recommendation", ""),
            "strengths": _top_items(candidate.get("strengths")),
            "gaps": _top_items(candidate.get("gaps")),
        })

    score_values = [float(c.get("total_score") or 0) for c in ranked]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "report_type": "pre_interview_shortlist",
        "job_description": jd,
        "total_candidates": len(ranked),
        "shortlist_count": len(shortlisted),
        "score_summary": {
            "highest": max(score_values) if score_values else 0,
            "lowest": min(score_values) if score_values else 0,
            "average": round(sum(score_values) / len(score_values), 1) if score_values else 0,
            "priority_interview": sum(1 for score in score_values if score >= 75),
            "interview": sum(1 for score in score_values if 58 <= score < 75),
            "manual_review": sum(1 for score in score_values if 40 <= score < 58),
            "not_recommended": sum(1 for score in score_values if score < 40),
        },
        "shortlisted_candidates": shortlisted,
    }


def save_shortlist_report(ranked: list, jd: dict, output_path: Path, top_n: int = 10) -> dict:
    output_path.mkdir(parents=True, exist_ok=True)
    report = build_shortlist_report(ranked, jd, top_n=top_n)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_file = output_path / f"shortlist_report_{stamp}.json"
    txt_file = output_path / f"shortlist_report_{stamp}.txt"

    json_file.write_text(json.dumps(report, indent=4, ensure_ascii=False), encoding="utf-8")

    lines = [
        "=" * 72,
        "PRE-INTERVIEW SHORTLIST REPORT",
        "=" * 72,
        f"Generated        : {report['generated_at']}",
        f"Job Title        : {jd.get('job_title', 'Open Position')}",
        f"Domain           : {jd.get('domain', 'N/A')}",
        f"Total Candidates : {report['total_candidates']}",
        f"Shortlisted      : {report['shortlist_count']}",
        "",
        "Score Summary",
        "-" * 72,
    ]
    summary = report["score_summary"]
    lines.extend([
        f"Highest score     : {summary['highest']}",
        f"Average score     : {summary['average']}",
        f"Priority interview: {summary['priority_interview']}",
        f"Interview         : {summary['interview']}",
        f"Manual review     : {summary['manual_review']}",
        f"Not recommended   : {summary['not_recommended']}",
        "",
        "Shortlisted Candidates",
        "-" * 72,
    ])

    for candidate in report["shortlisted_candidates"]:
        lines.extend([
            f"#{candidate['rank']} {candidate['candidate_name']} ({candidate['source_file']})",
            f"Score      : {candidate['score']}/100",
            f"Decision   : {candidate['decision']}",
            f"Confidence : {candidate['confidence']}",
            f"Domain     : {candidate['domain']}",
        ])
        if candidate["strengths"]:
            lines.append("Strengths  : " + "; ".join(candidate["strengths"]))
        if candidate["gaps"]:
            lines.append("Gaps       : " + "; ".join(candidate["gaps"]))
        lines.append("")

    txt_file.write_text("\n".join(lines), encoding="utf-8")

    report["files"] = {"json": json_file.name, "txt": txt_file.name}
    return report
