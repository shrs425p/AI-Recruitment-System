import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import jsonify, render_template, request

from app.core import OUTPUT_FOLDER, _save_tasks, pipeline_tasks
from app.database import (
    create_run,
    delete_job_template,
    finish_run,
    get_all_job_templates,
    save_job_template,
    upsert_candidate,
)
from app.utils import login_required
from src.ranking_engine import (
    build_jd_prompt,
    call_ai,
    load_candidates,
    save_leaderboard_txt,
    save_scores_json,
    score_candidate,
)
from src.shortlist_report import save_shortlist_report


def register_ranking_routes(app):
    @app.route("/ranking")
    @login_required
    def ranking():
        nlp_count     = len(list((OUTPUT_FOLDER / "nlp").glob("*_nlp.json")))
        ranking_files = sorted((OUTPUT_FOLDER / "ranking").glob("ranking_scores*.json"), reverse=True)
        latest        = None
        if ranking_files:
            try:
                import json
                with open(ranking_files[0], encoding="utf-8") as f:
                    latest = json.load(f)
            except Exception:
                pass
        templates = get_all_job_templates()
        return render_template("ranking.html", nlp_count=nlp_count, ranking=latest, templates=templates)

    @app.route("/api/job-templates", methods=["GET"])
    @login_required
    def api_get_job_templates():
        return jsonify(get_all_job_templates())

    @app.route("/api/job-templates", methods=["POST"])
    @login_required
    def api_save_job_template():
        data = request.json or {}
        title = data.get("title", "").strip()
        jd_text = data.get("jd_text", "").strip()
        if not title or not jd_text:
            return jsonify({"error": "Title and Job Description text are required"}), 400
        template_id = save_job_template(title, jd_text)
        return jsonify({"success": True, "id": template_id, "title": title}), 201

    @app.route("/api/job-templates/<int:template_id>", methods=["DELETE"])
    @login_required
    def api_delete_job_template(template_id):
        delete_job_template(template_id)
        return jsonify({"success": True})

    @app.route("/api/rank", methods=["POST"])
    def api_rank():
        data    = request.json
        jd_text = data.get("jd_text", "").strip()
        if not jd_text:
            return jsonify({"error": "No JD provided"}), 400

        pipeline_tasks["ranking"] = {"status": "running", "started": time.time()}
        _save_tasks()

        nlp_path    = OUTPUT_FOLDER / "nlp"
        output_path = OUTPUT_FOLDER / "ranking"
        output_path.mkdir(exist_ok=True)

        jd_data = call_ai(build_jd_prompt(jd_text))
        if not jd_data:
            return jsonify({"error": "Failed to parse JD"}), 500

        candidates = load_candidates(nlp_path)
        if not candidates:
            return jsonify({"error": "No candidates found"}), 404

        scored = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(score_candidate, c, jd_data): c for c in candidates}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    scored.append(result)

        ranked = sorted(scored, key=lambda x: x.get("total_score", 0), reverse=True)
        save_leaderboard_txt(ranked, jd_data, output_path)
        save_scores_json(ranked, jd_data, output_path)
        shortlist = save_shortlist_report(ranked, jd_data, output_path)

        run_id = create_run("ranking", {"job_title": jd_data.get("job_title"), "count": len(ranked)})
        for r in ranked:
            upsert_candidate(
                run_id=run_id,
                name=r.get("candidate_name", ""),
                score=r.get("total_score", 0),
            )
        finish_run(run_id, "COMPLETED")

        pipeline_tasks["ranking"] = {
            "status": "done",
            "result": {
                "count": len(ranked),
                "job_title": jd_data.get("job_title"),
                "shortlist_report": shortlist.get("files", {}),
            },
        }
        _save_tasks()

        return jsonify({
            "success": True,
            "job_title": jd_data.get("job_title"),
            "ranked": ranked,
            "shortlist_report": shortlist,
        })
