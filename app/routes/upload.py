from pathlib import Path

from flask import jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from app.core import OUTPUT_FOLDER, RESUMES_FOLDER
from app.utils import login_required
from src.pdf_to_txt import process_file as pdf_process_file

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


def _available_filename(folder: Path, filename: str) -> str:
    """Return a collision-free filename without trusting client path input."""
    candidate = Path(filename)
    stem, suffix = candidate.stem, candidate.suffix
    index = 1
    while (folder / candidate.name).exists():
        candidate = Path(f"{stem}_{index}{suffix}")
        index += 1
    return candidate.name


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
        rejected = []
        RESUMES_FOLDER.mkdir(parents=True, exist_ok=True)
        for file in files:
            if file.filename:
                safe_name = secure_filename(file.filename)
                suffix = Path(safe_name).suffix.lower()
                if not safe_name or suffix not in ALLOWED_UPLOAD_EXTENSIONS:
                    rejected.append({"filename": file.filename, "error": "Only PDF, PNG, JPG, and JPEG files are allowed."})
                    continue
                safe_name = _available_filename(RESUMES_FOLDER, safe_name)
                file.save(RESUMES_FOLDER / safe_name)
                saved.append(safe_name)
        return jsonify({"success": bool(saved), "saved": saved, "rejected": rejected, "count": len(saved)})

    @app.route("/api/view-resume/<filename>", methods=["GET"])
    @login_required
    def api_view_resume(filename):
        safe_name = secure_filename(filename)
        file_path = (RESUMES_FOLDER / safe_name).resolve()
        if not file_path.exists() or not file_path.is_relative_to(RESUMES_FOLDER.resolve()):
            return jsonify({"error": "Resume file not found"}), 404
        return send_from_directory(RESUMES_FOLDER, safe_name)

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
