"""
Tests for voice interview engine, speech recognition, and TTS queue.
"""

import queue
from unittest.mock import MagicMock

import pytest

import src.voice_interview as vi


class TestTextToSpeechFormatting:
    """Tests markdown stripping and queue management for speech synthesis."""

    def test_speak_strips_markdown_formatting_and_queues(self, monkeypatch: pytest.MonkeyPatch):
        test_q: queue.Queue = queue.Queue()
        monkeypatch.setattr(vi, "_tts_queue", test_q)

        vi.speak("### Hello **candidate**! Your `Python` score is #1.")

        assert not test_q.empty()
        item = test_q.get_nowait()
        assert item == "Hello candidate! Your Python score is 1."

    def test_speak_empty_and_whitespace_strings_are_ignored(self, monkeypatch: pytest.MonkeyPatch):
        test_q: queue.Queue = queue.Queue()
        monkeypatch.setattr(vi, "_tts_queue", test_q)

        vi.speak("")
        vi.speak("   \n\t  ")

        assert test_q.empty()


class TestVoiceSessionLifecycle:
    """Tests session initialization, state transitions, and announcements."""

    def test_voice_session_start_announce_and_end(self, monkeypatch: pytest.MonkeyPatch):
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

    def test_voice_session_mute_toggle(self, monkeypatch: pytest.MonkeyPatch):
        session = vi.VoiceSession(candidate_name="John Smith", job_title="DevOps")
        assert session.muted is False
        session.muted = True
        assert session.muted is True


class TestSpeechRecognitionTranscriber:
    """Tests speech input handling and fallback recognizers."""

    def test_listen_for_answer_returns_error_when_uninitialized(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(vi, "_sr_initialized", False)
        res = vi.listen_for_answer()
        assert res["success"] is False
        assert "not installed" in res["error"]

    def test_transcribe_audio_uses_google_fallback(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(vi, "_load_vosk_model", lambda: None)

        mock_recognizer = MagicMock()
        mock_recognizer.recognize_google.return_value = "transcribed voice response"
        monkeypatch.setattr(vi.sr, "Recognizer", lambda: mock_recognizer)

        mock_audio = MagicMock()
        text = vi._transcribe_audio(mock_audio)
        assert text == "transcribed voice response"
        mock_recognizer.recognize_google.assert_called_once_with(mock_audio, language="en-IN")
