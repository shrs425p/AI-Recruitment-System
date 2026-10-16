import json

import src.report_generator as rg


def test_calculate_combined_score():
    # 40% ranking (80 -> 32) + 60% interview (90 -> 54) = 86.0
    transcript = {"ranking_score": 80, "percentage": 90}
    assert rg.calculate_combined_score(transcript) == 86.0

    # 40% of 100 (40) + 60% of 50 (30) = 70.0
    transcript2 = {"ranking_score": 100, "percentage": 50}
    assert rg.calculate_combined_score(transcript2) == 70.0


def test_load_interview_transcripts(tmp_path):
    empty_list = rg.load_interview_transcripts(tmp_path)
    assert empty_list == []

    # Create dummy interview files
    f1 = tmp_path / "interview_cand1.json"
    f2 = tmp_path / "interview_cand2.json"
    f1.write_text(json.dumps({"candidate_name": "Cand 1"}), encoding="utf-8")
    f2.write_text(json.dumps({"candidate_name": "Cand 2"}), encoding="utf-8")

    loaded = rg.load_interview_transcripts(tmp_path)
    assert len(loaded) == 2
    assert loaded[0]["candidate_name"] == "Cand 1"
    assert loaded[0]["_source_file"] == "interview_cand1.json"


def test_generate_ai_report_mocked(monkeypatch):
    mock_report = {
        "overall_summary": "Strong candidate",
        "technical_assessment": "Excellent Python and ML skills",
        "behavioral_assessment": "Good communicator",
        "key_strengths": ["Python", "Fast Learner"],
        "key_gaps": [],
        "proctoring_remarks": "Clean session",
        "risk_level": "LOW",
        "combined_score": 85,
        "combined_score_explanation": "Solid performance across all rounds",
        "hire_recommendation": "RECOMMEND",
        "hire_justification": "Candidate meets requirements",
        "suggested_next_steps": ["Schedule final offer call"],
    }

    monkeypatch.setattr(rg, "call_ai", lambda sys_msg, usr_msg: json.dumps(mock_report))

    transcript = {
        "candidate_name": "Bob Smith",
        "job_title": "Senior Engineer",
        "domain": "Engineering",
        "ranking_score": 85,
        "total_score": 8,
        "max_score": 10,
        "percentage": 80,
        "technical_score": 5,
        "technical_max": 5,
        "technical_pct": 100,
        "behavioral_score": 3,
        "behavioral_max": 5,
        "behavioral_pct": 60,
        "proctoring_status": "CLEAN",
        "flagged_count": 0,
        "responses": [
            {
                "question": "What is Python GIL?",
                "answer": "Global Interpreter Lock",
                "type": "TECHNICAL",
                "topic": "Python",
                "score": 5,
                "evaluation": {"feedback": "Spot on", "weak_points": [], "strong_points": ["GIL"]},
            }
        ],
    }

    report = rg.generate_ai_report(transcript)
    assert report["hire_recommendation"] == "RECOMMEND"
    assert "Strong candidate" in report["overall_summary"]


def test_save_report_txt_and_json(tmp_path):
    transcript = {
        "candidate_name": "Alice Wonder",
        "job_title": "Backend Dev",
        "domain": "Python",
        "ranking_score": 82,
        "percentage": 88,
        "total_score": 44,
        "max_score": 50,
        "technical_score": 25,
        "technical_max": 25,
        "technical_pct": 100,
        "behavioral_score": 19,
        "behavioral_max": 25,
        "behavioral_pct": 76,
        "proctoring_status": "CLEAN",
        "flagged_count": 0,
        "responses": [],
    }
    ai_report = {
        "overall_summary": "Top performer",
        "technical_assessment": "Flawless",
        "behavioral_assessment": "Great attitude",
        "key_strengths": ["Architecture"],
        "key_gaps": [],
        "proctoring_remarks": "No issues",
        "risk_level": "LOW",
        "hire_recommendation": "STRONGLY RECOMMEND",
        "hire_justification": "Best in class",
        "suggested_next_steps": ["Offer"],
    }

    rg.save_report_txt(transcript, ai_report, 85.6, tmp_path)
    txt_files = list(tmp_path.glob("report_Alice_Wonder_*.txt"))
    assert len(txt_files) == 1
    content = txt_files[0].read_text(encoding="utf-8")
    assert "Alice Wonder" in content
    assert "STRONGLY RECOMMEND" in content
