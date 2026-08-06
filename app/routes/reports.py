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
        for rf in reports_files:
            try:
                with open(rf, encoding="utf-8") as f:
                    rdata = json.load(f)
                    rdata["filename"] = rf.name  # Inject filename for reference
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
        import unicodedata
        from io import BytesIO

        from fpdf import FPDF

        def _safe(s):
            if s is None:
                return ""
            s = str(s)
            s = unicodedata.normalize("NFKD", s)
            return s.encode("latin-1", errors="replace").decode("latin-1")

        safe = re.sub(r'[^a-zA-Z0-9_.\-]', '', filename)
        json_path = OUTPUT_FOLDER / "reports" / safe
        if not json_path.exists() or not json_path.suffix == '.json':
            return jsonify({"error": "Report not found"}), 404

        try:
            with open(json_path, encoding="utf-8") as f:
                report = json.load(f)
        except Exception:
            return jsonify({"error": "Report file is corrupted"}), 500

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Post-Interview Evaluation Report", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, _safe(f"Candidate    : {report.get('candidate_name','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, _safe(f"Job Title    : {report.get('job_title','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, _safe(f"Domain       : {report.get('domain','N/A')}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        buf = BytesIO()
        pdf.output(dest="S")
        buf.write(pdf.output())
        buf.seek(0)

        candidate = re.sub(r'[^a-zA-Z0-9_]', '_', report.get("candidate_name", "report"))
        return Response(
            buf.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{candidate}.pdf"}
        )

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

        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "Post-Interview Evaluation Report", new_x="LMARGIN", new_y="NEXT", align="C")

            candidate = re.sub(r'[^a-zA-Z0-9_]', '_', report.get("candidate_name", "report"))
            pdf_name = f"report_{candidate}.pdf"
            pdf_path = OUTPUT_FOLDER / "reports" / pdf_name
            pdf.output(str(pdf_path))

            # Auto-open with system PDF viewer
            _os.startfile(str(pdf_path))
        except Exception as e:
            return jsonify({"error": f"PDF save failed: {e}"}), 500

        return jsonify({"success": True, "path": str(pdf_path)})
