import collections
import json
import logging
import logging.handlers
import queue
import sys
import threading

logger = logging.getLogger(__name__)

# Paths Setup
from src.common import data_dir, data_path

# -- Structured JSON log formatter -------------------------------------------
class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for machine-readable log aggregation."""
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "module": record.module,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

# -- Setup Centralized Logging with rotation ----------------------------------
log_file_path = data_path("logs") / "app.log"
log_file_path.parent.mkdir(parents=True, exist_ok=True)

_rotating_handler = logging.handlers.RotatingFileHandler(
    log_file_path,
    maxBytes=5 * 1024 * 1024,  # 5 MB per file
    backupCount=5,
    encoding="utf-8",
)
_rotating_handler.setFormatter(
    logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
)

_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(
    logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_rotating_handler, _stream_handler],
)
logger = logging.getLogger(__name__)

# -- Unhandled exception hook -------------------------------------------------
def _excepthook(exc_type, exc_value, exc_tb):
    if not issubclass(exc_type, KeyboardInterrupt):
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _excepthook



def ensure_app_directories():
    """Ensure all critical runtime directories exist on disk."""
    for sub in ["resumes", "output", "output/txt", "output/nlp", "output/ranking", "output/scheduling", "output/interviews", "output/reports", "output/ssl"]:
        try:
            data_dir(sub)
        except Exception as e:
            logger.warning(f"Failed to create directory {sub}: {e}", exc_info=True)

ensure_app_directories()

RESUMES_FOLDER = data_dir("resumes")
OUTPUT_FOLDER = data_dir("output")

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
    except Exception as e:
        logger.warning(f"Failed to put log line in queue: {e}", exc_info=True)


def get_log_history() -> list:
    """Return a list of recent log lines."""
    with _log_lock:
        return list(log_history)

def _load_tasks():
    if TASK_STATE_FILE.exists():
        try:
            return json.loads(TASK_STATE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load tasks from {TASK_STATE_FILE}: {e}", exc_info=True)
            return {}
    return {}

def _save_tasks():
    try:
        TASK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASK_STATE_FILE.write_text(
            json.dumps(pipeline_tasks, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        logger.warning(f"Failed to save tasks to {TASK_STATE_FILE}: {e}", exc_info=True)

pipeline_tasks = _load_tasks()

# Clear stale running tasks
for _k in list(pipeline_tasks):
    if isinstance(pipeline_tasks[_k], dict) and pipeline_tasks[_k].get("status") == "running":
        pipeline_tasks[_k]["status"] = "error"
        pipeline_tasks[_k]["error"] = "Interrupted (app restarted)"
_save_tasks()
