import json
import queue

# Paths Setup
from .app_paths import data_path

RESUMES_FOLDER = data_path("resumes")
OUTPUT_FOLDER = data_path("output")
RESUMES_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)

(OUTPUT_FOLDER / "txt").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "nlp").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "ranking").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "scheduling").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "interviews").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "reports").mkdir(parents=True, exist_ok=True)
(OUTPUT_FOLDER / "ssl").mkdir(parents=True, exist_ok=True)

# Centralized State
TASK_STATE_FILE = OUTPUT_FOLDER / "task_state.json"
log_queue = queue.Queue(maxsize=1000)

def _load_tasks():
    if TASK_STATE_FILE.exists():
        try:
            return json.loads(TASK_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_tasks():
    try:
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
