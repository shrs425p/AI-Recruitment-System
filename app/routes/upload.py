from flask import request, jsonify, render_template
from app.core import RESUMES_FOLDER, OUTPUT_FOLDER
from app.utils import login_required
from pdf_to_txt import process_file as pdf_process_file

def register_upload_routes(app):
    @app.route("/upload")
    @login_required
    def upload():
        txt_count = len(list((OUTPUT_FOLDER / "txt").glob("*.txt")))
        pdf_count = len(list(RESUMES_FOLDER.glob("*.pdf"))) +                     len(list(RESUMES_FOLDER.glob("*.png"))) +                     len(list(RESUMES_FOLDER.glob("*.jpg"))) +                     len(list(RESUMES_FOLDER.glob("*.jpeg")))
        return render_template("upload.html", pdf_count=pdf_count, txt_count=txt_count)

    @app.route("/api/upload", methods=["POST"])
    def api_upload():
        files = request.files.getlist("resumes")
        saved = []
        for file in files:
            if file.filename:
                dest = RESUMES_FOLDER / file.filename
                file.save(dest)
                saved.append(file.filename)
        return jsonify({"success": True, "saved": saved, "count": len(saved)})

    @app.route("/api/process-pdfs", methods=["POST"])
    def api_process_pdfs():
        input_path  = RESUMES_FOLDER
        output_path = OUTPUT_FOLDER / "txt"
        files = [f for f in input_path.iterdir()
                 if f.is_file() and f.suffix.lower() in [".pdf", ".png", ".jpg", ".jpeg"]]
        results = {"success": [], "skipped": [], "failed": []}
        for f in files:
            try:
                is_new = pdf_process_file(f, output_path)
                if is_new:
                    results["success"].append(f.name)
                else:
                    results["skipped"].append(f.name)
            except Exception as e:
                results["failed"].append({"file": f.name, "error": str(e)})
        return jsonify(results)
