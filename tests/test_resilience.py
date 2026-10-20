import json
import tempfile
import unittest.mock as mock
from pathlib import Path

from app import database
from app.folder_opener import open_folder
from src import interview_bot, ranking_engine, report_generator, scheduling


class TestDatabaseExceptionHandling:
    def test_safe_json_loads_returns_default_on_invalid_json(self):
        assert database.safe_json_loads(None, default=None) is None
        assert database.safe_json_loads("", default={}) == {}
        assert database.safe_json_loads("INVALID_JSON{{{", default={}) == {}
        assert database.safe_json_loads("[1, 2, 3]", default={}) == [1, 2, 3]

    def test_get_interview_session_handles_corrupted_json_in_db(self):
        with database.db_session() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO interview_sessions (session_id, token, candidate_name, job_title, session_data, created_at) "
                "VALUES ('test_sess_corrupt', 'tok_corrupt', 'Alice', 'Engineer', 'MALFORMED{{{', 12345)"
            )
        try:
            sess = database.get_interview_session("test_sess_corrupt")
            assert sess is None

            s_id, s_data = database.get_active_session_by_token("tok_corrupt")
            assert s_id == "test_sess_corrupt"
            assert s_data is None
        finally:
            database.delete_interview_session("test_sess_corrupt")

    def test_get_all_candidate_embeddings_handles_corrupted_json(self):
        with database.db_session() as conn:
            conn.execute(
                "INSERT INTO candidate_embeddings (candidate_name, source_file, domain, skills_json, profile_text, vector_json) "
                "VALUES ('Corrupt Cand', 'test.pdf', 'Tech', 'BAD_SKILLS', 'text', 'BAD_VEC')"
            )
        try:
            embeddings = database.get_all_candidate_embeddings()
            matching = [e for e in embeddings if e["candidate_name"] == "Corrupt Cand"]
            assert len(matching) == 1
            assert matching[0]["skills"] == []
            assert matching[0]["vector"] == []
        finally:
            with database.db_session() as conn:
                conn.execute("DELETE FROM candidate_embeddings WHERE candidate_name='Corrupt Cand'")


class TestFileIoFaultTolerance:
    def test_load_top_candidates_handles_zero_byte_and_corrupt_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            empty_file = tmp_path / "ranking_scores_empty.json"
            empty_file.write_text("", encoding="utf-8")
            assert scheduling.load_top_candidates(tmp_path, top_n=5) == []

            corrupt_file = tmp_path / "ranking_scores_corrupt.json"
            corrupt_file.write_text("{broken json syntax: 123", encoding="utf-8")
            assert scheduling.load_top_candidates(tmp_path, top_n=5) == []

            array_file = tmp_path / "ranking_scores_array.json"
            array_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            assert scheduling.load_top_candidates(tmp_path, top_n=5) == []

    def test_load_scheduled_candidates_handles_zero_byte_and_corrupt_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            empty_file = tmp_path / "schedule_empty.json"
            empty_file.write_text("", encoding="utf-8")
            cands, title = interview_bot.load_scheduled_candidates(tmp_path)
            assert cands == []
            assert title == ""

            corrupt_file = tmp_path / "schedule_corrupt.json"
            corrupt_file.write_text("<<<NOT_JSON>>>", encoding="utf-8")
            cands, title = interview_bot.load_scheduled_candidates(tmp_path)
            assert cands == []
            assert title == ""


class TestRankingEngineSchemaPolymorphism:
    def test_score_candidate_handles_flat_score_dictionary(self):
        candidate = {"personal_info": {"name": "Bob"}, "_source_file": "Bob.pdf", "domain": "Tech"}
        jd = {"job_title": "Software Engineer"}
        flat_scores = {
            "candidate_name": "Bob",
            "scores": {
                "domain_match": 15,
                "skills_match": 25,
                "experience_years": 20,
                "education": 10,
                "certifications": 5,
            },
        }
        with mock.patch("src.ranking_engine.call_ai", return_value=flat_scores):
            res = ranking_engine.score_candidate(candidate, jd)
            assert res is not None
            assert res["total_score"] == 75
            assert res["scores"]["domain_match"]["score"] == 15

    def test_score_candidate_handles_numeric_strings_and_none(self):
        candidate = {"personal_info": {"name": "Bob"}, "_source_file": "Bob.pdf", "domain": "Tech"}
        jd = {"job_title": "Software Engineer"}
        str_scores = {
            "candidate_name": "Bob",
            "scores": {
                "domain_match": {"score": "12", "reason": "Good"},
                "skills_match": {"score": None, "reason": ""},
                "experience_years": {"score": "invalid", "reason": ""},
                "education": {"score": "15", "reason": ""},
                "certifications": {"score": 5, "reason": ""},
            },
        }
        with mock.patch("src.ranking_engine.call_ai", return_value=str_scores):
            res = ranking_engine.score_candidate(candidate, jd)
            assert res is not None
            assert res["scores"]["domain_match"]["score"] == 12
            assert res["scores"]["skills_match"]["score"] == 0
            assert res["scores"]["experience_years"]["score"] == 0


class TestReportGeneratorResilience:
    def test_save_report_txt_with_missing_question_num_and_none_proctor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            transcript = {
                "candidate_name": "Charlie",
                "source_file": "Charlie.pdf",
                "responses": [
                    {
                        "question": "What is unit testing?",
                        "answer": "Testing individual units.",
                        "type": "TECHNICAL",
                        "score": 9,
                        "proctor": None,
                    }
                ],
            }
            ai_rep = {
                "hire_recommendation": "Recommend",
                "risk_level": "Low",
                "proctoring_remarks": "Clean session",
            }
            txt_file = report_generator.save_report_txt(transcript, ai_rep, 85.0, tmp_path)
            assert txt_file.exists()
            content = txt_file.read_text(encoding="utf-8")
            assert "Charlie" in content
            assert "Q1 [TECHNICAL]" in content

    def test_save_final_summary_with_incomplete_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            reports = [
                {"candidate_name": "Candidate A", "combined_score": 90.0},
                {"candidate_name": "Candidate B"},  # missing combined_score!
            ]
            report_generator.save_final_summary(reports, tmp_path)
            summary_files = list(tmp_path.glob("final_summary_*.txt"))
            assert len(summary_files) == 1
            content = summary_files[0].read_text(encoding="utf-8")
            assert "Candidate A" in content
            assert "Candidate B" in content


class TestFolderOpenerResilience:
    def test_open_folder_does_not_crash_on_invalid_platform(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with mock.patch("subprocess.Popen", side_effect=FileNotFoundError("Mocked missing binary")):
                res = open_folder(tmp_path)
                assert res == str(tmp_path.resolve())
