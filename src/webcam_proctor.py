import base64  # Encode JPEG frame to base64 string for HTTP transport
import threading  # Background proctoring thread
import time  # sleep() in the capture loop
from datetime import datetime  # Timestamps for flag events

import cv2  # OpenCV — webcam capture, frame processing, Haar cascade
import numpy as np  # NumPy arrays used by OpenCV face detection results

# Try to import MediaPipe for high-accuracy face detection
try:
    import mediapipe as mp
    _MP_FACE  = mp.solutions.face_detection  # MediaPipe face detection module
    _MP_DRAW  = mp.solutions.drawing_utils   # Utility to draw detection boxes
    _MP_AVAILABLE = True
except (ImportError, AttributeError):
    _MP_AVAILABLE = False  # Fall back to Haar cascade (mediapipe missing or incompatible version)
    print("[PROCTOR] mediapipe unavailable — falling back to Haar cascade.")
    print("  For mediapipe support install: pip install mediapipe==0.10.9")

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# How often to run the proctor logic (face count evaluation).
# The camera reads frames at ~30fps, but we only flag every CHECK_INTERVAL seconds
# to avoid over-flagging due to brief occlusion (e.g. scratching nose).
CHECK_INTERVAL        = 2.0

# How many consecutive CHECK_INTERVAL periods must show no face before flagging.
# e.g. NO_FACE_THRESHOLD=3 means absence for 6 seconds (3 × 2s) before a flag.
NO_FACE_THRESHOLD     = 3

# How many consecutive periods must show multiple faces before flagging.
MULTI_FACE_THRESHOLD  = 2

# Resolution of captured frames — small enough for smooth streaming
FRAME_WIDTH           = 320
FRAME_HEIGHT          = 240

# JPEG quality for base64 streaming (lower = smaller bytes, faster transfer)
JPEG_QUALITY          = 60

# Path to OpenCV's pre-trained frontal face Haar cascade XML file
CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'

# ─────────────────────────────────────────────
# PROCTOR SESSION
# ─────────────────────────────────────────────

