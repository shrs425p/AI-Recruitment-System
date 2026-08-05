import json
from datetime import datetime

from nlp_extractor import save_output
from pdf_to_txt import clean_text, extract_direct_text
from ranking_engine import WEIGHTS, score_candidate
from scheduling import assign_slots_to_candidates, generate_ics


def test_pdf_text_cleaning():
    raw_text = "Hello\x00World!\r\n\n\n\nThis is a    test  ."
    cleaned = clean_text(raw_text)
    assert "\x00" not in cleaned
    assert "\r" not in cleaned
    assert "    " not in cleaned
    assert cleaned == "HelloWorld!\n\nThis is a test ."


def test_pdf_extract_direct_text_handles_nonexistent():
    # Direct extraction should fail gracefully and return empty string
    text = extract_direct_text("nonexistent_file_path.pdf")
    assert text == ""


def test_nlp_save_output_atomic_write_creates_files(tmp_path):
    output_prefix = tmp_path / "candidate_test"
    stem = "candidate_test"
    data = {
        "personal_info": {
            "name": "Jane Smith",
            "email": "jane@example.com"
        },
        "domain": "Software Engineering",
        "total_experience_years": 5,
        "skills": {
            "technical_skills": ["Python", "Flask"]
        }
    }

    save_output(data, output_prefix, stem)

    json_file = output_prefix.with_suffix(".json")
    txt_file = output_prefix.with_suffix(".txt")

    assert json_file.exists()
    assert txt_file.exists()

    with open(json_file, encoding="utf-8") as f:
        loaded_json = json.load(f)
    assert loaded_json["personal_info"]["name"] == "Jane Smith"

    with open(txt_file, encoding="utf-8") as f:
        loaded_txt = f.read()
    assert "NAME             : Jane Smith" in loaded_txt
    assert "EMAIL            : jane@example.com" in loaded_txt


def test_ranking_engine_score_candidate_and_clamping(monkeypatch):
    candidate = {
        "personal_info": {"name": "Bob Martin"},
        "domain": "DevOps",
        "total_experience_years": 3,
        "skills": {
            "technical_skills": ["Docker", "Kubernetes", "CI/CD"]
        }
    }
    jd = {
        "job_title": "DevOps Engineer",
        "domain": "DevOps"
    }

    # Mock call_ai to return high out-of-bounds scores to test clamping
    def mock_call_ai(prompt):
        return {
            "candidate_name": "Bob Martin",
            "scores": {
                "domain_match": {"score": 500, "max": WEIGHTS["domain_match"], "reason": "Good"},
                "skills_match": {"score": 300, "max": WEIGHTS["skills_match"], "reason": "Great"},
                "experience_years": {"score": 200, "max": WEIGHTS["experience_years"], "reason": "Exp"},
                "education": {"score": 150, "max": WEIGHTS["education"], "reason": "Edu"},
                "certifications": {"score": 100, "max": WEIGHTS["certifications"], "reason": "Cert"}
            }
        }

    monkeypatch.setattr("ranking_engine.call_ai", mock_call_ai)

    result = score_candidate(candidate, jd)

    assert result is not None
    assert result["candidate_name"] == "Bob Martin"
    # Verify sub-scores are clamped to their maximum weights
    assert result["scores"]["domain_match"]["score"] == WEIGHTS["domain_match"]
    assert result["scores"]["skills_match"]["score"] == WEIGHTS["skills_match"]
    assert result["scores"]["experience_years"]["score"] == WEIGHTS["experience_years"]
    assert result["scores"]["education"]["score"] == WEIGHTS["education"]
    assert result["scores"]["certifications"]["score"] == WEIGHTS["certifications"]
    assert result["total_score"] == 100
    assert result["percentage"] == 100.0
    assert result["hire_recommendation"] == "Strongly Recommend"


def test_scheduling_slot_rotation_assignment():
    candidates = [
        {"candidate_name": "Alice", "total_score": 90, "_source_file": "alice_res.pdf"},
        {"candidate_name": "Bob", "total_score": 80, "_source_file": "bob_res.pdf"},
        {"candidate_name": "Charlie", "total_score": 70, "_source_file": "charlie_res.pdf"}
    ]
    slots = [
        datetime(2026, 3, 1, 10, 0),
        datetime(2026, 3, 1, 11, 0),
        datetime(2026, 3, 1, 12, 0)
    ]

    scheduled = assign_slots_to_candidates(candidates, slots, slots_per_candidate=3)

    assert len(scheduled) == 3
    # Check that rotation worked
    # Alice should receive 10:00 as her first slot option (index 0 offset)
    assert scheduled[0]["offered_slots"][0] == "2026-03-01 10:00"
    # Bob should receive 11:00 as his first slot option (index 1 offset)
    assert scheduled[1]["offered_slots"][0] == "2026-03-01 10:00" # sorted chronologically!
    # They should both receive 3 offered slots
    assert len(scheduled[0]["offered_slots"]) == 3
    assert len(scheduled[1]["offered_slots"]) == 3


def test_scheduling_generate_ics_invite(tmp_path):
    entry = {
        "candidate_name": "Dave Rogers",
        "source_file": "dave_res.pdf",
        "rank": 4,
        "score": 75,
        "status": "CONFIRMED",
        "selected_slot": "2026-03-05 14:30"
    }

    ics_file = generate_ics(
        entry=entry,
        output_path=tmp_path,
        hr_name="HR Specialist",
        job_title="Frontend Lead",
        stamp="20260305",
        hr_email="specialist@company.com"
    )

    assert ics_file is not None
    assert ics_file.exists()
    assert "Dave_Rogers" in ics_file.name

    with open(ics_file, "rb") as f:
        content = f.read().decode("utf-8")

    assert "SUMMARY:Interview — Dave Rogers for Frontend Lead" in content.replace("\r\n", "")
    assert "ORGANIZER:MAILTO:specialist@company.com" in content.replace("\r\n", "")
