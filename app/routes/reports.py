import logging

logger = logging.getLogger(__name__)
import json
import re
import time

from flask import Response, jsonify, render_template

from app.core import OUTPUT_FOLDER, _save_tasks, pipeline_tasks
from app.utils import login_required
from src.report_generator import (
    calculate_combined_score,
    generate_ai_report,
    load_interview_transcripts,
    save_final_summary,
    save_report_json,
    save_report_txt,
)


def register_reports_routes(app):
    @app.route("/reports")
    @login_required
    def reports():
        reports_files = sorted((OUTPUT_FOLDER / "reports").glob("report_*.json"), reverse=True)
        reports_data  = []

        # Load interview transcripts to enrich reports with detailed proctoring logs if needed
        interviews_map = {}
        for int_f in sorted((OUTPUT_FOLDER / "interviews").glob("interview_*.json")):
            try:
                with open(int_f, encoding="utf-8") as f:
                    idata = json.load(f)
                    c_name = idata.get("candidate_name")
                    if c_name:
                        interviews_map[c_name] = idata
            except Exception:
                pass

        for rf in reports_files:
            try:
                with open(rf, encoding="utf-8") as f:
                    rdata = json.load(f)
                    rdata["filename"] = rf.name  # Inject filename for reference
                    rdata["_filename"] = rf.name

                    c_name = rdata.get("candidate_name")
                    if c_name in interviews_map:
                        idata = interviews_map[c_name]
                        if not rdata.get("responses") and idata.get("responses"):
                            rdata["responses"] = idata["responses"]
                        proctor_info = rdata.setdefault("proctoring", {})
                        if not proctor_info.get("browser_log"):
                            proctor_info["browser_log"] = idata.get("browser_log", [])
                        if not proctor_info.get("webcam_log"):
                            proctor_info["webcam_log"] = idata.get("webcam_log", [])

                    reports_data.append(rdata)
            except Exception as e:
                logger.warning('Caught exception: %s', e, exc_info=True)

        summary_files = sorted((OUTPUT_FOLDER / "reports").glob("final_summary*.json"), reverse=True)
        summary       = None
        if summary_files:
            try:
                with open(summary_files[0], encoding="utf-8") as f:
                    summary = json.load(f)
            except Exception as e:
                logger.warning('Caught exception: %s', e, exc_info=True)
        return render_template("reports.html", reports=reports_data, summary=summary)

    @app.route("/api/generate-reports", methods=["POST"])
    @login_required
    def api_generate_reports():
        interviews_path = OUTPUT_FOLDER / "interviews"
        output_path     = OUTPUT_FOLDER / "reports"
        output_path.mkdir(exist_ok=True)

        transcripts = load_interview_transcripts(interviews_path)
        if not transcripts:
            return jsonify({"error": "No interview transcripts found"}), 404

        pipeline_tasks["reports"] = {"status": "running", "started": time.time()}
        _save_tasks()

        all_reports   = []
        success_count = 0

        for transcript in transcripts:
            combined_score = calculate_combined_score(transcript)
            ai_report      = generate_ai_report(transcript)
            if not ai_report:
                continue
            save_report_txt(transcript, ai_report, combined_score, output_path)
            save_report_json(transcript, ai_report, combined_score, output_path)
            all_reports.append({
                "candidate_name":      transcript.get("candidate_name", "Unknown"),
                "source_file":         transcript.get("source_file", ""),
                "combined_score":      combined_score,
                "ranking_score":       transcript.get("ranking_score", 0),
                "interview_pct":       transcript.get("percentage", 0),
                "proctoring_status":   transcript.get("proctoring_status", "UNKNOWN"),
                "hire_recommendation": ai_report.get("hire_recommendation", "N/A"),
                "risk_level":          ai_report.get("risk_level", "N/A"),
                "key_strengths":       ai_report.get("key_strengths", []),
                "key_gaps":            ai_report.get("key_gaps", [])
            })
            success_count += 1

        if all_reports:
            save_final_summary(all_reports, output_path)

        pipeline_tasks["reports"] = {"status": "done", "result": {"count": success_count}}
        _save_tasks()

        return jsonify({"success": True, "count": success_count, "reports": all_reports})

    @app.route("/api/report-pdf/<filename>")
    @login_required
    def api_report_pdf(filename):
        safe = re.sub(r'[^a-zA-Z0-9_.\-]', '', filename)
        json_path = OUTPUT_FOLDER / "reports" / safe
        if not json_path.exists() or not json_path.suffix == '.json':
            return jsonify({"error": "Report not found"}), 404

        try:
            with open(json_path, encoding="utf-8") as f:
                report = json.load(f)
        except Exception:
            return jsonify({"error": "Report file is corrupted"}), 500

        # Backfill responses if missing from report JSON
        if not report.get("responses"):
            interviews_path = OUTPUT_FOLDER / "interviews"
            cname = report.get("candidate_name")
            for jf in interviews_path.glob("interview_*.json"):
                try:
                    with open(jf, encoding="utf-8") as tf:
                        tdata = json.load(tf)
                        if tdata.get("candidate_name") == cname:
                            report["responses"] = tdata.get("responses", [])
                            break
                except Exception:
                    pass

        try:
            from src.report_generator import generate_evaluation_pdf
            pdf = generate_evaluation_pdf(report)
            candidate = re.sub(r'[^a-zA-Z0-9_]', '_', report.get("candidate_name", "report"))
            return Response(
                bytes(pdf.output()),
                mimetype="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=report_{candidate}.pdf"}
            )
        except Exception as e:
            return jsonify({"error": f"PDF generation failed: {e}"}), 500

    @app.route("/api/save-report-pdf/<filename>")
    @login_required
    def api_save_report_pdf(filename):
        import os as _os
        safe = re.sub(r'[^a-zA-Z0-9_.\-]', '', filename)
        json_path = OUTPUT_FOLDER / "reports" / safe
        if not json_path.exists() or json_path.suffix != '.json':
            return jsonify({"error": "Report not found"}), 404

        try:
            with open(json_path, encoding="utf-8") as f:
                report = json.load(f)
        except Exception:
            return jsonify({"error": "Report file corrupted"}), 500

        # Backfill responses if missing from report JSON
        if not report.get("responses"):
            interviews_path = OUTPUT_FOLDER / "interviews"
            cname = report.get("candidate_name")
            for jf in interviews_path.glob("interview_*.json"):
                try:
                    with open(jf, encoding="utf-8") as tf:
                        tdata = json.load(tf)
                        if tdata.get("candidate_name") == cname:
                            report["responses"] = tdata.get("responses", [])
                            break
                except Exception:
                    pass

        try:
            from src.report_generator import generate_evaluation_pdf
            candidate = re.sub(r'[^a-zA-Z0-9_]', '_', report.get("candidate_name", "report"))
            pdf_name = f"report_{candidate}.pdf"
            pdf_path = OUTPUT_FOLDER / "reports" / pdf_name
            generate_evaluation_pdf(report, output_file=pdf_path)

            # Auto-open with system PDF viewer if available
            try:
                _os.startfile(str(pdf_path))
            except Exception:
                pass
        except Exception as e:
            return jsonify({"error": f"PDF save failed: {e}"}), 500

        return jsonify({"success": True, "path": str(pdf_path)})
