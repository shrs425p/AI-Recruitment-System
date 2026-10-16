import time

import app.routes.interview as interview_routes
from app.database import (
    create_run,
    delete_candidate,
    get_interview_session,
    init_db,
    save_interview_session,
    upsert_candidate,
)


def test_interview_session_ttl_expiration(monkeypatch, tmp_path):
    test_db = tmp_path / "test_sess.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    interview_routes.interview_session.clear()
    interview_routes.active_token_sessions.clear()

    now = time.time()
    # Active session (created now)
    active_sess = {
        "session_id": "ACTIVE_1",
        "token": "T_ACTIVE",
        "session_key": "KEY_ACTIVE",
        "remote_addr": "127.0.0.1",
        "user_agent": "TestBrowser",
        "candidate_name": "Active Cand",
        "created_at": now,
    }
    interview_routes.interview_session["ACTIVE_1"] = active_sess
    save_interview_session("ACTIVE_1", active_sess)
    interview_routes.active_token_sessions["T_ACTIVE"] = "ACTIVE_1"

    # Expired session (created 3 hours ago)
    expired_sess = {
        "session_id": "EXPIRED_1",
        "token": "T_EXPIRED",
        "session_key": "KEY_EXPIRED",
        "remote_addr": "127.0.0.1",
        "user_agent": "TestBrowser",
        "candidate_name": "Expired Cand",
        "created_at": now - 10000,
    }
    interview_routes.interview_session["EXPIRED_1"] = expired_sess
    save_interview_session("EXPIRED_1", expired_sess)
    interview_routes.active_token_sessions["T_EXPIRED"] = "EXPIRED_1"

    interview_routes._cleanup_expired_sessions()

    assert "ACTIVE_1" in interview_routes.interview_session
    assert "EXPIRED_1" not in interview_routes.interview_session
    assert "T_EXPIRED" not in interview_routes.active_token_sessions

    # Verify SQLite state
    assert get_interview_session("ACTIVE_1") is not None
    assert get_interview_session("EXPIRED_1") is None


def test_interview_session_recovery_after_restart(monkeypatch, tmp_path):
    """Simulate server restart by clearing in-memory dictionaries and restoring from SQLite."""
    test_db = tmp_path / "test_restart.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    interview_routes.interview_session.clear()
    interview_routes.active_token_sessions.clear()

    session_id = "S_RESTORE_1"
    session_data = {
        "session_id": session_id,
        "token": "TOKEN_ABC",
        "session_key": "KEY_SECRET_123",
        "remote_addr": "192.168.1.50",
        "user_agent": "Mozilla/5.0",
        "candidate_name": "Maria Garcia",
        "job_title": "Data Engineer",
        "responses": [{"q": 1, "score": 8}],
        "created_at": time.time(),
    }
    save_interview_session(session_id, session_data)

    # In-memory dictionary is empty (simulating process restart)
    assert session_id not in interview_routes.interview_session

    # Fetching via _get_candidate_session restores it from SQLite
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context(
        "/api/candidate/interview/answer",
        headers={
            "X-Interview-Session-Key": "KEY_SECRET_123",
            "User-Agent": "Mozilla/5.0",
        },
        environ_base={"REMOTE_ADDR": "192.168.1.50"},
    ):
        restored, error = interview_routes._get_candidate_session({"session_id": session_id})
        assert error is None
        assert restored is not None
        assert restored["candidate_name"] == "Maria Garcia"
        assert restored["token"] == "TOKEN_ABC"
        assert len(restored["responses"]) == 1

        # Check it was re-cached in memory
        assert session_id in interview_routes.interview_session


def test_candidate_deletion_purges_interview_sessions(monkeypatch, tmp_path):
    test_db = tmp_path / "test_purge.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    run_id = create_run("ranking")
    cand_id = upsert_candidate(run_id, "Devon Lane", email="devon@example.com")

    sess_id = "S_DEVON"
    save_interview_session(
        sess_id,
        {
            "session_id": sess_id,
            "token": "T_DEVON",
            "candidate_name": "Devon Lane",
            "created_at": time.time(),
        },
    )

    assert get_interview_session(sess_id) is not None

    # Delete candidate
    deleted = delete_candidate(cand_id)
    assert deleted is not None

    # Verify session was deleted from SQLite
    assert get_interview_session(sess_id) is None
