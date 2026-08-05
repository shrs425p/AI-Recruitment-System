import json
import threading
import time

from flask import jsonify, render_template

from src import privacy_setup
from app.core import OUTPUT_FOLDER, _save_tasks, pipeline_tasks
from app.database import create_run, finish_run, upsert_candidate
from app.utils import login_required

# Global status for privacy Setup
privacy_setup_status = {
    "running": False,
    "percent": 0,
    "message": "Idle",
    "success": False,
    "log": []
}
privacy_setup_thread = None

def register_nlp_routes(app):
    @app.route("/nlp")
    @login_required
    def nlp():
        txt_count  = len(list((OUTPUT_FOLDER / "txt").glob("*.txt")))
        nlp_count  = len(list((OUTPUT_FOLDER / "nlp").glob("*_nlp.json")))
        return render_template("nlp.html", txt_count=txt_count, nlp_count=nlp_count)

    @app.route("/api/process-nlp", methods=["POST"])
    def api_process_nlp():
        input_path  = OUTPUT_FOLDER / "txt"
        output_path = OUTPUT_FOLDER / "nlp"
        txt_files   = list(input_path.glob("*.txt"))
        results     = {"success": [], "skipped": [], "failed": []}
        run_id = create_run("nlp", {"file_count": len(txt_files)})

        if not txt_files:
            finish_run(run_id, "COMPLETED", results)
            return jsonify(results)

        pipeline_tasks["nlp"] = {"status": "running", "started": time.time()}
        _save_tasks()

        import asyncio

        from src.nlp_extractor import process_file_async

        async def run_batch():
            sem = asyncio.Semaphore(4)
            async def limited_process(f):
                async with sem:
                    try:
                        is_new = await process_file_async(f, output_path)
                        return f, is_new, None
                    except Exception as ex:
                        return f, False, str(ex)
            tasks = [limited_process(f) for f in txt_files]
            return await asyncio.gather(*tasks)

        try:
            batch_results = asyncio.run(run_batch())
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, run_batch())
                batch_results = future.result()

        for txt_file, is_new, err in batch_results:
            if err:
                results["failed"].append({"file": txt_file.name, "error": err})
            elif is_new:
                results["success"].append(txt_file.name)
                nlp_json = output_path / (txt_file.stem + "_nlp.json")
                if nlp_json.exists():
                    try:
                        ndata = json.loads(nlp_json.read_text(encoding="utf-8"))
                        pi = ndata.get("personal_info", {})
                        upsert_candidate(
                            run_id=run_id,
                            name=pi.get("name", txt_file.stem),
                            email=pi.get("email", ""),
                            source_file=txt_file.name,
                            skills=ndata.get("skills", {}).get("technical_skills", []),
                        )
                    except Exception:
                        pass
            else:
                results["skipped"].append(txt_file.name)

        finish_run(run_id, "COMPLETED", results)
        pipeline_tasks["nlp"] = {"status": "done", "result": results}
        _save_tasks()
        return jsonify(results)

    @app.route("/api/privacy-setup", methods=["POST"])
    def api_privacy_setup():
        global privacy_setup_thread
        if privacy_setup_status["running"]:
            return jsonify({"error": "Installation is already running"}), 400

        privacy_setup_status["running"] = True
        privacy_setup_status["percent"] = 5
        privacy_setup_status["message"] = "Initializing installer..."
        privacy_setup_status["success"] = False
        privacy_setup_status["log"] = ["Starting local AI installation..."]

        def on_progress(percent, msg):
            privacy_setup_status["percent"] = percent
            privacy_setup_status["message"] = msg
            privacy_setup_status["log"].append(f"[{percent}%] {msg}")

        def _run():
            try:
                success = privacy_setup.run_setup_process(on_progress)
                privacy_setup_status["success"] = success
                if success:
                    privacy_setup_status["percent"] = 100
                    privacy_setup_status["message"] = "Local AI ready!"
                    privacy_setup_status["log"].append("[Success] Ollama and Llama models configured.")
                else:
                    privacy_setup_status["percent"] = 0
                    privacy_setup_status["message"] = "Installation failed."
                    privacy_setup_status["log"].append("[FAILED] Installation aborted due to error.")
            except Exception as e:
                privacy_setup_status["percent"] = 0
                privacy_setup_status["message"] = f"Error: {e}"
                privacy_setup_status["log"].append(f"[ERROR] {e}")
            finally:
                privacy_setup_status["running"] = False

        privacy_setup_thread = threading.Thread(target=_run, daemon=True)
        privacy_setup_thread.start()
        return jsonify({"success": True})

    @app.route("/api/privacy-status", methods=["GET"])
    def api_privacy_status():
        return jsonify(privacy_setup_status)

    @app.route("/api/privacy-cancel", methods=["POST"])
    def api_privacy_cancel():
        privacy_setup.cancel_setup()
        privacy_setup_status["running"] = False
        privacy_setup_status["message"] = "Cancelled"
        privacy_setup_status["log"].append("[INFO] Installation cancelled by user.")
        return jsonify({"success": True})
