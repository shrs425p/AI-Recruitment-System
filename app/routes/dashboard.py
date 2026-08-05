import json
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from flask import jsonify, redirect, render_template, url_for

from app.core import OUTPUT_FOLDER, RESUMES_FOLDER, _save_tasks, pipeline_tasks
from app.database import create_interview_token, create_run, finish_run, upsert_candidate
from app.database import save_schedule as db_save_schedule
from app.utils import login_required
from src.nlp_extractor import process_file_async

# Imports for auto-pipeline
from src.pdf_to_txt import process_file as pdf_process_file
from src.ranking_engine import load_candidates, save_leaderboard_txt, save_scores_json, score_candidate
from src.report_generator import (
    calculate_combined_score,
    generate_ai_report,
    load_interview_transcripts,
    save_final_summary,
    save_report_json,
    save_report_txt,
)
from src.scheduling import (
    SLOTS_TO_OFFER,
    generate_ics,
    load_top_candidates,
    save_schedule_summary,
)
from src.shortlist_report import save_shortlist_report

AUTO_PIPELINE_STEPS = 5
_pipeline_lock = threading.Lock()


def _set_auto_pipeline_status(status, message, **extra):
    with _pipeline_lock:
        current = pipeline_tasks.setdefault("auto_pipeline", {})
        current.update({
            "status": status,
            "message": message,
            "updated": time.time(),
            **extra,
        })
        _save_tasks()


