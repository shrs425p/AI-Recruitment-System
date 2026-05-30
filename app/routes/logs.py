from flask import render_template, Response
from app.core import log_queue
from app.utils import login_required

def register_logs_routes(app):
    @app.route("/logs")
    @login_required
    def logs():
        return render_template("logs.html")

    @app.route("/stream-logs")
    def stream_logs():
        def generate():
            while True:
                line = log_queue.get()
                yield f"data: {line}\n\n"
        return Response(generate(), mimetype="text/event-stream")
