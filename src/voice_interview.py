import queue  # Thread-safe queue for TTS text dispatch
import re  # Regex — strip markdown from TTS text
import threading  # TTS runs in a background thread to avoid blocking
import time  # sleep() calls and timing

import pyttsx3  # Offline TTS engine (no internet needed for speech)
import speech_recognition as sr  # Wrapper for multiple speech-to-text backends

from app.app_paths import install_path

# ─────────────────────────────────────────────
# OPEN-SOURCE SPEECH RECOGNITION: VOSK (Apache 2.0)
# Fully offline. No API key. No internet needed after model download.
#
# Indian English models (Apache 2.0):
#   Small (36 MB)  — vosk-model-small-en-in-0.4   ← preferred (fast, desktop-ready)
#   Large (1.0 GB) — vosk-model-en-in-0.5          ← high-accuracy option
#
# Run setup_vosk.py to auto-download the small model, or:
#   1. Download from https://alphacephei.com/vosk/models
#   2. Extract the zip so the folder sits next to this file.
# ─────────────────────────────────────────────
try:
    from vosk import KaldiRecognizer as VoskRecognizer
    from vosk import Model as VoskModel
    _VOSK_AVAILABLE = True
except ImportError:
    _VOSK_AVAILABLE = False

_BASE_DIR = install_path(".")

# Ordered preference: small Indian-English first, then large Indian-English,
# then small US-English as a last resort.
_VOSK_MODEL_CANDIDATES = [
    _BASE_DIR / "vosk-model-small-en-in-0.4",
    _BASE_DIR / "vosk-model-en-in-0.5",
    _BASE_DIR / "vosk-model-small-en-us-0.15",
]
_VOSK_MODEL_DIR = next((p for p in _VOSK_MODEL_CANDIDATES if p.exists()), _VOSK_MODEL_CANDIDATES[0])
_vosk_model = None  # loaded lazily on first use

def _load_vosk_model():
    """Load the Vosk model once and cache it. Returns None if no model directory found."""
    global _vosk_model, _VOSK_MODEL_DIR
    if _vosk_model is not None:
        return _vosk_model
    if not _VOSK_AVAILABLE:
        return None
    # Re-scan in case a model was downloaded after startup
    found = next((p for p in _VOSK_MODEL_CANDIDATES if p.exists()), None)
    if found is None:
        return None
    _VOSK_MODEL_DIR = found
    try:
        import vosk
        vosk.SetLogLevel(-1)  # suppress noisy Vosk logs
        _vosk_model = VoskModel(str(_VOSK_MODEL_DIR))
        print(f"[STT] Vosk model loaded: {_VOSK_MODEL_DIR.name} (offline, Apache 2.0)")
        return _vosk_model
    except Exception as e:
        print(f"[STT] Vosk model load failed: {e}")
        return None


def _transcribe_audio(audio_data: sr.AudioData) -> str:
    """
    Transcribe audio using the best available fully-open-source engine.
    Priority: Vosk (Apache 2.0, offline) → Google free API fallback with warning.
    """
    model = _load_vosk_model()
    if model is not None:
        try:
            import json as _json
            wav_bytes = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
            rec = VoskRecognizer(model, 16000)
            rec.AcceptWaveform(wav_bytes)
            result = _json.loads(rec.Result())
            return result.get("text", "")
        except Exception as e:
            print(f"[STT] Vosk transcription error: {e}")
            return ""
    else:
        # No Vosk model installed — fall back to Google free API with a clear warning
        print("[STT] WARNING: No Vosk model found. Falling back to Google Speech API (requires internet).")
        print("[STT]          Run 'python setup_vosk.py' to download the offline Indian-English model.")
        try:
            return sr.Recognizer().recognize_google(audio_data, language='en-IN')
        except Exception:
            return ""

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# How long to wait (seconds) for the candidate to start speaking after a question
SPEECH_TIMEOUT        = 15

# Maximum length (seconds) of a single answer recording
PHRASE_TIME_LIMIT     = 60