def _run_auto_pipeline_job():
    results = {
        "txt": {"success": [], "skipped": [], "failed": []},
        "nlp": {"success": [], "skipped": [], "failed": []},
        "ranking": {"success": False, "message": "Skipped", "count": 0},
        "scheduling": {"success": False, "message": "Skipped", "count": 0},
        "reports": {"success": False, "message": "Skipped", "count": 0},
    }

    try:
        _set_auto_pipeline_status(
            "running",
            f"Step 1/{AUTO_PIPELINE_STEPS}: Converting resumes to plain text...",
            started=time.time(),
            step="txt",
            result=results,
        )

        input_path = RESUMES_FOLDER
        output_txt_path = OUTPUT_FOLDER / "txt"
        output_txt_path.mkdir(parents=True, exist_ok=True)
        pdf_files = [
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in [".pdf", ".png", ".jpg", ".jpeg"]
        ]

        for f in pdf_files:
            try:
                is_new = pdf_process_file(f, output_txt_path)
                if is_new:
                    results["txt"]["success"].append(f.name)
                else:
                    results["txt"]["skipped"].append(f.name)
            except Exception as e:
                results["txt"]["failed"].append({"file": f.name, "error": str(e)})

        _set_auto_pipeline_status(
            "running",
            f"Step 2/{AUTO_PIPELINE_STEPS}: Extracting structured candidate profiles...",
            step="nlp",
            result=results,
        )

        output_nlp_path = OUTPUT_FOLDER / "nlp"
        output_nlp_path.mkdir(parents=True, exist_ok=True)
        txt_files = list(output_txt_path.glob("*.txt"))

        if txt_files:
            run_id = create_run("nlp", {"file_count": len(txt_files), "source": "auto_pipeline"})
            import asyncio

            async def run_batch():
                sem = asyncio.Semaphore(4)

                async def limited_process(f):
                    async with sem:
                        try:
                            is_new = await process_file_async(f, output_nlp_path)
                            return f, is_new, None
                        except Exception as ex:
                            return f, False, str(ex)

                tasks = [limited_process(f) for f in txt_files]
                return await asyncio.gather(*tasks)

            batch_results = asyncio.run(run_batch())

            for txt_file, is_new, err in batch_results:
                if err:
                    results["nlp"]["failed"].append({"file": txt_file.name, "error": err})
                elif is_new:
                    results["nlp"]["success"].append(txt_file.name)
                    nlp_json = output_nlp_path / (txt_file.stem + "_nlp.json")
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
                    results["nlp"]["skipped"].append(txt_file.name)
            finish_run(run_id, "COMPLETED", results["nlp"])

        _set_auto_pipeline_status(
            "running",
            f"Step 3/{AUTO_PIPELINE_STEPS}: Updating ranking from the active job description...",
            step="ranking",
            result=results,
        )

        output_ranking_path = OUTPUT_FOLDER / "ranking"
        output_ranking_path.mkdir(exist_ok=True)
        ranking_files = sorted(output_ranking_path.glob("ranking_scores*.json"), reverse=True)

        if ranking_files:
            latest_ranking = None
            try:
                with open(ranking_files[0], encoding="utf-8") as f:
                    latest_ranking = json.load(f)
            except Exception:
                pass

            if latest_ranking and "job_description" in latest_ranking:
                jd_data = latest_ranking["job_description"]
                candidates = load_candidates(output_nlp_path)

                if candidates:
                    ranked_candidates = latest_ranking.get("ranked_candidates", [])
                    ranked_filenames = {
                        c.get("_source_file") for c in ranked_candidates if c.get("_source_file")
                    }
                    new_candidates = [
                        c for c in candidates if c.get("_source_file") not in ranked_filenames
                    ]

                    if new_candidates:
                        scored_new = []
                        with ThreadPoolExecutor(max_workers=5) as executor:
                            futures = {executor.submit(score_candidate, c, jd_data): c for c in new_candidates}
                            for future in as_completed(futures):
                                res_score = future.result()
                                if res_score:
                                    scored_new.append(res_score)

                        all_scored = ranked_candidates + scored_new
                        ranked = sorted(all_scored, key=lambda x: x.get("total_score", 0), reverse=True)

                        save_leaderboard_txt(ranked, jd_data, output_ranking_path)
                        save_scores_json(ranked, jd_data, output_ranking_path)
                        shortlist = save_shortlist_report(ranked, jd_data, output_ranking_path)

                        rank_run_id = create_run(
                            "ranking",
                            {"job_title": jd_data.get("job_title"), "count": len(ranked), "source": "auto_pipeline"},
                        )
                        for r in ranked:
                            upsert_candidate(
                                run_id=rank_run_id,
                                name=r.get("candidate_name") or r.get("candidate", ""),
                                score=r.get("total_score", 0),
                            )
                        finish_run(rank_run_id, "COMPLETED")

                        results["ranking"] = {
                            "success": True,
                            "message": f"Evaluated {len(scored_new)} new candidate(s).",
                            "count": len(scored_new),
                            "shortlist_report": shortlist.get("files", {}),
                        }
                    else:
                        results["ranking"] = {
                            "success": True,
                            "message": "All candidate profiles are already ranked.",
                            "count": 0,
                        }
        else:
            results["ranking"] = {
                "success": False,
                "message": "No active job description. Add one in Ranking to enable automatic scoring.",
                "count": 0,
            }

        _set_auto_pipeline_status(
            "running",
            f"Step 4/{AUTO_PIPELINE_STEPS}: Scheduling ranked candidates and creating tokens...",
            step="scheduling",
            result=results,
        )

        output_sched_path = OUTPUT_FOLDER / "scheduling"
        output_sched_path.mkdir(exist_ok=True)
        top_candidates = load_top_candidates(output_ranking_path, 10)

        if top_candidates:
            latest_schedule = None
            schedule_files = sorted(output_sched_path.glob("schedule_*.json"), reverse=True)
            if schedule_files:
                try:
                    with open(schedule_files[0], encoding="utf-8") as f:
                        latest_schedule = json.load(f)
                except Exception:
                    pass

            job_title = latest_schedule.get("job_title", "Open Position") if latest_schedule else "Open Position"
            slots_raw = []
            if latest_schedule:
                all_slots = []
                for entry in latest_schedule.get("schedule", []):
                    all_slots.extend(entry.get("offered_slots", []))
                slots_raw = list(set(all_slots))

            if not slots_raw:
                now = datetime.now()
                slots_raw = [
                    f"{(now + timedelta(days=i)).strftime('%Y-%m-%d')} 10:00"
                    for i in range(1, 6)
                ]

            try:
                hr_slots = [datetime.strptime(s, "%Y-%m-%d %H:%M") for s in slots_raw]
            except Exception:
                hr_slots = []

            if hr_slots:
                scheduled_entries = latest_schedule.get("schedule", []) if latest_schedule else []
                scheduled_names = {entry["candidate_name"] for entry in scheduled_entries}
                new_candidates = [
                    c for c in top_candidates
                    if (c.get("candidate_name") or c.get("candidate", "Unknown")) not in scheduled_names
                ]

                if new_candidates:
                    new_scheduled = []
                    start_offset = len(scheduled_entries)
                    for i, candidate in enumerate(new_candidates):
                        name = candidate.get("candidate_name") or candidate.get("candidate") or "Unknown"
                        source = candidate.get("_source_file", "")
                        score = candidate.get("total_score", 0)
                        offered_slots = []
                        seen = set()
                        for j in range(len(hr_slots)):
                            slot_idx = (start_offset + i + j) % len(hr_slots)
                            slot = hr_slots[slot_idx]
                            slot_str = slot.strftime("%Y-%m-%d %H:%M")
                            if slot_str not in seen:
                                seen.add(slot_str)
                                offered_slots.append(slot)
                            if len(offered_slots) == SLOTS_TO_OFFER:
                                break

                        offered_slots.sort()
                        slot_strings = [s.strftime("%Y-%m-%d %H:%M") for s in offered_slots]
                        new_scheduled.append({
                            "rank": start_offset + i + 1,
                            "candidate_name": name,
                            "source_file": source,
                            "score": score,
                            "offered_slots": slot_strings,
                            "selected_slot": slot_strings[0] if slot_strings else None,
                            "status": "CONFIRMED" if offered_slots else "PENDING",
                        })

                    session_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    for entry in new_scheduled:
                        generate_ics(entry, output_sched_path, "Hiring Manager", job_title, session_stamp)

                    merged_schedule = scheduled_entries + new_scheduled
                    save_schedule_summary(merged_schedule, output_sched_path, job_title)

                    sched_run_id = create_run(
                        "scheduling",
                        {"job_title": job_title, "count": len(new_scheduled), "source": "auto_pipeline"},
                    )
                    db_save_schedule(sched_run_id, new_scheduled, job_title)
                    finish_run(sched_run_id, "COMPLETED")

                    for entry in new_scheduled:
                        if entry["status"] == "CONFIRMED":
                            token = f"T_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                            create_interview_token(
                                token=token,
                                candidate_name=entry["candidate_name"],
                                source_file=entry["source_file"],
                                job_title=job_title,
                                rank=entry["rank"],
                                score=entry["score"],
                            )

                    results["scheduling"] = {
                        "success": True,
                        "message": f"Coordinated {len(new_scheduled)} new candidate(s).",
                        "count": len(new_scheduled),
                    }
                else:
                    results["scheduling"] = {
                        "success": True,
                        "message": "All ranked candidates are already scheduled.",
                        "count": 0,
                    }
        else:
            results["scheduling"] = {
                "success": False,
                "message": "No ranked candidates available to schedule.",
                "count": 0,
            }

        _set_auto_pipeline_status(
            "running",
            f"Step 5/{AUTO_PIPELINE_STEPS}: Generating reports for completed interviews...",
            step="reports",
            result=results,
        )

        output_reports_path = OUTPUT_FOLDER / "reports"
        output_reports_path.mkdir(exist_ok=True)
        transcripts = load_interview_transcripts(OUTPUT_FOLDER / "interviews")
        if transcripts:
            existing_report_sources = set()
            for report_file in output_reports_path.glob("report_*.json"):
                try:
                    data = json.loads(report_file.read_text(encoding="utf-8"))
                    existing_report_sources.add(data.get("source_file"))
                except Exception:
                    pass

            new_transcripts = [
                t for t in transcripts
                if t.get("_source_file") not in existing_report_sources
            ]
            all_reports = []
            success_count = 0
            for transcript in new_transcripts:
                ai_report = generate_ai_report(transcript)
                if not ai_report:
                    continue
                combined_score = calculate_combined_score(transcript)
                save_report_txt(transcript, ai_report, combined_score, output_reports_path)
                save_report_json(transcript, ai_report, combined_score, output_reports_path)
                success_count += 1
                all_reports.append({
                    "candidate_name": transcript.get("candidate_name", "Unknown"),
                    "job_title": transcript.get("job_title", "N/A"),
                    "combined_score": combined_score,
                    "ranking_score": transcript.get("ranking_score", 0),
                    "hire_recommendation": ai_report.get("hire_recommendation", "N/A"),
                    "risk_level": ai_report.get("risk_level", "N/A"),
                    "key_strengths": ai_report.get("key_strengths", []),
                    "key_gaps": ai_report.get("key_gaps", []),
                })

            if all_reports:
                save_final_summary(all_reports, output_reports_path)

            results["reports"] = {
                "success": True,
                "message": f"Generated {success_count} new report(s).",
                "count": success_count,
            }
        else:
            results["reports"] = {
                "success": False,
                "message": "No completed interviews yet. Reports will run automatically after interviews exist.",
                "count": 0,
            }

        _set_auto_pipeline_status(
            "done",
            "Auto-pipeline completed.",
            finished=time.time(),
            step="complete",
            result=results,
        )
    except Exception as ex:
        _set_auto_pipeline_status(
            "error",
            f"Auto-pipeline failed: {ex}",
            finished=time.time(),
            error=str(ex),
            result=results,
        )


