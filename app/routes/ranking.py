import csv
import io
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Response, jsonify, render_template, request

import config as cfg

logger = logging.getLogger(__name__)

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
    if "ranking" in app.view_functions:
        return
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
            except Exception as e:
                logger.warning('Caught exception: %s', e, exc_info=True)
        templates = get_all_job_templates()
        from app.database import get_setting
        saved_jd = get_setting("LAST_JD_TEXT", "")

        scoring_preset = getattr(cfg, "SCORING_PRESET", "default")
        try:
            raw_w = getattr(cfg, "SCORING_WEIGHTS", "{}")
            scoring_weights = json.loads(raw_w) if raw_w else {}
        except Exception:
            scoring_weights = {"skills_match": 35, "experience_years": 20, "domain_match": 20, "education": 15, "certifications": 10}
        try:
            raw_ko = getattr(cfg, "KNOCKOUT_RULES", "{}")
            knockout_rules = json.loads(raw_ko) if raw_ko else {}
        except Exception:
            knockout_rules = {"min_experience_years": 0, "required_skills": [], "required_certifications": []}

        from app.database import get_all_candidate_notes
        candidate_notes = get_all_candidate_notes()

        return render_template(
            "ranking.html",
            nlp_count=nlp_count,
            ranking=latest,
            templates=templates,
            saved_jd=saved_jd,
            scoring_preset=scoring_preset,
            scoring_weights=scoring_weights,
            knockout_rules=knockout_rules,
            candidate_notes=candidate_notes,
        )

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

    @app.route("/api/save-jd", methods=["POST"])
    @login_required
    def api_save_jd():
        data = request.json or {}
        jd_text = data.get("jd_text", "").strip()
        if not jd_text:
            return jsonify({"success": False, "error": "Empty JD"}), 400
        from app.database import set_setting
        set_setting("LAST_JD_TEXT", jd_text)
        return jsonify({"success": True})

    @app.route("/api/rank", methods=["POST"])
    @login_required
    def api_rank():
        data           = request.json or {}
        jd_text        = data.get("jd_text", "").strip()
        weights        = data.get("weights")
        knockout_rules = data.get("knockout_rules")

        if not weights:
            try:
                raw_w = getattr(cfg, "SCORING_WEIGHTS", "")
                if raw_w:
                    weights = json.loads(raw_w)
            except Exception:
                weights = None

        if not knockout_rules:
            try:
                raw_ko = getattr(cfg, "KNOCKOUT_RULES", "")
                if raw_ko:
                    knockout_rules = json.loads(raw_ko)
            except Exception:
                knockout_rules = None

        if not jd_text:
            return jsonify({"error": "No JD provided"}), 400

        # Persist JD so it survives tab switches and restarts
        from app.database import set_setting
        set_setting("LAST_JD_TEXT", jd_text)

        pipeline_tasks["ranking"] = {"status": "running", "started": time.time()}
        _save_tasks()

        nlp_path    = OUTPUT_FOLDER / "nlp"
        output_path = OUTPUT_FOLDER / "ranking"
        output_path.mkdir(exist_ok=True)

        try:
            try:
                jd_data = call_ai(build_jd_prompt(jd_text))
            except Exception as e:
                pipeline_tasks["ranking"] = {"status": "error", "error": str(e)}
                _save_tasks()
                return jsonify({
                    "error": f"AI Parsing Error: {e}. If your Cloud API quota is exhausted, switch to Privacy Mode in Settings to use your offline Ollama model without limits."
                }), 429 if "429" in str(e) else 500
            if not jd_data:
                pipeline_tasks["ranking"] = {"status": "error", "error": "Failed to parse Job Description."}
                _save_tasks()
                return jsonify({"error": "Failed to parse Job Description. Please try again."}), 500

            # Fallback if AI returned empty template
            if not jd_data.get("job_title") or jd_data.get("job_title").startswith("<"):
                from src.ranking_engine import _extract_title_fallback
                jd_data["job_title"] = _extract_title_fallback(jd_text)

            candidates = load_candidates(nlp_path)
            if not candidates:
                pipeline_tasks["ranking"] = {"status": "error", "error": "No candidates found."}
                _save_tasks()
                return jsonify({"error": "No candidates found"}), 404

            scored = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(score_candidate, c, jd_data, weights=weights, knockout_rules=knockout_rules): c
                    for c in candidates
                }
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        scored.append(result)

            ranked = sorted(scored, key=lambda x: x.get("total_score", 0), reverse=True)
            save_leaderboard_txt(ranked, jd_data, output_path)
            save_scores_json(ranked, jd_data, output_path, weights=weights, knockout_rules=knockout_rules)
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
        except Exception as ex:
            pipeline_tasks["ranking"] = {"status": "error", "error": str(ex)}
            _save_tasks()
            logger.exception("Ranking pipeline execution error: %s", ex)
            return jsonify({"error": f"Ranking execution error: {ex}"}), 500

    @app.route("/api/ranking/export/csv", methods=["GET"])
    @login_required
    def api_export_ranking_csv():
        ranking_files = sorted((OUTPUT_FOLDER / "ranking").glob("ranking_scores*.json"), reverse=True)
        if not ranking_files:
            return jsonify({"error": "No ranking data available to export"}), 404

        try:
            with open(ranking_files[0], encoding="utf-8") as f:
                ranking_data = json.load(f)
        except Exception as e:
            return jsonify({"error": f"Failed reading ranking data: {e}"}), 500

        job_title = ranking_data.get("job_description", {}).get("job_title", "Candidates")
        ranked = ranking_data.get("ranked_candidates", [])
        if not ranked and isinstance(ranking_data, list):
            ranked = ranking_data

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Rank",
            "Name",
            "Email",
            "Total Score",
            "Skills Match",
            "Experience Score",
            "Strengths",
            "Hire Recommendation",
        ])

        nlp_path = OUTPUT_FOLDER / "nlp"
        for idx, c in enumerate(ranked, 1):
            name = c.get("candidate_name") or "Unknown"
            email = c.get("email", "")
            source_file = c.get("source_file") or c.get("_source_file") or ""

            # Attempt lookup from candidate's NLP file if email not in score dict
            if not email and nlp_path.exists():
                candidates_to_check = []
                if source_file:
                    candidates_to_check.extend([nlp_path / f"{source_file}.json", nlp_path / f"{source_file}_nlp.json"])
                for p in nlp_path.glob("*_nlp.json"):
                    candidates_to_check.append(p)

                c_name_lower = name.lower()
                for nf in candidates_to_check:
                    if nf.exists():
                        try:
                            with open(nf, encoding="utf-8") as fh:
                                ndata = json.load(fh)
                            p_name = ndata.get("personal_info", {}).get("name", "").lower()
                            if p_name == c_name_lower or c_name_lower in p_name:
                                email = ndata.get("personal_info", {}).get("email", "")
                                if email:
                                    break
                        except Exception:
                            pass

            scores = c.get("scores", {})
            skills_score = scores.get("skills_match", {})
            skills_val = skills_score.get("score", c.get("skills_score", 0)) if isinstance(skills_score, dict) else skills_score

            exp_score = scores.get("experience_years", {})
            exp_val = exp_score.get("score", c.get("experience_score", 0)) if isinstance(exp_score, dict) else exp_score

            raw_strengths = c.get("strengths", [])
            strengths_str = "; ".join(raw_strengths) if isinstance(raw_strengths, list) else str(raw_strengths)

            hire_rec = c.get("hire_recommendation") or c.get("overall_verdict") or ("Knocked Out" if c.get("knocked_out") else "Review")

            writer.writerow([
                c.get("rank", idx),
                name,
                email,
                c.get("total_score", 0),
                skills_val,
                exp_val,
                strengths_str,
                hire_rec,
            ])

        csv_data = output.getvalue()
        safe_title = "".join(ch if ch.isalnum() else "_" for ch in job_title).strip("_")
        filename = f"candidate_rankings_{safe_title or 'export'}.csv"
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.route("/api/candidates/notes", methods=["GET"])
    @login_required
    def api_get_candidate_notes():
        candidate_name = request.args.get("candidate_name")
        if candidate_name:
            from app.database import get_candidate_note
            note = get_candidate_note(candidate_name)
            return jsonify(note or {})
        from app.database import get_all_candidate_notes
        return jsonify(get_all_candidate_notes())

    @app.route("/api/candidates/notes", methods=["POST"])
    @login_required
    def api_save_candidate_notes():
        data = request.get_json(silent=True) or request.form.to_dict()
        candidate_name = (data.get("candidate_name") or "").strip()
        if not candidate_name:
            return jsonify({"error": "Candidate name is required"}), 400
        note = data.get("note", "")
        tags = data.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = [t.strip() for t in tags.split(",") if t.strip()]
        source_file = data.get("source_file", "")
        from app.database import save_candidate_note
        save_candidate_note(candidate_name, note=note, tags=tags, source_file=source_file)
        return jsonify({"success": True, "candidate_name": candidate_name, "note": note, "tags": tags})

