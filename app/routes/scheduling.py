import json
import time
from datetime import datetime

from flask import jsonify, render_template, request

from app.core import OUTPUT_FOLDER, _save_tasks, pipeline_tasks
from app.database import create_run, finish_run
from app.database import save_schedule as db_save_schedule
from app.utils import login_required
from src.google_calendar import check_calendar_auth, create_event_from_dict, get_free_slots, trigger_auth_flow
from src.scheduling import (
    SLOTS_TO_OFFER,
    assign_slots_to_candidates,
    generate_ics,
    load_top_candidates,
    save_schedule_summary,
)


def _parse_schedule_slots(raw_slots):
    now = datetime.now()
    parsed = []
    seen = set()
    rejected = []

    for raw in raw_slots:
        value = str(raw).strip()
        if not value:
            continue
        try:
            slot = datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError:
            rejected.append({"slot": value, "reason": "Use format YYYY-MM-DD HH:MM"})
            continue
        if slot <= now:
            rejected.append({"slot": value, "reason": "Slot is in the past"})
            continue
        key = slot.strftime("%Y-%m-%d %H:%M")
        if key in seen:
            rejected.append({"slot": value, "reason": "Duplicate slot"})
            continue
        seen.add(key)
        parsed.append(slot)

    parsed.sort()
    return parsed, rejected


def register_scheduling_routes(app):
    @app.route("/scheduling")
    @login_required
    def scheduling():
        ranking_files  = sorted((OUTPUT_FOLDER / "ranking").glob("ranking_scores*.json"), reverse=True)
        latest_ranking = None
        if ranking_files:
            try:
                with open(ranking_files[0], encoding="utf-8") as f:
                    latest_ranking = json.load(f)
            except Exception:
                pass

        has_ranking    = len(ranking_files) > 0
        schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
        latest_schedule = None
        if schedule_files:
            try:
                with open(schedule_files[0], encoding="utf-8") as f:
                    latest_schedule = json.load(f)
            except Exception:
                pass

        try:
            cal_status = check_calendar_auth()
        except Exception:
            cal_status = {"authenticated": False, "error": "Google Calendar module unavailable"}

        return render_template("scheduling.html",
                               ranking=latest_ranking,
                               has_ranking=has_ranking,
                               schedule=latest_schedule,
                               cal_status=cal_status)

    @app.route("/api/schedule", methods=["POST"])
    def api_schedule():
        data      = request.json
        job_title = data.get("job_title", "Open Position")
        hr_name   = data.get("hr_name", "Hiring Manager")
        hr_email  = data.get("hr_email", "")
        slots_raw = data.get("slots", [])
        try:
            top_n = max(1, min(int(data.get("top_n", 10)), 50))
        except (TypeError, ValueError):
            top_n = 10

        pipeline_tasks["scheduling"] = {"status": "running", "started": time.time()}
        _save_tasks()

        ranking_path = OUTPUT_FOLDER / "ranking"
        output_path  = OUTPUT_FOLDER / "scheduling"
        output_path.mkdir(exist_ok=True)

        top_candidates = load_top_candidates(ranking_path, top_n)
        if not top_candidates:
            return jsonify({"error": "No ranked candidates found"}), 404

        hr_slots, rejected_slots = _parse_schedule_slots(slots_raw)
        if len(hr_slots) < SLOTS_TO_OFFER:
            return jsonify({
                "error": f"Enter at least {SLOTS_TO_OFFER} valid future slots.",
                "rejected_slots": rejected_slots,
            }), 400

        session_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scheduled     = assign_slots_to_candidates(top_candidates, hr_slots, SLOTS_TO_OFFER)

        for entry in scheduled:
            if entry["offered_slots"]:
                entry["selected_slot"] = entry["offered_slots"][0]
                entry["status"]        = "CONFIRMED"
            else:
                entry["status"] = "PENDING"

        for entry in scheduled:
            generate_ics(entry, output_path, hr_name, job_title, session_stamp, hr_email=hr_email)

        metadata = {
            "top_n": top_n,
            "slot_count": len(hr_slots),
            "rejected_slots": rejected_slots,
            "hr_name": hr_name,
            "hr_email": hr_email,
        }
        save_schedule_summary(scheduled, output_path, job_title, metadata=metadata)

        sched_run_id = create_run("scheduling", {"job_title": job_title, "count": len(scheduled)})
        db_save_schedule(sched_run_id, scheduled, job_title)
        finish_run(sched_run_id, "COMPLETED")

        pipeline_tasks["scheduling"] = {
            "status": "done",
            "result": {
                "total": len(scheduled),
                "confirmed": sum(1 for entry in scheduled if entry.get("status") == "CONFIRMED"),
                "pending": sum(1 for entry in scheduled if entry.get("status") == "PENDING"),
                "rejected_slots": rejected_slots,
            },
        }
        _save_tasks()

        return jsonify({"success": True, "scheduled": scheduled, "rejected_slots": rejected_slots})

    @app.route("/api/update-slot", methods=["POST"])
    def api_update_slot():
        data           = request.json
        candidate_name = data.get("candidate_name")
        selected_slot  = data.get("selected_slot")

        schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
        if not schedule_files:
            return jsonify({"error": "No schedule found"}), 404

        try:
            with open(schedule_files[0], encoding="utf-8") as f:
                schedule_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return jsonify({"error": "Schedule file is corrupted"}), 500

        for entry in schedule_data["schedule"]:
            if entry["candidate_name"] == candidate_name:
                entry["selected_slot"] = selected_slot
                entry["status"]        = "CONFIRMED"
                break

        with open(schedule_files[0], "w", encoding="utf-8") as f:
            json.dump(schedule_data, f, indent=4)

        return jsonify({"success": True})

    @app.route("/api/calendar/status", methods=["GET"])
    def api_calendar_status():
        return jsonify(check_calendar_auth())

    @app.route("/api/calendar/auth", methods=["POST"])
    def api_calendar_auth():
        result = trigger_auth_flow()
        return jsonify(result)

    @app.route("/api/calendar/free-slots", methods=["GET"])
    def api_calendar_free_slots():
        days = request.args.get("days", 14)
        try:
            days = int(days)
        except Exception:
            days = 14
        result  = get_free_slots(days_ahead=days)
        return jsonify(result)

    @app.route("/api/calendar/create-events", methods=["POST"])
    def api_calendar_create_events():
        schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
        if not schedule_files:
            return jsonify({"error": "No schedule found"}), 404

        try:
            with open(schedule_files[0], encoding="utf-8") as f:
                sdata = json.load(f)
        except Exception:
            return jsonify({"error": "Corrupted schedule summary"}), 500

        created = []
        errors  = []
        for entry in sdata.get("schedule", []):
            if entry.get("status") == "CONFIRMED" and entry.get("selected_slot"):
                try:
                    create_event_from_dict(entry, sdata.get("job_title", "Interview"))
                    created.append(entry["candidate_name"])
                except Exception as ex:
                    errors.append(f"{entry['candidate_name']}: {ex}")

        return jsonify({"success": True, "created": created, "errors": errors})
