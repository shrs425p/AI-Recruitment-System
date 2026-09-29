import logging

logger = logging.getLogger(__name__)
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
            except Exception as e:
                logger.warning('Caught exception: %s', e, exc_info=True)

        has_ranking    = len(ranking_files) > 0
        schedule_files = sorted((OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True)
        latest_schedule = None
        if schedule_files:
            try:
                with open(schedule_files[0], encoding="utf-8") as f:
                    latest_schedule = json.load(f)
            except Exception as e:
                logger.warning('Caught exception: %s', e, exc_info=True)

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

    @app.route("/api/send-emails", methods=["POST"])
    @login_required
    def api_send_emails():
        import config as cfg
        from app.database import (
            get_confirmed_not_emailed, log_email, mark_email_sent, get_latest_schedule
        )
        from src.email_sender import send_interview_email

        smtp_host     = getattr(cfg, "SMTP_HOST", "").strip()
        smtp_port     = int(getattr(cfg, "SMTP_PORT", 587) or 587)
        smtp_email    = getattr(cfg, "SMTP_EMAIL", "").strip()
        smtp_password = getattr(cfg, "SMTP_PASSWORD", "").strip()
        hr_name       = getattr(cfg, "HR_DISPLAY_NAME", "").strip()
        company       = getattr(cfg, "HR_COMPANY", "").strip()

        if not smtp_host or not smtp_email or not smtp_password:
            return jsonify({
                "success": False,
                "error": "SMTP not configured. Go to Settings → Email to set up your SMTP credentials."
            }), 400

        # Get all scheduled candidates (confirmed or not) from latest schedule JSON
        schedule_files = sorted(
            (OUTPUT_FOLDER / "scheduling").glob("schedule_*.json"), reverse=True
        )
        if not schedule_files:
            return jsonify({"success": False, "error": "No schedule found. Run scheduling first."}), 400

        try:
            with open(schedule_files[0], encoding="utf-8") as f:
                sdata = json.load(f)
        except Exception:
            return jsonify({"error": "Corrupted schedule file"}), 500

        job_title = sdata.get("job_title", "Open Position")
        entries   = sdata.get("schedule", [])

        sent   = []
        failed = []
        errors = []

        for entry in entries:
            name  = entry.get("candidate_name", "Candidate")
            email = entry.get("email", "")
            slot  = entry.get("selected_slot", "") or (entry.get("offered_slots") or [""])[0]

            # Fallback: look up email from the NLP JSON if not in schedule
            if not email:
                source_file = entry.get("source_file", "")
                nlp_path = OUTPUT_FOLDER / "nlp"
                # Try exact source_file name first, then by candidate name
                candidates_to_try = []
                if source_file:
                    candidates_to_try.append(nlp_path / f"{source_file}.json")
                    candidates_to_try.append(nlp_path / f"{source_file}_nlp.json")
                # Also try matching by candidate name
                if nlp_path.exists():
                    for nlp_file in nlp_path.glob("*_nlp.json"):
                        candidates_to_try.append(nlp_file)
                for nlp_file in candidates_to_try:
                    try:
                        if not nlp_file.exists():
                            continue
                        import json as _json
                        with open(nlp_file, encoding="utf-8") as nf:
                            ndata = _json.load(nf)
                        found_name = ndata.get("personal_info", {}).get("name", "")
                        found_email = ndata.get("personal_info", {}).get("email", "")
                        if found_email and (not found_name or found_name.lower() == name.lower() or name.lower() in found_name.lower()):
                            email = found_email
                            break
                    except Exception:
                        continue

            if not email:
                failed.append(name)
                errors.append(f"{name}: No email address found in resume.")
                continue

            ok, err = send_interview_email(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_email=smtp_email,
                smtp_password=smtp_password,
                recipient_email=email,
                candidate_name=name,
                job_title=job_title,
                interview_slot=slot,
                hr_name=hr_name,
                company=company,
            )

            if ok:
                sent.append(name)
                logger.info(f"[EMAIL] Sent to {name} <{email}>")
            else:
                failed.append(name)
                errors.append(f"{name}: {err}")
                logger.error(f"[EMAIL] Failed for {name}: {err}")

        return jsonify({
            "success": len(sent) > 0,
            "sent": len(sent),
            "failed": len(failed),
            "sent_names": sent,
            "errors": errors,
        })
