import collections
import json
import logging
import queue
import re
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Paths Setup
from src.common import data_dir, data_path

# Setup Centralized Logging
log_file_path = data_path("logs") / "app.log"
log_file_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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


def purge_candidate_files(candidate_info: dict):
    """Securely delete all files on disk related to the candidate across all pipeline stages."""
    name = candidate_info.get("name", "")
    source_file = candidate_info.get("source_file", "")
    stem = Path(source_file).stem if source_file else ""
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name) if name else ""

    # 1. Resumes folder
    if source_file:
        for f in [RESUMES_FOLDER / source_file, RESUMES_FOLDER / f"{source_file}.enc"]:
            if f.exists():
                try:
                    f.unlink()
                except Exception as e:
                    logger.warning("Failed to delete resume file %s: %s", f, e)

    # 2. Text folder
    txt_folder = OUTPUT_FOLDER / "txt"
    if txt_folder.exists() and stem:
        for f in txt_folder.glob(f"{stem}*.txt"):
            try:
                f.unlink()
            except Exception as e:
                logger.warning("Failed to delete text file %s: %s", f, e)

    # 3. NLP folder
    nlp_folder = OUTPUT_FOLDER / "nlp"
    if nlp_folder.exists() and stem:
        for f in nlp_folder.glob(f"{stem}*.json"):
            try:
                f.unlink()
            except Exception as e:
                logger.warning("Failed to delete nlp file %s: %s", f, e)

    # 4. Interviews folder
    int_folder = OUTPUT_FOLDER / "interviews"
    if int_folder.exists():
        patterns = []
        if safe_name:
            patterns.append(f"interview_{safe_name}*.json")
        if stem:
            patterns.append(f"interview_{stem}*.json")
        for pat in patterns:
            for f in int_folder.glob(pat):
                try:
                    f.unlink()
                except Exception as e:
                    logger.warning("Failed to delete interview file %s: %s", f, e)

    # 5. Reports folder
    rep_folder = OUTPUT_FOLDER / "reports"
    if rep_folder.exists():
        patterns = []
        if safe_name:
            patterns.extend([f"report_{safe_name}*.json", f"report_{safe_name}*.pdf"])
        if stem:
            patterns.extend([f"report_{stem}*.json", f"report_{stem}*.pdf"])
        for pat in patterns:
            for f in rep_folder.glob(pat):
                try:
                    f.unlink()
                except Exception as e:
                    logger.warning("Failed to delete report file %s: %s", f, e)

    # 6. Ranking leaderboard cleaning
    rank_folder = OUTPUT_FOLDER / "ranking"
    if rank_folder.exists() and name:
        for rf in rank_folder.glob("ranking_scores*.json"):
            try:
                with open(rf, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "ranked_candidates" in data:
                    orig_len = len(data["ranked_candidates"])
                    data["ranked_candidates"] = [c for c in data["ranked_candidates"] if c.get("candidate_name") != name]
                    if len(data["ranked_candidates"]) != orig_len:
                        with open(rf, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=4)
            except Exception as e:
                logger.warning("Failed to clean candidate from ranking file %s: %s", rf, e)

    # 7. Proctoring, snapshots, recordings folders
    for sub in ["proctoring", "recordings", "snapshots"]:
        try:
            folder = data_dir(sub)
            if folder.exists():
                for pat in [f"*{safe_name}*", f"*{stem}*"]:
                    for f in folder.glob(pat):
                        try:
                            f.unlink()
                        except Exception as e:
                            logger.warning("Failed to delete proctoring asset %s: %s", f, e)
        except Exception:
            pass