def register_dashboard_routes(app):
    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        pdf_count       = len([f for f in RESUMES_FOLDER.iterdir()
                               if f.is_file() and f.suffix.lower() in [".pdf",".png",".jpg",".jpeg"]])
        txt_count       = len(list((OUTPUT_FOLDER / "txt").glob("*.txt")))
        nlp_count       = len(list((OUTPUT_FOLDER / "nlp").glob("*_nlp.json")))
        ranking_files   = sorted((OUTPUT_FOLDER / "ranking").glob("ranking_scores*.json"), reverse=True)
        has_ranking     = len(ranking_files) > 0
        has_schedule    = len(list((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"))) > 0
        interview_count = len(list((OUTPUT_FOLDER / "interviews").glob("interview_*.json")))
        report_count    = len(list((OUTPUT_FOLDER / "reports").glob("report_*.json")))

        latest_ranking = None
        if ranking_files:
            try:
                with open(ranking_files[0], encoding="utf-8") as f:
                    latest_ranking = json.load(f)
            except Exception:
                pass

        return render_template("dashboard.html",
                               pdf_count=pdf_count, txt_count=txt_count,
                               nlp_count=nlp_count, has_ranking=has_ranking,
                               has_schedule=has_schedule, interview_count=interview_count,
                               report_count=report_count, ranking=latest_ranking)

    @app.route("/api/stats", methods=["GET"])
    def api_stats():
        pdf_count  = len([f for f in RESUMES_FOLDER.iterdir()
                          if f.is_file() and f.suffix.lower() in [".pdf", ".png", ".jpg", ".jpeg"]])
        txt_count  = len(list((OUTPUT_FOLDER / "txt").glob("*.txt")))
        nlp_count  = len(list((OUTPUT_FOLDER / "nlp").glob("*_nlp.json")))
        rank_files = sorted((OUTPUT_FOLDER / "ranking").glob("ranking_scores*.json"), reverse=True)
        ranked     = len(rank_files) > 0
        sched_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
        scheduled  = len(sched_files) > 0
        interview_count = len(list((OUTPUT_FOLDER / "interviews").glob("interview_*.json")))
        report_count    = len(list((OUTPUT_FOLDER / "reports").glob("report_*.json")))
        return jsonify({
            "pdf_count":       pdf_count,
            "txt_count":       txt_count,
            "nlp_count":       nlp_count,
            "pending_txt":     pdf_count - txt_count,
            "pending_nlp":     txt_count - nlp_count,
            "has_ranking":     ranked,
            "has_schedule":    scheduled,
            "interview_count": interview_count,
            "report_count":    report_count,
            "tasks":           pipeline_tasks,
        })

    @app.route("/api/task-status", methods=["GET"])
    def api_task_status():
        return jsonify(pipeline_tasks)

    @app.route("/api/reset-pipeline", methods=["POST"])
    def api_reset_pipeline():
        from app import database
        database.delete_all_tokens()

        folders_to_clear = ["nlp", "ranking", "scheduling", "interviews", "reports"]
        for folder in folders_to_clear:
            path = OUTPUT_FOLDER / folder
            if path.exists():
                for f in path.iterdir():
                    try:
                        if f.is_file():
                            f.unlink()
                        elif f.is_dir():
                            shutil.rmtree(f)
                    except Exception:
                        pass
        pipeline_tasks.clear()
        _save_tasks()
        return jsonify({"success": True, "message": "Database reset completed safely."})

    @app.route("/api/open-output-folder", methods=["POST"])
    def api_open_output_folder():
        import os
        try:
            os.startfile(str(OUTPUT_FOLDER))
        except Exception:
            pass
        return jsonify({"success": True})

    @app.route("/api/run-auto-pipeline", methods=["POST"])
    @login_required
    def api_run_auto_pipeline():
        with _pipeline_lock:
            current = pipeline_tasks.get("auto_pipeline", {})
            if current.get("status") == "running":
                return jsonify({
                    "success": True,
                    "started": False,
                    "message": current.get("message", "Auto-pipeline is already running."),
                    "task": current,
                }), 202

            pipeline_tasks["auto_pipeline"] = {
                "status": "running",
                "started": time.time(),
                "updated": time.time(),
                "step": "queued",
                "message": "Queued auto-pipeline run...",
            }
            _save_tasks()

        threading.Thread(target=_run_auto_pipeline_job, daemon=True).start()
        return jsonify({
            "success": True,
            "started": True,
            "message": "Auto-pipeline started.",
            "task": pipeline_tasks["auto_pipeline"],
        }), 202