class WebcamProctor:
    """
    Manages webcam-based proctoring for one interview session.

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
    """

    def __init__(self, session_id: str):
        self.session_id      = session_id   # unique identifier for this interview session
        self.active          = False         # set to True when proctoring is running
        self.cap             = None          # OpenCV VideoCapture object
        self._detector       = None          # MediaPipe FaceDetection or CascadeClassifier
        self._thread         = None          # background proctoring thread
        self._lock           = threading.Lock()  # protects shared state

        # Shared state (safe to read from any thread via get_frame / get_status)
        self.latest_frame_b64 = None    # most recent webcam frame encoded as base64 JPEG
        self.face_count        = 0      # number of faces in the most recent frame
        self.flags             = []     # list of flag event dicts recorded so far
        self.flag_counts       = {
            'NO_FACE':     0,   # running count of consecutive no-face intervals
            'MULTI_FACE':  0,   # running count of consecutive multi-face intervals
        }
        self.total_frames_checked = 0   # total frames processed (for analytics)
        self.started_at           = None  # ISO timestamp when proctoring started
        self.last_check_time      = 0     # time.time() of last proctor logic run

    # ── Setup ──────────────────────────────────

    def start(self) -> dict:
        """
        Open the webcam and start the proctoring background thread.

        Returns:
          {'success': True, 'error': None} on success
          {'success': False, 'error': str} if webcam unavailable
        """
        try:
            if _MP_AVAILABLE:
                # model_selection=0 → optimised for faces within ~2 m (webcam range)
                self._detector = _MP_FACE.FaceDetection(
                    model_selection=0, min_detection_confidence=0.5
                )
            else:
                cascade = cv2.CascadeClassifier(CASCADE_PATH)
                if cascade.empty():
                    return {'success': False, 'error': 'Haar cascade not found and mediapipe not installed'}
                self._detector = cascade

            self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                return {'success': False, 'error': 'No webcam found or access denied'}

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, 30)

            self.active     = True
            self.started_at = datetime.now().isoformat()
            # daemon=True: thread won't prevent the process from exiting if the app closes
            self._thread    = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

            return {'success': True, 'error': None}

        except Exception as e:
            # Release webcam if it was opened but setup failed
            if self.cap and self.cap.isOpened():
                self.cap.release()
            return {'success': False, 'error': str(e)}

    def stop(self) -> dict:
        """
        Stop proctoring: signal the thread to exit, wait for it, then
        release the webcam and close MediaPipe detector.

        Returns a final proctor summary dict (same as get_summary()).
        """
        self.active = False
        if self._thread:
            self._thread.join(timeout=5)  # wait up to 5 seconds for thread to finish
        if self.cap:
            self.cap.release()  # release the webcam so other apps can use it
        if _MP_AVAILABLE and self._detector:
            self._detector.close()  # free MediaPipe resources

        return self.get_summary()

    # ── Background Thread ───────────────────────

    def _run(self):
        """
        Main proctoring loop — executes in the background daemon thread.

        Continuously reads webcam frames, runs face detection,
        annotates frames with status text, encodes them to base64 JPEG,
        and every CHECK_INTERVAL seconds evaluates the face count
        to decide whether to raise a proctor flag.
        """
        while self.active:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    with self._lock:
                        self.face_count = 0
                        self.total_frames_checked += 1

                    now_time = time.time()
                    if now_time - self.last_check_time >= CHECK_INTERVAL:
                        self._check_proctor(0)
                        self.last_check_time = now_time

                    time.sleep(0.033)
                    continue

                # Flip horizontally so it looks like a mirror to the candidate
                frame = cv2.flip(frame, 1)

                # ── Face detection ──────────────────────────────────
                fh, fw = frame.shape[:2]  # frame height and width in pixels
                face_boxes = []  # list of (x, y, w, h) tuples for each detected face

                if _MP_AVAILABLE:
                    # Convert BGR (OpenCV format) to RGB (MediaPipe format)
                    rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    result = self._detector.process(rgb)
                    for det in (result.detections or []):
                        # MediaPipe returns relative coordinates (0.0–1.0)
                        # Multiply by frame dimensions to get pixel coordinates
                        bb = det.location_data.relative_bounding_box
                        x  = max(0, int(bb.xmin * fw))
                        y  = max(0, int(bb.ymin * fh))
                        bw = int(bb.width  * fw)
                        bh = int(bb.height * fh)
                        face_boxes.append((x, y, bw, bh))
                else:
                    # Haar cascade expects a grayscale image
                    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = self._detector.detectMultiScale(
                        gray, scaleFactor=1.1, minNeighbors=5,
                        minSize=(60, 60), flags=cv2.CASCADE_SCALE_IMAGE
                    )
                    if isinstance(faces, np.ndarray):
                        face_boxes = [tuple(f) for f in faces]  # convert to list of tuples

                n_faces = len(face_boxes)  # 0 = no one, 1 = normal, 2+ = suspicious

                # ── Annotate frame with status text and face boxes ──
                display_frame = frame.copy()  # keep the original frame unmodified
                color = (0, 200, 0)  # green = candidate present (all OK)

                if n_faces == 0:
                    color = (0, 0, 255)  # red = no face
                    cv2.putText(display_frame, 'NO FACE DETECTED', (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                elif n_faces > 1:
                    color = (0, 165, 255)  # orange = multiple faces
                    cv2.putText(display_frame, f'MULTIPLE FACES: {n_faces}', (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                else:
                    cv2.putText(display_frame, 'CANDIDATE DETECTED', (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                for (x, y, bw, bh) in face_boxes:
                    cv2.rectangle(display_frame, (x, y), (x + bw, y + bh), color, 2)

                # Timestamp
                ts = datetime.now().strftime('%H:%M:%S')
                cv2.putText(display_frame, ts, (FRAME_WIDTH - 80, FRAME_HEIGHT - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

                # ── Encode frame as base64 JPEG for HTTP streaming ──────────
                # imencode writes to an in-memory buffer (no disk I/O)
                _, buf = cv2.imencode('.jpg', display_frame,
                                      [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                # Decode bytes to ASCII string so it fits in a JSON response
                b64 = base64.b64encode(buf).decode('utf-8')

                # ── Write shared state atomically under lock ──────────────────
                with self._lock:
                    self.face_count        = n_faces
                    self.latest_frame_b64  = b64
                    self.total_frames_checked += 1

                # ── Proctor flag check at coarser interval than frame rate ────
                # Avoids flooding the flags list on every captured frame
                now_time = time.time()
                if now_time - self.last_check_time >= CHECK_INTERVAL:
                    self._check_proctor(n_faces)
                    self.last_check_time = now_time

                time.sleep(0.033)  # target ~30fps; yields CPU between frames

            except Exception as e:
                print(f'[WEBCAM] Frame error: {e}')
                time.sleep(0.5)

    def _check_proctor(self, n_faces: int):
        """
        Evaluate the most recent face count and increment running counters.

        A flag is only raised once the consecutive-absence count reaches the
        configured threshold (NO_FACE_THRESHOLD or MULTI_FACE_THRESHOLD).
        This prevents false flags from brief occlusions (e.g. the candidate
        briefly looking down or coughing). After flagging, the counter resets.

        Args:
          n_faces: number of faces detected in the current frame
        """
        now = datetime.now().strftime('%H:%M:%S')

        if n_faces == 0:
            self.flag_counts['NO_FACE'] += 1
            if self.flag_counts['NO_FACE'] >= NO_FACE_THRESHOLD:
                self._add_flag('NO_FACE_DETECTED',
                               f'Candidate not visible at {now}')
                self.flag_counts['NO_FACE'] = 0  # reset after flagging
        else:
            self.flag_counts['NO_FACE'] = 0

        if n_faces > 1:
            self.flag_counts['MULTI_FACE'] += 1
            if self.flag_counts['MULTI_FACE'] >= MULTI_FACE_THRESHOLD:
                self._add_flag('MULTIPLE_FACES',
                               f'{n_faces} faces detected at {now}')
                self.flag_counts['MULTI_FACE'] = 0
        else:
            self.flag_counts['MULTI_FACE'] = 0

    def _add_flag(self, flag_type: str, detail: str):
        """
        Thread-safely append a proctor event to the flags list.

        Args:
          flag_type: 'NO_FACE_DETECTED' or 'MULTIPLE_FACES'
          detail:    human-readable description with timestamp
        """
        with self._lock:
            self.flags.append({
                'type':      flag_type,
                'detail':    detail,
                'timestamp': datetime.now().isoformat()
            })
        print(f'[PROCTOR] {flag_type}: {detail}')

    # ── Public API ─────────────────────────────

    def get_frame(self) -> "str | None":
        """
        Return the most recently captured webcam frame as a base64-encoded JPEG string.
        Returns None if no frame has been captured yet.
        Thread-safe (uses internal lock).
        """
        with self._lock:
            return self.latest_frame_b64

    def get_status(self) -> dict:
        """
        Return the live proctoring status for the GUI.

        Returns a dict with:
          face_count  — how many faces are currently in frame
          flags       — list of all flag events recorded so far
          flag_count  — total number of flags (shortcut for len(flags))
          active      — True while the background thread is running
        """
        with self._lock:
            return {
                'face_count': self.face_count,
                'flags':      list(self.flags),
                'flag_count': len(self.flags),
                'active':     self.active,
            }

    def get_summary(self) -> dict:
        """
        Return the final proctoring report to be saved with the interview transcript.

        Status thresholds (configurable):
          CLEAN              — fewer than 2 total flags (no concerns)
          FLAGGED            — 2–4 flags (minor concerns, worth reviewing)
          HIGHLY_SUSPICIOUS  — 5 or more flags (strong integrity concern)

        Returns a dict with status, flag counts, event list, and session metadata.
        """
        with self._lock:
            total_flags  = len(self.flags)
            no_face_flags = sum(1 for f in self.flags if f['type'] == 'NO_FACE_DETECTED')
            multi_flags   = sum(1 for f in self.flags if f['type'] == 'MULTIPLE_FACES')
            status = 'CLEAN'
            if total_flags >= 5:
                status = 'HIGHLY_SUSPICIOUS'
            elif total_flags >= 2:
                status = 'FLAGGED'

            return {
                'status':          status,
                'total_flags':     total_flags,
                'no_face_flags':   no_face_flags,
                'multi_face_flags': multi_flags,
                'events':          list(self.flags),
                'frames_checked':  self.total_frames_checked,
                'started_at':      self.started_at,
            }


# ─────────────────────────────────────────────────────────────────
# MODULE-LEVEL SESSION STORE AND ROUTE-HANDLER FUNCTIONS
# ─────────────────────────────────────────────────────────────────
# Each interview session (identified by session_id) gets its own
# WebcamProctor instance stored in this dict.  Flask route handlers
# in app.py call the functions below rather than touching the dict directly.
# ─────────────────────────────────────────────────────────────────

_proctor_sessions = {}  # type: dict[str, WebcamProctor]


def start_proctoring(session_id: str) -> dict:
    """
    Start webcam proctoring for the given interview session.

    If a proctor is already running for this session_id (e.g. a reconnect),
    it is stopped first to free the webcam before starting a new one.

    Args:
      session_id: unique interview session identifier (from Flask session)
    Returns:
      {'success': True/False, 'error': str or None}
    """
    if session_id in _proctor_sessions:
        _proctor_sessions[session_id].stop()

    wp = WebcamProctor(session_id)
    result = wp.start()
    if result['success']:
        _proctor_sessions[session_id] = wp
    return result


def get_frame(session_id: str) -> "str | None":
    """
    Get the latest base64-encoded JPEG frame for the given session.
    Returns None if the session doesn't exist or no frame captured yet.
    """
    wp = _proctor_sessions.get(session_id)
    return wp.get_frame() if wp else None


def get_proctor_status(session_id: str) -> dict:
    """
    Return the live proctoring status dict for the session.
    Returns a 'not active' dict if the session is not found.
    """
    wp = _proctor_sessions.get(session_id)
    if wp:
        return wp.get_status()
    return {'face_count': 0, 'flags': [], 'flag_count': 0, 'active': False}


def stop_proctoring(session_id: str) -> dict:
    """
    Stop proctoring for the given session and return the final summary.

    Removes the session from the global store (pop) so its resources are freed.
    Returns a blank summary dict if the session was not found.
    """
    wp = _proctor_sessions.pop(session_id, None)
    if wp:
        return wp.stop()
    return {'status': 'UNKNOWN', 'total_flags': 0, 'no_face_flags': 0,
            'multi_face_flags': 0, 'events': [], 'frames_checked': 0, 'started_at': None}


def check_webcam_available() -> dict:
    """
    Check whether a webcam is connected and readable.

    Opens camera index 0, attempts a single frame read, then immediately
    releases it.  Used before starting an interview to show the user a
    friendly error if no camera is available.

    Returns:
      {'available': True/False, 'error': None or str}
    """
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            return {'available': ret, 'error': None if ret else 'Could not read frame'}
        else:
            return {'available': False, 'error': 'No webcam found or access denied'}
    except Exception as e:
        return {'available': False, 'error': str(e)}
