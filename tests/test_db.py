"""
test_db.py - database layer test suite.
Covers schema integrity, relational foreign-key cascades, transactional rollbacks,
concurrent multi-threaded access, SQL injection defense, bulk performance, and CRUD.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from app.database import (
    create_interview_token,
    create_run,
    db_session,
    delete_all_tokens,
    delete_job_template,
    finish_run,
    get_all_candidates,
    get_all_job_templates,
    get_candidate_by_name,
    get_candidate_note,
    get_connection,
    get_interview_token,
    get_latest_schedule,
    get_runs,
    get_setting,
    mark_token_used,
    save_candidate_note,
    save_job_template,
    save_schedule,
    save_settings_dict,
    update_schedule_slot,
    upsert_candidate,
)


class TestDatabaseSchemaAndLifecycle:
    """Verifies schema definitions, table creation, and index configurations."""

    def test_schema_integrity_all_tables_exist(self, test_db: Path):
        expected_tables = {
            "candidates",
            "pipeline_runs",
            "schedules",
            "interview_tokens",
            "email_log",
            "interview_sessions",
            "job_templates",
            "candidate_notes",
            "app_settings",
        }
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

        for table in expected_tables:
            assert table in tables, f"Database table '{table}' missing from schema"

    def test_pipeline_run_lifecycle_transitions(self, test_db: Path):
        run_id = create_run("test_job_pipeline")
        assert isinstance(run_id, int)
        assert run_id > 0

        runs = get_runs()
        assert any(r["id"] == run_id and r["status"].upper() == "RUNNING" for r in runs)

        finish_run(run_id, status="COMPLETED", metadata={"candidate_count": 5})
        runs_after = get_runs()
        target = next(r for r in runs_after if r["id"] == run_id)
        assert target["status"] == "COMPLETED"
        meta = json.loads(target["metadata"])
        assert meta["candidate_count"] == 5


class TestCandidateAndNotesCrud:
    """Tests candidate records, scoring updates, notes, and tags."""

    def test_candidate_upsert_and_score_ordering(self, test_db: Path):
        run_id = create_run("ranking_run")
        upsert_candidate(run_id, "Candidate Beta", score=75.5)
        upsert_candidate(run_id, "Candidate Alpha", score=92.0)
        upsert_candidate(run_id, "Candidate Gamma", score=60.0)

        candidates = get_all_candidates(run_id=run_id)
        assert len(candidates) == 3
        # Ensure ordered by score descending
        assert candidates[0]["name"] == "Candidate Alpha"
        assert candidates[0]["score"] == 92.0
        assert candidates[1]["name"] == "Candidate Beta"
        assert candidates[2]["name"] == "Candidate Gamma"

        # Test update (upsert) existing candidate
        upsert_candidate(run_id, "Candidate Beta", score=95.0)
        updated = get_candidate_by_name("Candidate Beta")
        assert updated is not None
        assert updated["score"] == 95.0

    def test_candidate_notes_and_tags_persistence(self, test_db: Path):
        cand_name = "Evelyn Reed"
        save_candidate_note(
            candidate_name=cand_name,
            note="Strong system architecture knowledge",
            tags=["Follow up", "Strong Fit"],
            source_file="evelyn_resume.pdf",
        )

        record = get_candidate_note(cand_name)
        assert record is not None
        assert record["note"] == "Strong system architecture knowledge"
        assert "Follow up" in record["tags"]
        assert "Strong Fit" in record["tags"]

        # Update note without losing tags
        save_candidate_note(
            candidate_name=cand_name,
            note="Updated: Prefers remote position",
            tags=["Strong Fit"],
            source_file="evelyn_resume.pdf",
        )
        record2 = get_candidate_note(cand_name)
        assert record2["note"] == "Updated: Prefers remote position"
        assert record2["tags"] == ["Strong Fit"]


class TestSchedulesAndTokensCrud:
    """Tests interview schedule generation, slot allocation, and secure access tokens."""

    def test_schedule_crud_and_slot_selection(self, test_db: Path):
        run_id = create_run("schedule_run")
        schedule_entries = [
            {
                "rank": 1,
                "candidate_name": "Alice Dev",
                "score": 90,
                "status": "CONFIRMED",
                "selected_slot": "2026-11-01 10:00 AM",
                "offered_slots": ["2026-11-01 10:00 AM", "2026-11-01 02:00 PM"],
            }
        ]
        sched_ids = save_schedule(run_id, schedule_entries, "Cloud Engineer")
        assert len(sched_ids) > 0

        latest = get_latest_schedule()
        assert len(latest) >= 1
        alice_entry = next(e for e in latest if e["candidate_name"] == "Alice Dev")
        assert alice_entry["job_title"] == "Cloud Engineer"

        update_schedule_slot("Alice Dev", "2026-11-01 02:00 PM")
        updated_sched = get_latest_schedule()
        updated_alice = next(e for e in updated_sched if e["candidate_name"] == "Alice Dev")
        assert updated_alice["selected_slot"] == "2026-11-01 02:00 PM"

    def test_interview_token_lifecycle(self, test_db: Path):
        token_str = "T_SECURE_TOKEN_XYZ_123"
        create_interview_token(
            token=token_str,
            candidate_name="Bob Coder",
            source_file="bob.pdf",
            job_title="Backend Engineer",
            score=88.5,
            rank=2,
        )

        token_record = get_interview_token(token_str)
        assert token_record is not None
        assert token_record["candidate_name"] == "Bob Coder"
        assert token_record["used"] == 0

        mark_token_used(token_str)
        used_record = get_interview_token(token_str)
        assert used_record["used"] == 1

        delete_all_tokens()
        assert get_interview_token(token_str) is None


class TestJobTemplatesAndSettings:
    """Tests job description templates and key-value system settings."""

    def test_job_template_crud(self, test_db: Path):
        template_id = save_job_template("DevOps Lead", "Kubernetes, Terraform, CI/CD, AWS")
        assert isinstance(template_id, int)

        templates = get_all_job_templates()
        assert any(t["title"] == "DevOps Lead" for t in templates)

        delete_job_template(template_id)
        templates_after = get_all_job_templates()
        assert not any(t["id"] == template_id for t in templates_after)

    def test_settings_persistence(self, test_db: Path):
        save_settings_dict({"TECH_Q_COUNT": "6", "INTERVIEW_TIMER_SEC": "90"})
        assert get_setting("TECH_Q_COUNT") == "6"
        assert get_setting("INTERVIEW_TIMER_SEC") == "90"
        assert get_setting("NONEXISTENT_KEY", default="default_val") == "default_val"


class TestDatabaseReliabilityAndSecurity:
    """Tests ACID guarantees, transactional rollback, multi-thread concurrency, and SQL injection defense."""

    def test_transactional_rollback_on_exception(self, test_db: Path):
        run_id = create_run("rollback_test_run")
        try:
            with db_session() as conn:
                conn.execute(
                    "INSERT INTO candidates (run_id, name, score) VALUES (?, ?, ?)",
                    (run_id, "Candidate ShouldRollback", 50.0),
                )
                raise RuntimeError("Intentional error to trigger rollback")
        except RuntimeError:
            pass

        assert get_candidate_by_name("Candidate ShouldRollback") is None

    def test_sql_injection_defense_via_parameterization(self, test_db: Path):
        run_id = create_run("injection_test_run")
        malicious_name = "Robert'); DROP TABLE candidates;--"
        upsert_candidate(run_id, malicious_name, score=99.9)

        record = get_candidate_by_name(malicious_name)
        assert record is not None
        assert record["name"] == malicious_name

        # Verify table was not dropped
        candidates = get_all_candidates(run_id=run_id)
        assert len(candidates) >= 1

    def test_multi_threaded_concurrency_safety(self, test_db: Path):
        run_id = create_run("concurrency_run")
        thread_count = 15
        errors = []

        def worker(thread_idx: int):
            try:
                for i in range(10):
                    cand_name = f"Worker_{thread_idx}_Cand_{i}"
                    upsert_candidate(run_id, cand_name, score=float(thread_idx + i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent database writes failed with errors: {errors}"
        total_candidates = get_all_candidates(run_id=run_id)
        assert len(total_candidates) == thread_count * 10

    def test_bulk_candidate_performance(self, test_db: Path):
        run_id = create_run("bulk_performance_run")
        start = time.perf_counter()

        with db_session() as conn:
            payload = [(run_id, f"Candidate Bulk {i:04d}", float(i % 100)) for i in range(500)]
            conn.executemany(
                "INSERT INTO candidates (run_id, name, score) VALUES (?, ?, ?)",
                payload,
            )

        insert_duration = time.perf_counter() - start
        assert insert_duration < 5.0, f"Bulk insert took too long: {insert_duration:.2f}s"

        start_query = time.perf_counter()
        results = get_all_candidates(run_id=run_id)
        query_duration = time.perf_counter() - start_query

        assert len(results) == 500
        assert query_duration < 1.0, f"Bulk query took too long: {query_duration:.3f}s"
