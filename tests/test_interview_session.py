import time

import app.routes.interview as interview_routes


def test_interview_session_ttl_expiration(monkeypatch):
    interview_routes.interview_session.clear()
    interview_routes.active_token_sessions.clear()

    now = time.time()
    # Active session (created now)
    interview_routes.interview_session["ACTIVE_1"] = {
        "token": "T_ACTIVE",
        "session_key": "KEY_ACTIVE",
        "remote_addr": "127.0.0.1",
        "user_agent": "TestBrowser",
        "created_at": now,
    }
    interview_routes.active_token_sessions["T_ACTIVE"] = "ACTIVE_1"

    # Expired session (created 3 hours ago)
    interview_routes.interview_session["EXPIRED_1"] = {
        "token": "T_EXPIRED",
        "session_key": "KEY_EXPIRED",
        "remote_addr": "127.0.0.1",
        "user_agent": "TestBrowser",
        "created_at": now - 10000,
    }
    interview_routes.active_token_sessions["T_EXPIRED"] = "EXPIRED_1"

    interview_routes._cleanup_expired_sessions()

    assert "ACTIVE_1" in interview_routes.interview_session
    assert "EXPIRED_1" not in interview_routes.interview_session
    assert "T_EXPIRED" not in interview_routes.active_token_sessions
