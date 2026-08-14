# Documentation for `voice_interview.py`

**Path:** `src/voice_interview.py`

## Module Docstring
No module-level docstring provided.

## Role
The `voice_interview.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (_load_vosk_model, _transcribe_audio, _init_tts) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `logging`
- `queue`
- `re`
- `threading`
- `time`
- `pyttsx3`
- `speech_recognition`
- `src.common.install_path`

### Global Variables
- `logger`
- `_BASE_DIR`
- `_VOSK_MODEL_CANDIDATES`
- `_VOSK_MODEL_DIR`
- `_vosk_model`
- `SPEECH_TIMEOUT`
- `PHRASE_TIME_LIMIT`
- `SILENCE_THRESHOLD`
- `TTS_RATE`
- `TTS_VOLUME`
- `_tts_engine`
- `_tts_lock`
- `_tts_thread`
- `_tts_running`
- `_recognizer`
- `_microphone`
- `_sr_initialized`
- `_voice_sessions`

### Classes
#### `VoiceSession`
**Docstring:** Manages a full voice interview session for one candidate.

**Methods:**
- `__init__(self, candidate_name, job_title)`
  - **Docstring:** No method docstring provided.
- `start(self)`
  - **Docstring:** No method docstring provided.
- `announce_question(self, q_num, total, q_type, question)`
  - **Docstring:** Speak question number and text.
- `get_answer(self, timeout)`
  - **Docstring:** Listen and return candidate's spoken answer.
- `announce_score(self, score, feedback)`
  - **Docstring:** Optionally read out score and brief feedback.
- `end(self)`
  - **Docstring:** No method docstring provided.


### Functions
#### `_load_vosk_model()`
**Docstring:** Load the Vosk model once and cache it. Returns None if no model directory found.

#### `_transcribe_audio(audio_data)`
**Docstring:** Transcribe audio using the best available fully-open-source engine.
Priority: Vosk (Apache 2.0, offline) → Google free API fallback with warning.

#### `_init_tts()`
**Docstring:** Initialise the pyttsx3 TTS engine and configure voice settings.
Must be called from the same thread that will call engine.say() / runAndWait().
pyttsx3 is not thread-safe — that's why it runs in a dedicated worker thread.

Returns True on success, False if pyttsx3 cannot initialise (e.g. no audio output).

#### `_tts_worker()`
**Docstring:** Background thread that pulls text from _tts_queue and speaks it sequentially.

Items are processed one at a time so overlapping speak() calls don't clash.
Sending None to the queue is the signal to exit the thread gracefully.

#### `start_tts_engine()`
**Docstring:** Start the TTS background thread. Call once before any speak() calls.

#### `stop_tts_engine()`
**Docstring:** Signal the TTS background thread to exit and wait for it to finish.

#### `speak(text, block)`
**Docstring:** Queue text for TTS playback.

Parameters:
  text  — The string to speak. Markdown symbols are stripped automatically.
  block — If True, waits until the speech finishes before returning.
          Use block=True for critical messages (e.g. the final farewell)
          where you need to be sure the candidate heard it.

#### `speak_sync(text)`
**Docstring:** Speak immediately, blocking until done. Used for critical messages.

#### `init_speech_recognition()`
**Docstring:** Set up the Recognizer and test that a microphone is accessible.

Settings tuned for interview use:
  energy_threshold = 300          — minimum audio energy to consider as speech
  dynamic_energy_threshold = True — auto-adjust threshold for ambient noise
  pause_threshold = 1.5           — seconds of silence that ends an utterance
  phrase_threshold = 0.3          — min duration for a recognisable phrase

Returns True if microphone intake works, False if no microphone is found.

#### `listen_for_answer(timeout, phrase_limit, status_callback)`
**Docstring:** Listen to microphone and return transcribed text.
Returns: {
    'success': bool,
    'text': str,
    'error': str or None,
    'duration': float
}

#### `check_microphone()`
**Docstring:** Check if microphone is available and working.

#### `check_tts()`
**Docstring:** Check if TTS is available.

#### `create_voice_session(session_id, candidate_name, job_title)`
**Docstring:** Create and start a voice session. Returns True if mic available.

#### `speak_question(session_id, q_num, total, q_type, question)`
**Docstring:** Speak a question in a voice session.

#### `listen_answer(session_id)`
**Docstring:** Listen for candidate's answer in a voice session.

#### `end_voice_session(session_id)`
**Docstring:** End and clean up a voice session.