# Seconds of silence detected before the recording is considered complete
SILENCE_THRESHOLD     = 2

# TTS speaking speed in words per minute (higher = faster, 165 is natural conversational pace)
TTS_RATE              = 165

# TTS volume from 0.0 (silent) to 1.0 (maximum)
TTS_VOLUME            = 0.95

# ─────────────────────────────────────────────
# TTS ENGINE — Thread-safe singleton
# ─────────────────────────────────────────────

# Module-level TTS engine and thread state
# Using module-level globals so the engine is initialised once and shared
_tts_engine   = None          # pyttsx3 engine instance
_tts_lock     = threading.Lock()  # Mutex guard (currently unused but available for future use)
_tts_queue: queue.Queue = queue.Queue()     # Thread-safe queue of text strings to speak
_tts_thread   = None          # Background worker thread reference
_tts_running  = False         # Flag used to signal the worker to stop

def _init_tts():
    """
    Initialise the pyttsx3 TTS engine and configure voice settings.
    Must be called from the same thread that will call engine.say() / runAndWait().
    pyttsx3 is not thread-safe — that's why it runs in a dedicated worker thread.

    Returns True on success, False if pyttsx3 cannot initialise (e.g. no audio output).
    """
    global _tts_engine
    try:
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty('rate',   TTS_RATE)    # speaking speed
        _tts_engine.setProperty('volume', TTS_VOLUME)  # volume level

        # Try to find a clear English voice from the installed TTS voices
        voices = _tts_engine.getProperty('voices')
        for v in voices:
            if 'english' in v.name.lower() or 'en_' in v.id.lower():
                _tts_engine.setProperty('voice', v.id)
                break  # use the first English voice found

        return True
    except Exception as e:
        print(f"[TTS] Init failed: {e}")
        return False


def _tts_worker():
    """
    Background thread that pulls text from _tts_queue and speaks it sequentially.

    Items are processed one at a time so overlapping speak() calls don't clash.
    Sending None to the queue is the signal to exit the thread gracefully.
    """
    global _tts_running
    if not _init_tts():  # initialise engine in this thread (pyttsx3 requirement)
        return

    while _tts_running:
        try:
            text = _tts_queue.get(timeout=0.5)  # wait up to 0.5s for next item
            if text is None:  # shutdown sentinel received
                break
            if _tts_engine:
                _tts_engine.say(text)
                _tts_engine.runAndWait()  # blocks until speech finishes
            _tts_queue.task_done()  # signal that this item is done (for queue.join())
        except queue.Empty:
            continue  # no item in queue — loop back and wait
        except Exception as e:
            print(f"[TTS] Speak error: {e}")


def start_tts_engine():
    """Start the TTS background thread. Call once before any speak() calls."""
    global _tts_thread, _tts_running
    if _tts_running and _tts_thread and _tts_thread.is_alive():
        return  # already running
    _tts_running = True
    _tts_thread  = threading.Thread(target=_tts_worker, daemon=True)  # daemon=True: thread won't block app exit
    _tts_thread.start()
    time.sleep(0.5)  # give the engine a moment to initialise before the first speak()


def stop_tts_engine():
    """Signal the TTS background thread to exit and wait for it to finish."""
    global _tts_running
    _tts_running = False
    _tts_queue.put(None)  # send shutdown sentinel
    if _tts_thread:
        _tts_thread.join(timeout=3)  # wait up to 3 seconds for thread to exit


def speak(text: str, block: bool = False):
    """
    Queue text for TTS playback.

    Parameters:
      text  — The string to speak. Markdown symbols are stripped automatically.
      block — If True, waits until the speech finishes before returning.
              Use block=True for critical messages (e.g. the final farewell)
              where you need to be sure the candidate heard it.
    """
    if not text or not text.strip():
        return  # nothing to say

    # Strip markdown formatting that would sound weird when read aloud
    clean = re.sub(r'[*_`#]', '', text)          # remove *, _, `, # symbols
    clean = re.sub(r'\s+', ' ', clean).strip()   # collapse extra whitespace

    _tts_queue.put(clean)  # put cleaned text into the worker thread's queue

    if block:
        _tts_queue.join()  # wait until the queue is empty (all items spoken)


