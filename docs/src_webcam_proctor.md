# Documentation for `webcam_proctor.py`

**Path:** `src/webcam_proctor.py`

## Module Docstring
No module-level docstring provided.

## Role
The `webcam_proctor.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (start_proctoring, get_frame, get_proctor_status) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `base64`
- `threading`
- `time`
- `datetime.datetime`
- `typing.Any`
- `cv2`
- `numpy`

### Global Variables
- `CHECK_INTERVAL`
- `NO_FACE_THRESHOLD`
- `MULTI_FACE_THRESHOLD`
- `FRAME_WIDTH`
- `FRAME_HEIGHT`
- `JPEG_QUALITY`
- `CASCADE_PATH`
- `_proctor_sessions`

### Classes
#### `WebcamProctor`
**Docstring:** Manages webcam-based proctoring for one interview session.

Starts a background thread that:
  1. Reads frames from the webcam at ~30fps.
  2. Runs face detection on each frame.
  3. Annotates the frame (green box for detected face, red for missing).
  4. Encodes the frame as a base64 JPEG string for live browser streaming.
  5. Every CHECK_INTERVAL seconds, checks face count and records flags.

Thread-safety:
  All shared state (latest_frame_b64, face_count, flags) is protected
  by a threading.Lock so the Flask route handlers can read safely while
  the background thread writes.

Public API:
  start()       — open webcam and start background thread
  stop()        — stop thread, release webcam, return summary
  get_frame()   — return latest JPEG frame as base64 string
  get_status()  — return live proctor status dict
  get_summary() — return final proctor report for the interview transcript

**Methods:**
- `__init__(self, session_id)`
  - **Docstring:** No method docstring provided.
- `start(self)`
  - **Docstring:** Open the webcam and start the proctoring background thread.

Returns:
  {'success': True, 'error': None} on success
  {'success': False, 'error': str} if webcam unavailable
- `stop(self)`
  - **Docstring:** Stop proctoring: signal the thread to exit, wait for it, then
release the webcam and close MediaPipe detector.

Returns a final proctor summary dict (same as get_summary()).
- `_run(self)`
  - **Docstring:** Main proctoring loop — executes in the background daemon thread.

Continuously reads webcam frames, runs face detection,
annotates frames with status text, encodes them to base64 JPEG,
and every CHECK_INTERVAL seconds evaluates the face count
to decide whether to raise a proctor flag.
- `_check_proctor(self, n_faces)`
  - **Docstring:** Evaluate the most recent face count and increment running counters.

A flag is only raised once the consecutive-absence count reaches the
configured threshold (NO_FACE_THRESHOLD or MULTI_FACE_THRESHOLD).
This prevents false flags from brief occlusions (e.g. the candidate
briefly looking down or coughing). After flagging, the counter resets.

Args:
  n_faces: number of faces detected in the current frame
- `_add_flag(self, flag_type, detail)`
  - **Docstring:** Thread-safely append a proctor event to the flags list.

Args:
  flag_type: 'NO_FACE_DETECTED' or 'MULTIPLE_FACES'
  detail:    human-readable description with timestamp
- `get_frame(self)`
  - **Docstring:** Return the most recently captured webcam frame as a base64-encoded JPEG string.
Returns None if no frame has been captured yet.
Thread-safe (uses internal lock).
- `get_status(self)`
  - **Docstring:** Return the live proctoring status for the GUI.

Returns a dict with:
  face_count  — how many faces are currently in frame
  flags       — list of all flag events recorded so far
  flag_count  — total number of flags (shortcut for len(flags))
  active      — True while the background thread is running
- `get_summary(self)`
  - **Docstring:** Return the final proctoring report to be saved with the interview transcript.

Status thresholds (configurable):
  CLEAN              — fewer than 2 total flags (no concerns)
  FLAGGED            — 2–4 flags (minor concerns, worth reviewing)
  HIGHLY_SUSPICIOUS  — 5 or more flags (strong integrity concern)

Returns a dict with status, flag counts, event list, and session metadata.


### Functions
#### `start_proctoring(session_id)`
**Docstring:** Start webcam proctoring for the given interview session.

If a proctor is already running for this session_id (e.g. a reconnect),
it is stopped first to free the webcam before starting a new one.

Args:
  session_id: unique interview session identifier (from Flask session)
Returns:
  {'success': True/False, 'error': str or None}

#### `get_frame(session_id)`
**Docstring:** Get the latest base64-encoded JPEG frame for the given session.
Returns None if the session doesn't exist or no frame captured yet.

#### `get_proctor_status(session_id)`
**Docstring:** Return the live proctoring status dict for the session.
Returns a 'not active' dict if the session is not found.

#### `stop_proctoring(session_id)`
**Docstring:** Stop proctoring for the given session and return the final summary.

Removes the session from the global store (pop) so its resources are freed.
Returns a blank summary dict if the session was not found.

#### `check_webcam_available()`
**Docstring:** Check whether a webcam is connected and readable.

Opens camera index 0, attempts a single frame read, then immediately
releases it.  Used before starting an interview to show the user a
friendly error if no camera is available.

Returns:
  {'available': True/False, 'error': None or str}
