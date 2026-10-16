import queue
from unittest.mock import MagicMock

import src.voice_interview as vi


def test_speak_strips_markdown_and_queues(monkeypatch):
    test_q = queue.Queue()
    monkeypatch.setattr(vi, "_tts_queue", test_q)

    vi.speak("### Hello **candidate**! Your `Python` score is #1.")

    assert not test_q.empty()
    item = test_q.get_nowait()
    assert item == "Hello candidate! Your Python score is 1."


def test_speak_empty_string_does_not_queue(monkeypatch):
    test_q = queue.Queue()
    monkeypatch.setattr(vi, "_tts_queue", test_q)

    vi.speak("")
    vi.speak("   ")

    assert test_q.empty()


def test_voice_session_lifecycle(monkeypatch):
    monkeypatch.setattr(vi, "start_tts_engine", lambda: None)
    monkeypatch.setattr(vi, "stop_tts_engine", lambda: None)
    monkeypatch.setattr(vi, "init_speech_recognition", lambda: True)
    monkeypatch.setattr(vi, "speak_sync", lambda msg: None)
    monkeypatch.setattr(vi, "speak", lambda msg: None)

    session = vi.VoiceSession(candidate_name="Jane Doe", job_title="ML Engineer")
    assert session.active is False
    assert session.muted is False

    session.start()
    assert session.active is True

    session.announce_question(1, 5, "Technical", "Explain recursion")
    session.announce_score(8, "Good explanation")

    session.end()
    assert session.active is False


def test_listen_for_answer_uninitialized(monkeypatch):
    monkeypatch.setattr(vi, "_sr_initialized", False)
    res = vi.listen_for_answer()
    assert res["success"] is False
    assert "not installed" in res["error"]


def test_transcribe_audio_google_fallback(monkeypatch):
    monkeypatch.setattr(vi, "_load_vosk_model", lambda: None)

    mock_recognizer = MagicMock()
    mock_recognizer.recognize_google.return_value = "transcribed voice response"
    monkeypatch.setattr(vi.sr, "Recognizer", lambda: mock_recognizer)

    mock_audio = MagicMock()
    text = vi._transcribe_audio(mock_audio)
    assert text == "transcribed voice response"
    mock_recognizer.recognize_google.assert_called_once_with(mock_audio, language="en-IN")