def speak_sync(text: str):
    """Speak immediately, blocking until done. Used for critical messages."""
    speak(text, block=True)


# ─────────────────────────────────────────────
# SPEECH RECOGNITION
# ─────────────────────────────────────────────

_recognizer     = None
_microphone     = None
_sr_initialized = False


def init_speech_recognition():
    """
    Set up the Recognizer and test that a microphone is accessible.

    Settings tuned for interview use:
      energy_threshold = 300          — minimum audio energy to consider as speech
      dynamic_energy_threshold = True — auto-adjust threshold for ambient noise
      pause_threshold = 1.5           — seconds of silence that ends an utterance
      phrase_threshold = 0.3          — min duration for a recognisable phrase

    Returns True if microphone intake works, False if no microphone is found.
    """
    global _recognizer, _microphone, _sr_initialized
    try:
        _recognizer = sr.Recognizer()
        _recognizer.energy_threshold        = 300
        _recognizer.dynamic_energy_threshold = True
        _recognizer.pause_threshold         = 1.5   # silence before stopping
        _recognizer.phrase_threshold        = 0.3

        # Test microphone access and calibrate for room noise
        with sr.Microphone() as mic:
            _recognizer.adjust_for_ambient_noise(mic, duration=0.5)  # 0.5s noise sample

        _microphone     = sr.Microphone()
        _sr_initialized = True
        print("[SR] Speech recognition initialized.")
        return True
    except Exception as e:
        print(f"[SR] Init failed: {e}")
        _sr_initialized = False
        return False


def listen_for_answer(timeout: int = SPEECH_TIMEOUT,
                      phrase_limit: int = PHRASE_TIME_LIMIT,
                      status_callback=None) -> dict:
    """
    Listen to microphone and return transcribed text.
    Returns: {
        'success': bool,
        'text': str,
        'error': str or None,
        'duration': float
    }
    """
    if not _sr_initialized:
        return {'success': False, 'text': '', 'error': 'SpeechRecognition not installed', 'duration': 0}

    if _recognizer is None or _microphone is None:
        if not init_speech_recognition():
            return {'success': False, 'text': '', 'error': 'Speech recognition not initialized', 'duration': 0}

    if _microphone is None or _recognizer is None:
        return {'success': False, 'text': '', 'error': 'Microphone device unavailable', 'duration': 0}

    if status_callback:
        status_callback('listening')

    start_time = time.time()

    try:
        with _microphone as source:
            # Adjust microphone for current room noise before each recording
            _recognizer.adjust_for_ambient_noise(source, duration=0.3)

            if status_callback:
                status_callback('recording')  # notify GUI to show recording indicator

            # Record audio — blocks until phrase_time_limit reached or silence detected
            audio = _recognizer.listen(
                source,
                timeout=timeout,          # how long to wait for speech to start
                phrase_time_limit=phrase_limit  # max recording length
            )

        if status_callback:
            status_callback('processing')  # notify GUI to show 'Processing...' indicator

        # Transcribe using preferred open-source engine (Vosk if available, else Google fallback)
        text = _transcribe_audio(audio)

        duration = time.time() - start_time

        if text.strip():
            return {'success': True, 'text': text.strip(), 'error': None, 'duration': round(duration, 1)}
        else:
            return {'success': False, 'text': '', 'error': 'No speech detected', 'duration': round(duration, 1)}

    except sr.WaitTimeoutError:
        return {'success': False, 'text': '', 'error': 'No speech detected (timeout)', 'duration': SPEECH_TIMEOUT}
    except sr.UnknownValueError:
        return {'success': False, 'text': '', 'error': 'Could not understand speech', 'duration': round(time.time() - start_time, 1)}
    except sr.RequestError as e:
        return {'success': False, 'text': '', 'error': f'Recognition service error: {e}', 'duration': 0}
    except Exception as e:
        return {'success': False, 'text': '', 'error': str(e), 'duration': 0}


