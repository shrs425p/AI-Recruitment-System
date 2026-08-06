from flask import jsonify

from app.database import get_connection
from src.common import APP_DATA_DIR


def register_health_routes(app):
    @app.route("/api/health", methods=["GET"])
    def api_health():
        db_ok = False
        try:
            conn = get_connection()
            conn.execute("SELECT 1")
            conn.close()
            db_ok = True
        except Exception:
            db_ok = False

        return jsonify(
            {
                "success": db_ok,
                "status": "ok" if db_ok else "degraded",
                "data_dir": str(APP_DATA_DIR),
                "database": "ok" if db_ok else "error",
            }
        ), (200 if db_ok else 503)
