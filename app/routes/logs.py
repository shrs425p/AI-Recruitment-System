import queue

from flask import Response, render_template

from app.core import get_log_history, log_queue
from app.utils import login_required


def register_logs_routes(app):
    @app.route("/logs")
    @login_required
    def logs():
        return render_template("logs.html")

    @app.route("/stream-logs")
    def stream_logs():
        def generate():
            history = get_log_history()
            if history:
                for line in history:
                    yield f"data: {line}\n\n"
            else:
                yield "data: [SYSTEM] Connected to live backend log stream.\n\n"

            while True:
                try:
                    line = log_queue.get(timeout=2.0)
                    yield f"data: {line}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"

        return Response(generate(), mimetype="text/event-stream")
