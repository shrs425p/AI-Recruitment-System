"""
test_nlp.py - test suite for NLP entity extraction, skills taxonomy parsing,
AI provider routing with resilience fallbacks, and robust LLM JSON parsing sanitizers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.provider_router as pr
from src.common import clean_json_response
from src.nlp_extractor import build_prompt, extract_with_ai, save_output


class TestJsonCleaningAndSanitization:
    """Tests the JSON sanitization engine handling malformed LLM outputs and markdown blocks."""

    def test_clean_json_accepts_valid_json_string(self):
        raw = '{"candidate_name": "Ada Lovelace", "years_experience": 10}'
        parsed = clean_json_response(raw)
        assert parsed["candidate_name"] == "Ada Lovelace"
        assert parsed["years_experience"] == 10

    def test_clean_json_strips_markdown_code_fences(self):
        fenced = """```json
        {
            "skills": ["Python", "Flask", "Docker"],
            "education": [{"degree": "Bachelor of Science"}]
        }
        ```"""
        parsed = clean_json_response(fenced)
        assert "Python" in parsed["skills"]
        assert parsed["education"][0]["degree"] == "Bachelor of Science"

    def test_clean_json_extracts_embedded_json_from_conversational_text(self):
        text = 'Here is the parsed resume data in JSON format: {"name": "Grace Hopper", "score": 99} Hope this helps!'
        parsed = clean_json_response(text)
        assert parsed["name"] == "Grace Hopper"
        assert parsed["score"] == 99

    def test_clean_json_repairs_trailing_commas(self):
        broken = """
        {
            "technical_skills": ["Python", "SQL",],
            "certifications": ["AWS Solutions Architect",],
        }
        """
        parsed = clean_json_response(broken)
        assert parsed["technical_skills"] == ["Python", "SQL"]
        assert parsed["certifications"] == ["AWS Solutions Architect"]


class TestNlpEntityExtraction:
    """Tests structured candidate profile extraction from resume plain text."""

    def test_nlp_build_prompt_includes_text(self):
        prompt = build_prompt("Sample candidate resume content for software developer.")
        assert "Sample candidate resume content" in prompt
        assert "JSON" in prompt

    def test_nlp_extractor_returns_structured_schema(self, monkeypatch: pytest.MonkeyPatch):
        mock_output = {
            "name": "Alan Turing",
            "email": "alan@example.com",
            "phone": "+1 555-0100",
            "total_experience_years": 8.0,
            "skills": ["Cryptography", "Algorithms", "Mathematics", "Python"],
            "education": [{"degree": "PhD", "institution": "Cambridge"}],
            "domain": "Computer Science",
        }

        called_kwargs = {}
        def mock_call_ollama(sys_msg, usr_msg, *args, **kwargs):
            called_kwargs.update(kwargs)
            return json.dumps(mock_output)

        monkeypatch.setattr("src.nlp_extractor.call_ollama", mock_call_ollama)

        sample_resume_text = (
            "Alan Turing\nEmail: alan@example.com\n"
            "PhD in Mathematics from Cambridge. 8 years researching cryptography and algorithms."
        )

        result = extract_with_ai(sample_resume_text)
        assert result is not None
        assert result["name"] == "Alan Turing"
        assert result["total_experience_years"] == 8.0
        assert "Cryptography" in result["skills"]
        assert result["education"][0]["degree"] == "PhD"
        assert called_kwargs.get("format") == "json"
        assert called_kwargs.get("think") is False

    def test_nlp_save_output_creates_atomic_files(self, tmp_path: Path):
        data = {
            "name": "Claude Shannon",
            "domain": "Information Theory",
            "skills": {"technical_skills": ["Boolean Logic", "Information Theory"]},
            "experience": [{"role": "Researcher", "years": 10}],
            "candidate_strength_summary": "Father of Information Theory.",
        }
        out_base = tmp_path / "resume_shannon_nlp"
        save_output(data, out_base, "resume_shannon")

        json_out = out_base.with_suffix(".json")
        txt_out = out_base.with_suffix(".txt")

        assert json_out.exists()
        assert txt_out.exists()
        loaded = json.loads(json_out.read_text(encoding="utf-8"))
        assert loaded["name"] == "Claude Shannon"


class TestAiProviderRouter:
    """Tests AI provider dispatch, failover routing, and configuration error handling."""

    def test_key_is_valid_rejects_placeholders_and_accepts_valid(self):
        router = pr.ProviderRouter()
        assert router._key_is_valid({"name": "anthropic", "key": "sk-ant-..."}) is False
        assert router._key_is_valid({"name": "openai", "key": "sk-..."}) is False
        assert router._key_is_valid({"name": "anthropic", "key": "sk-ant-live-real-key-12345"}) is True
        assert router._key_is_valid({"name": "ollama_cloud", "key": ""}) is True

    def test_validate_endpoint_enforces_scheme(self):
        pr._validate_endpoint("https://api.openai.com/v1")
        pr._validate_endpoint("http://127.0.0.1:11434")

        with pytest.raises(RuntimeError, match="Plain HTTP provider endpoints are only allowed for local Ollama"):
            pr._validate_endpoint("http://api.remote-llm.com/v1")

        with pytest.raises(RuntimeError, match="Unsupported provider endpoint scheme"):
            pr._validate_endpoint("ftp://example.com")


class TestThinkingConfiguration:
    """Tests the task-based AI reasoning and thinking controls across NLP and Interview modules."""

    def test_thinking_settings_defaults(self):
        import config
        assert getattr(config, "AI_THINKING_NLP", None) is False
        assert getattr(config, "AI_THINKING_INTERVIEW", None) is True

    def test_extract_with_ai_respects_custom_thinking_setting(self, monkeypatch: pytest.MonkeyPatch):
        import config
        from src.nlp_extractor import extract_with_ai

        captured = {}
        def mock_call(sys_msg, usr_msg, *args, **kwargs):
            captured.update(kwargs)
            return '{"name": "Ada Lovelace"}'

        monkeypatch.setattr("src.nlp_extractor.call_ollama", mock_call)

        # Toggle to True
        monkeypatch.setattr(config, "AI_THINKING_NLP", True)
        res = extract_with_ai("Sample resume")
        assert res["name"] == "Ada Lovelace"
        assert captured.get("think") is True
        assert captured.get("format") == "json"

        # Toggle to False
        monkeypatch.setattr(config, "AI_THINKING_NLP", False)
        extract_with_ai("Sample resume")
        assert captured.get("think") is False

    def test_report_generator_uses_interview_thinking_setting(self, monkeypatch: pytest.MonkeyPatch):
        import config
        from src.report_generator import call_ai

        captured = {}
        def mock_call(sys_msg, usr_msg, *args, **kwargs):
            captured.update(kwargs)
            return "Evaluation text"

        monkeypatch.setattr("src.report_generator.call_ollama", mock_call)

        # Default is True
        call_ai("system prompt", "user prompt")
        assert captured.get("think") is True

        # Toggle to False
        monkeypatch.setattr(config, "AI_THINKING_INTERVIEW", False)
        call_ai("system prompt", "user prompt")
        assert captured.get("think") is False
    def test_interview_bot_uses_interview_thinking_setting(self, monkeypatch: pytest.MonkeyPatch):
        import config
        from src.interview_bot import call_ai

        captured = {}
        def mock_call(sys_msg, usr_msg, *args, **kwargs):
            captured.update(kwargs)
            return "Interview question"

        monkeypatch.setattr("src.interview_bot.call_ollama", mock_call)

        # Default is True
        call_ai("system prompt", "user prompt")
        assert captured.get("think") is True

        # Toggle to False
        monkeypatch.setattr(config, "AI_THINKING_INTERVIEW", False)
        call_ai("system prompt", "user prompt")
        assert captured.get("think") is False


class TestNlpHardeningAndHeuristics:
    """Tests contact information restoration, heuristic fallback parsing, and polymorphic schema handling."""

    def test_nlp_restores_contact_info_when_cloud_redacts(self):
        from src.nlp_extractor import restore_contact_info

        sample_resume = (
            "Diana Prince\n"
            "Email: diana.prince@themyscira.gov\n"
            "Phone: +1 555-738-9201\n"
            "LinkedIn: https://linkedin.com/in/dianaprince\n"
            "GitHub: https://github.com/dianaprince\n\n"
            "Security Analyst with 5 years experience in threat modeling and cryptography."
        )

        redacted_ai_output = {
            "personal_info": {
                "name": "Diana Prince",
                "email": "[EMAIL_REDACTED]",
                "phone": "[PHONE_REDACTED]",
                "location": "",
                "linkedin": "",
                "portfolio_or_github": "",
            },
            "domain": "Cybersecurity",
            "total_experience_years": 5.0,
        }

        restored = restore_contact_info(redacted_ai_output, sample_resume)
        assert restored["personal_info"]["email"] == "diana.prince@themyscira.gov"
        assert restored["personal_info"]["phone"] == "+1 555-738-9201"
        assert restored["personal_info"]["linkedin"] == "https://linkedin.com/in/dianaprince"
        assert restored["personal_info"]["portfolio_or_github"] == "https://github.com/dianaprince"

    def test_extract_with_heuristics_full_pipeline(self):
        from src.nlp_extractor import extract_with_heuristics

        sample_resume = (
            "Bruce Wayne\n"
            "Email: bwayne@wayneenterprises.com\n"
            "Phone: (555) 928-1029\n"
            "GitHub: https://github.com/bwayne\n\n"
            "Lead Software Architect with 8 years of experience building secure distributed systems.\n"
            "Core competencies: Python, Go, Docker, Kubernetes, AWS, PostgreSQL, Redis, Microservices.\n"
            "Education: M.Tech in Computer Engineering from Gotham University."
        )

        data = extract_with_heuristics(sample_resume, "bruce_wayne")
        assert data["personal_info"]["name"] == "Bruce Wayne"
        assert data["personal_info"]["email"] == "bwayne@wayneenterprises.com"
        assert data["personal_info"]["phone"] == "(555) 928-1029"
        assert data["domain"] in {"Software Engineering", "Cloud & DevOps"}
        assert data["total_experience_years"] == 8.0
        assert "Python" in data["skills"]["technical_skills"]
        assert "Kubernetes" in data["skills"]["technical_skills"]
        assert any(e["degree"] == "M.Tech" for e in data["education"])

    def test_extract_with_ai_passes_token_budget_and_temperature(self, monkeypatch: pytest.MonkeyPatch):
        from src.nlp_extractor import extract_with_ai

        captured = {}
        def mock_call_ollama(sys_msg, usr_msg, *args, **kwargs):
            captured.update(kwargs)
            return json.dumps({"personal_info": {"name": "Test Candidate"}})

        monkeypatch.setattr("src.nlp_extractor.call_ollama", mock_call_ollama)

        res = extract_with_ai("Sample resume text")
        assert res["personal_info"]["name"] == "Test Candidate"
        assert captured.get("temperature") == 0.0
        assert captured.get("num_predict") == 4096
        assert captured.get("format") == "json"

    def test_save_output_handles_polymorphic_schema(self, tmp_path: Path):
        from src.nlp_extractor import save_output

        polymorphic_data = {
            "personal_info": {
                "name": "Poly Dev",
                "email": "poly@example.com",
            },
            "domain": "Software",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "education": ["B.S. in Computer Science (2020)"],
            "work_experience": ["Software Engineer at TechCorp (2020-2024)"],
            "projects": ["Distributed Cache in Go"],
            "certifications": ["AWS Certified Developer"],
        }

        out_base = tmp_path / "poly_dev_nlp"
        save_output(polymorphic_data, out_base, "poly_dev")

        json_out = out_base.with_suffix(".json")
        txt_out = out_base.with_suffix(".txt")

        assert json_out.exists()
        assert txt_out.exists()
        txt_content = txt_out.read_text(encoding="utf-8")
        assert "Python, FastAPI, PostgreSQL" in txt_content
        assert "B.S. in Computer Science" in txt_content
        assert "Distributed Cache in Go" in txt_content

    def test_prompt_truncation_enforces_max_length(self):
        from src.nlp_extractor import MAX_RESUME_TEXT_CHARS, build_prompt

        huge_resume = "Word " * 10000  # 50,000 chars
        prompt = build_prompt(huge_resume)
        assert "[TRUNCATED FOR LENGTH]" in prompt
        assert len(huge_resume) > MAX_RESUME_TEXT_CHARS

    def test_process_file_fallback_to_heuristics_on_ai_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from src.nlp_extractor import process_file

        sample_txt = tmp_path / "fallback_cand.txt"
        sample_txt.write_text(
            "Clark Kent\nEmail: clark.kent@dailyplanet.com\nPhone: 555-123-4567\n"
            "Software Developer with 4 years experience in Python and Django.\n"
            "B.S. in Computer Science.",
            encoding="utf-8"
        )

        out_dir = tmp_path / "nlp_out"
        out_dir.mkdir()

        # Simulate AI raising RuntimeError
        def mock_extract_fail(text):
            raise RuntimeError("Ollama daemon unreachable")

        monkeypatch.setattr("src.nlp_extractor.extract_with_ai", mock_extract_fail)

        success, err = process_file(sample_txt, out_dir)
        assert success is True
        assert err is None

        json_file = out_dir / "fallback_cand_nlp.json"
        assert json_file.exists()
        saved = json.loads(json_file.read_text(encoding="utf-8"))
        assert saved["personal_info"]["name"] == "Clark Kent"
        assert saved["personal_info"]["email"] == "clark.kent@dailyplanet.com"
        assert "Python" in saved["skills"]["technical_skills"]

    def test_load_candidate_nlp_filename_variants(self, tmp_path: Path):
        from src.interview_bot import load_candidate_nlp

        nlp_file = tmp_path / "barry_allen_nlp.json"
        nlp_file.write_text(json.dumps({"name": "Barry Allen", "domain": "Physics"}), encoding="utf-8")

        # Variant 1: "barry_allen.pdf"
        res1 = load_candidate_nlp("barry_allen.pdf", tmp_path)
        assert res1.get("name") == "Barry Allen"

        # Variant 2: "barry_allen"
        res2 = load_candidate_nlp("barry_allen", tmp_path)
        assert res2.get("name") == "Barry Allen"

        # Variant 3: "barry_allen_nlp"
        res3 = load_candidate_nlp("barry_allen_nlp", tmp_path)
        assert res3.get("name") == "Barry Allen"
