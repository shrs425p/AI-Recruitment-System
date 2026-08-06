from app.database import (
    create_interview_token,
    create_run,
    finish_run,
    get_connection,
    get_interview_token,
    init_db,
    upsert_candidate,
)


def test_init_db_creates_indexes_and_tables(tmp_path, monkeypatch):
    test_db = tmp_path / "test_ars.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)

    init_db()

    conn = get_connection()
    try:
        # Verify PRAGMA busy_timeout
        cursor = conn.execute("PRAGMA busy_timeout")
        row = cursor.fetchone()
        assert row[0] == 10000

        # Verify index creation
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = {r["name"] for r in cursor.fetchall()}
        assert "idx_candidates_run_id" in indexes
        assert "idx_schedules_run_id" in indexes
        assert "idx_schedules_status" in indexes
        assert "idx_interview_tokens_token" in indexes
    finally:
        conn.close()


def test_create_and_finish_run(tmp_path, monkeypatch):
    test_db = tmp_path / "test_ars.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    run_id = create_run("ranking", {"source": "unit_test"})
    assert isinstance(run_id, int)

    finish_run(run_id, status="COMPLETED", metadata={"count": 5})

    conn = get_connection()
    try:
        row = conn.execute("SELECT status, metadata FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
        assert row["status"] == "COMPLETED"
        assert '"count": 5' in row["metadata"]
    finally:
        conn.close()


def test_upsert_candidate_and_interview_token(tmp_path, monkeypatch):
    test_db = tmp_path / "test_ars.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    run_id = create_run("nlp")
    cid = upsert_candidate(run_id, "Alice Smith", email="alice@example.com", score=92.5)
    assert isinstance(cid, int)

    token = create_interview_token("TOK_999", "Alice Smith", "alice.pdf", job_title="Developer", rank=1, score=92.5)
    assert token == "TOK_999"

    fetched = get_interview_token("TOK_999")
    assert fetched["candidate_name"] == "Alice Smith"
    assert fetched["score"] == 92.5
