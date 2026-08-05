import collections
import json
import queue
import threading

# Paths Setup
from .app_paths import data_path


def ensure_app_directories():
    """Ensure all critical runtime directories exist on disk."""
    for sub in ["resumes", "output", "output/txt", "output/nlp", "output/ranking", "output/scheduling", "output/interviews", "output/reports", "output/ssl"]:
        try:
            data_path(sub).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

ensure_app_directories()

RESUMES_FOLDER = data_path("resumes")
OUTPUT_FOLDER = data_path("output")

# Centralized State
TASK_STATE_FILE = OUTPUT_FOLDER / "task_state.json"
log_queue: queue.Queue = queue.Queue(maxsize=1000)
log_history: collections.deque = collections.deque(maxlen=200)
_log_lock = threading.Lock()


def add_log_line(line: str):
    """Store log line in history and queue for streaming clients."""
    with _log_lock:
        log_history.append(line)
    try:
        log_queue.put_nowait(line)
    except Exception:
        pass


def get_log_history() -> list:
    """Return a list of recent log lines."""
    with _log_lock:
        return list(log_history)

def _load_tasks():
    if TASK_STATE_FILE.exists():
        try:
            return json.loads(TASK_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_tasks():
    try:
        TASK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASK_STATE_FILE.write_text(
            json.dumps(pipeline_tasks, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception:
        pass

pipeline_tasks = _load_tasks()

# Clear stale running tasks
for _k in list(pipeline_tasks):
    if isinstance(pipeline_tasks[_k], dict) and pipeline_tasks[_k].get("status") == "running":
        pipeline_tasks[_k]["status"] = "error"
        pipeline_tasks[_k]["error"] = "Interrupted (app restarted)"
_save_tasks()