# ─────────────────────────────────────────────
# VOICE SESSION MANAGER
# ─────────────────────────────────────────────

class VoiceSession:
    """Manages a full voice interview session for one candidate."""

    def __init__(self, candidate_name: str, job_title: str):
        self.candidate_name = candidate_name
        self.job_title      = job_title
        self.active         = False
        self.muted          = False

    def start(self):
        self.active = True
        start_tts_engine()
        sr_ok = init_speech_recognition()

        greeting = (
            f"Hello, I am your AI interviewer today. "
            f"You are being interviewed for the position of {self.job_title}. "
            f"Please speak clearly after each question. "
            f"Say 'skip' if you want to skip a question. "
            f"Let's begin."
        )
        speak_sync(greeting)
        return sr_ok

    def announce_question(self, q_num: int, total: int, q_type: str, question: str):
        """Speak question number and text."""
        if not self.active or self.muted:
            return
        intro = f"Question {q_num} of {total}. {q_type} question."
        speak_sync(intro)
        time.sleep(0.3)
        speak_sync(question)
        time.sleep(0.5)
        speak("Please give your answer now.")

    def get_answer(self, timeout: int = SPEECH_TIMEOUT) -> dict:
        """Listen and return candidate's spoken answer."""
        if not self.active:
            return {'success': False, 'text': '', 'error': 'Session not active', 'duration': 0}
        return listen_for_answer(timeout=timeout)

    def announce_score(self, score: int, feedback: str):
        """Optionally read out score and brief feedback."""
        if not self.active or self.muted:
            return
        msg = f"Thank you. You scored {score} out of 10."
        speak(msg)

    def end(self):
        self.active = False
        speak_sync(
            "Thank you for completing this interview. "
            "Your responses have been recorded. "
            "We will be in touch soon. Goodbye."
        )
        time.sleep(2)
        stop_tts_engine()


# ─────────────────────────────────────────────
# UTILITY: Check microphone availability
# ─────────────────────────────────────────────

def check_microphone() -> dict:
    """Check if microphone is available and working."""
    try:
        mics = sr.Microphone.list_microphone_names()
        if not mics:
            return {'available': False, 'error': 'No microphone found', 'devices': []}
        r = sr.Recognizer()
        with sr.Microphone() as src:
            r.adjust_for_ambient_noise(src, duration=0.3)
        return {'available': True, 'error': None, 'devices': mics[:5]}
    except Exception as e:
        return {'available': False, 'error': str(e), 'devices': []}


def check_tts() -> dict:
    """Check if TTS is available."""
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        engine.stop()
        return {'available': True, 'voices': [v.name for v in voices[:3]], 'error': None}
    except Exception as e:
        return {'available': False, 'voices': [], 'error': str(e)}


# ─────────────────────────────────────────────
# FLASK-COMPATIBLE SYNCHRONOUS API
# ─────────────────────────────────────────────

# Global voice sessions store
_voice_sessions = {}  # type: dict[str, VoiceSession]


def create_voice_session(session_id: str, candidate_name: str, job_title: str) -> bool:
    """Create and start a voice session. Returns True if mic available."""
    vs = VoiceSession(candidate_name, job_title)
    _voice_sessions[session_id] = vs
    return vs.start()


def speak_question(session_id: str, q_num: int, total: int, q_type: str, question: str):
    """Speak a question in a voice session."""
    vs = _voice_sessions.get(session_id)
    if vs:
        vs.announce_question(q_num, total, q_type, question)


def listen_answer(session_id: str) -> dict:
    """Listen for candidate's answer in a voice session."""
    vs = _voice_sessions.get(session_id)
    if vs:
        return vs.get_answer()
    return {'success': False, 'text': '', 'error': 'Session not found', 'duration': 0}


def end_voice_session(session_id: str):
    """End and clean up a voice session."""
    vs = _voice_sessions.pop(session_id, None)
    if vs:
        vs.end()
