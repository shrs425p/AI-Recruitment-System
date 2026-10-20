"""Tests for webcam and browser proctoring integrity.

Verifies face detection state machine, threshold counting, flag classification,
server-verified response timing, instant paste detection, and browser anti-cheat events.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

import app.routes.interview as interview_routes
from src.webcam_proctor import (
    MULTI_FACE_THRESHOLD,
    NO_FACE_THRESHOLD,
    WebcamProctor,
    check_webcam_available,
    get_proctor_status,
    start_proctoring,
    stop_proctoring,
)


def test_proctor_initialization():
    session = WebcamProctor("sess_init_test")
    assert session.session_id == "sess_init_test"
    assert session.active is False
    assert session.face_count == 0
    assert len(session.flags) == 0
    assert session.flag_counts["NO_FACE"] == 0
    assert session.flag_counts["MULTI_FACE"] == 0


def test_proctor_start_cascade_missing():
    session = WebcamProctor("sess_no_cascade")
    mock_cascade = MagicMock()
    mock_cascade.empty.return_value = True
    with (
        patch("src.webcam_proctor._MP_AVAILABLE", False),
        patch("cv2.CascadeClassifier", return_value=mock_cascade),
    ):
        result = session.start()
        assert result["success"] is False
        assert "Haar cascade not found" in result["error"]
        assert session.active is False


def test_proctor_start_webcam_unavailable():
    session = WebcamProctor("sess_no_cam")
    mock_cascade = MagicMock()
    mock_cascade.empty.return_value = False
    with (
        patch("src.webcam_proctor._MP_AVAILABLE", False),
        patch("cv2.CascadeClassifier", return_value=mock_cascade),
        patch("cv2.VideoCapture") as mock_cap_cls,
    ):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cap_cls.return_value = mock_cap

        result = session.start()
        assert result["success"] is False
        assert "No webcam found" in result["error"]
        assert session.active is False


def test_proctor_start_webcam_success():
    session = WebcamProctor("sess_cam_ok")
    mock_cascade = MagicMock()
    mock_cascade.empty.return_value = False
    with (
        patch("src.webcam_proctor._MP_AVAILABLE", False),
        patch("cv2.CascadeClassifier", return_value=mock_cascade),
        patch("cv2.VideoCapture") as mock_cap_cls,
        patch("src.webcam_proctor.threading.Thread") as mock_thread_cls,
    ):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap_cls.return_value = mock_cap
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        result = session.start()
        assert result["success"] is True
        assert session.active is True
        assert mock_thread.start.called
        session.stop()


def test_proctor_no_face_threshold_counting():
    session = WebcamProctor("sess_thresh_test")

    # Step through below threshold
    for i in range(NO_FACE_THRESHOLD - 1):
        session._check_proctor(0)
        assert len(session.flags) == 0
        assert session.flag_counts["NO_FACE"] == i + 1

    # Threshold reached -> flag emitted and counter reset
    session._check_proctor(0)
    assert len(session.flags) == 1
    assert session.flags[0]["type"] == "NO_FACE_DETECTED"
    assert session.flag_counts["NO_FACE"] == 0


def test_proctor_face_present_resets_no_face_counter():
    session = WebcamProctor("sess_reset_test")
    session._check_proctor(0)
    session._check_proctor(0)
    assert session.flag_counts["NO_FACE"] == 2
    assert len(session.flags) == 0

    # Face detected resets counter
    session._check_proctor(1)
    assert session.flag_counts["NO_FACE"] == 0
    assert len(session.flags) == 0


def test_proctor_multiple_faces_threshold_counting():
    session = WebcamProctor("sess_multi_face")

    for i in range(MULTI_FACE_THRESHOLD - 1):
        session._check_proctor(2)
        assert len(session.flags) == 0
        assert session.flag_counts["MULTI_FACE"] == i + 1

    session._check_proctor(2)
    assert len(session.flags) == 1
    assert session.flags[0]["type"] == "MULTIPLE_FACES"
    assert session.flag_counts["MULTI_FACE"] == 0


def test_proctor_summary_status_tiers():
    session = WebcamProctor("sess_tiers")

    # 0 flags -> CLEAN
    summary = session.get_summary()
    assert summary["status"] == "CLEAN"
    assert summary["total_flags"] == 0

    # 2 flags -> FLAGGED
    session._add_flag("NO_FACE_DETECTED", "Test 1")
    session._add_flag("NO_FACE_DETECTED", "Test 2")
    summary = session.get_summary()
    assert summary["status"] == "FLAGGED"
    assert summary["total_flags"] == 2
    assert summary["no_face_flags"] == 2

    # 5 flags -> HIGHLY_SUSPICIOUS
    session._add_flag("MULTIPLE_FACES", "Test 3")
    session._add_flag("MULTIPLE_FACES", "Test 4")
    session._add_flag("NO_FACE_DETECTED", "Test 5")
    summary = session.get_summary()
    assert summary["status"] == "HIGHLY_SUSPICIOUS"
    assert summary["total_flags"] == 5
    assert summary["multi_face_flags"] == 2


def test_proctor_module_session_lifecycle():
    mock_cascade = MagicMock()
    mock_cascade.empty.return_value = False
    with (
        patch("src.webcam_proctor._MP_AVAILABLE", False),
        patch("cv2.CascadeClassifier", return_value=mock_cascade),
        patch("cv2.VideoCapture") as mock_cap_cls,
        patch("src.webcam_proctor.threading.Thread"),
    ):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap_cls.return_value = mock_cap

        sess_id = "mod_sess_001"
        res = start_proctoring(sess_id)
        assert res["success"] is True

        status = get_proctor_status(sess_id)
        assert status["active"] is True
        assert status["flag_count"] == 0

        summary = stop_proctoring(sess_id)
        assert summary["status"] == "CLEAN"

        # After stop, session is removed from active store
        assert get_proctor_status(sess_id)["active"] is False


def test_check_webcam_available_utility():
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, None)
        mock_cap_cls.return_value = mock_cap

        res = check_webcam_available()
        assert res["available"] is True
        assert res["error"] is None

    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cap_cls.return_value = mock_cap

        res = check_webcam_available()
        assert res["available"] is False
        assert "No webcam found" in res["error"]


def test_server_calculates_actual_response_time_not_client_forged(candidate_app, candidate_client, monkeypatch):
    interview_routes.interview_session.clear()
    interview_routes.active_token_sessions.clear()

    token_data = {
        "used": 0,
        "candidate_name": "Proctor Timing Candidate",
        "source_file": "cand.pdf",
        "job_title": "Python Developer",
        "score": 90,
        "rank": 1,
    }
    monkeypatch.setattr(interview_routes, "get_interview_token", lambda token: token_data)
    monkeypatch.setattr(interview_routes, "start_proctoring_session", lambda session_id: None)
    monkeypatch.setattr(interview_routes, "stop_proctoring", lambda session_id: {"events": []})
    monkeypatch.setattr(
        interview_routes,
        "generate_interview_question",
        lambda **kwargs: f"Interview Question {kwargs['q_num']}",
    )
    monkeypatch.setattr(
        interview_routes,
        "evaluate_answer",
        lambda **kwargs: {"total": 8, "feedback": "Good", "strong_points": [], "weak_points": []},
    )

    started = candidate_client.post("/api/candidate/interview/start", json={"token": "PROCTOR_TOK_1", "consent": True})
    assert started.status_code == 200
    sess_id = started.get_json()["session_id"]
    sess_key = started.get_json()["session_key"]

    resp = candidate_client.post(
        "/api/candidate/interview/answer",
        json={
            "session_id": sess_id,
            "session_key": sess_key,
            "question_num": 1,
            "time_taken": 60,
            "answer": "This is pre-copied text from another tab or chat application.",
        },
        headers={"X-Interview-Session-Key": sess_key},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "INSTANT_PASTE_DETECTED" in data["proctor"]["flags"]
    assert data["proctor"]["server_verified_time"] < 2.0


def test_prolonged_response_delay_flag(candidate_app, candidate_client, monkeypatch):
    interview_routes.interview_session.clear()
    interview_routes.active_token_sessions.clear()

    token_data = {
        "used": 0,
        "candidate_name": "Proctor Delay Candidate",
        "source_file": "cand.pdf",
        "job_title": "Python Developer",
        "score": 90,
        "rank": 1,
    }
    monkeypatch.setattr(interview_routes, "get_interview_token", lambda token: token_data)
    monkeypatch.setattr(interview_routes, "start_proctoring_session", lambda session_id: None)
    monkeypatch.setattr(interview_routes, "stop_proctoring", lambda session_id: {"events": []})
    monkeypatch.setattr(
        interview_routes,
        "generate_interview_question",
        lambda **kwargs: f"Interview Question {kwargs['q_num']}",
    )
    monkeypatch.setattr(
        interview_routes,
        "evaluate_answer",
        lambda **kwargs: {"total": 8, "feedback": "Good", "strong_points": [], "weak_points": []},
    )

    started = candidate_client.post("/api/candidate/interview/start", json={"token": "PROCTOR_TOK_2", "consent": True})
    sess_id = started.get_json()["session_id"]
    sess_key = started.get_json()["session_key"]

    interview_routes.interview_session[sess_id]["question_issued_at"] = time.time() - 350.0

    resp = candidate_client.post(
        "/api/candidate/interview/answer",
        json={
            "session_id": sess_id,
            "session_key": sess_key,
            "question_num": 1,
            "time_taken": 30,
            "answer": "Finally answering after prolonged delay.",
        },
        headers={"X-Interview-Session-Key": sess_key},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    flags = data["proctor"]["flags"]
    assert "PROLONGED_RESPONSE_DELAY" in flags or "TIME_LIMIT_EXCEEDED" in flags


def test_reasonable_response_interval_no_timing_flags(candidate_app, candidate_client, monkeypatch):
    interview_routes.interview_session.clear()
    interview_routes.active_token_sessions.clear()

    token_data = {
        "used": 0,
        "candidate_name": "Proctor Normal Candidate",
        "source_file": "cand.pdf",
        "job_title": "Python Developer",
        "score": 90,
        "rank": 1,
    }
    monkeypatch.setattr(interview_routes, "get_interview_token", lambda token: token_data)
    monkeypatch.setattr(interview_routes, "start_proctoring_session", lambda session_id: None)
    monkeypatch.setattr(interview_routes, "stop_proctoring", lambda session_id: {"events": []})
    monkeypatch.setattr(
        interview_routes,
        "generate_interview_question",
        lambda **kwargs: f"Interview Question {kwargs['q_num']}",
    )
    monkeypatch.setattr(
        interview_routes,
        "evaluate_answer",
        lambda **kwargs: {"total": 8, "feedback": "Good", "strong_points": [], "weak_points": []},
    )

    started = candidate_client.post("/api/candidate/interview/start", json={"token": "PROCTOR_TOK_3", "consent": True})
    sess_id = started.get_json()["session_id"]
    sess_key = started.get_json()["session_key"]

    interview_routes.interview_session[sess_id]["question_issued_at"] = time.time() - 25.0

    resp = candidate_client.post(
        "/api/candidate/interview/answer",
        json={
            "session_id": sess_id,
            "session_key": sess_key,
            "question_num": 1,
            "time_taken": 25,
            "answer": "A well-thought-out answer explaining my background in Python development and software engineering.",
        },
        headers={"X-Interview-Session-Key": sess_key},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    flags = data["proctor"]["flags"]
    assert "INSTANT_PASTE_DETECTED" not in flags
    assert "PROLONGED_RESPONSE_DELAY" not in flags
    assert "SUSPICIOUSLY_FAST_ANSWER" not in flags


def test_proctor_mediapipe_tasks_live_or_mocked():
    session = WebcamProctor("sess_mp_tasks")
    assert session._init_detector() is True
    blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    assert session.detect_faces_in_frame(blank_frame) == 0
    res = session.process_frame_image(blank_frame)
    assert res["success"] is True
    assert res["face_count"] == 0
    session.stop()


def test_proctor_mediapipe_solutions_mode():
    session = WebcamProctor("sess_mp_solutions")
    mock_detector = MagicMock()
    mock_res = MagicMock()
    mock_res.detections = []
    mock_detector.process.return_value = mock_res
    mock_mp_face = MagicMock()
    mock_mp_face.FaceDetection.return_value = mock_detector

    with (
        patch("src.webcam_proctor._MP_AVAILABLE", True),
        patch("src.webcam_proctor._MP_MODE", "solutions"),
        patch("src.webcam_proctor._MP_FACE", mock_mp_face),
    ):
        assert session._init_detector() is True
        blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        assert session.detect_faces_in_frame(blank_frame) == 0
        res = session.process_frame_image(blank_frame)
        assert res["success"] is True
        assert res["face_count"] == 0
        session.stop()


def test_proctor_tasks_missing_model_fallback():
    session = WebcamProctor("sess_model_missing")
    mock_cascade = MagicMock()
    mock_cascade.empty.return_value = False
    fake_model = Path("non_existent_blaze_face.tflite")
    with (
        patch("src.webcam_proctor._MP_AVAILABLE", True),
        patch("src.webcam_proctor._MP_MODE", "tasks"),
        patch("src.webcam_proctor._MODEL_PATH", fake_model),
        patch("cv2.CascadeClassifier", return_value=mock_cascade),
    ):
        assert session._init_detector() is True
        assert session._detector == mock_cascade
