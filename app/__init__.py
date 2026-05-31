import os
import secrets

from flask import Flask

import config
from app.app_paths import APP_RESOURCE_DIR
from app.utils import protect_hr_routes


def create_app():
    templates_dir = str(APP_RESOURCE_DIR / "app" / "templates")
    static_dir = str(APP_RESOURCE_DIR / "app" / "static")

    app = Flask(__name__, template_folder=templates_dir, static_folder=static_dir)
    app.secret_key = (
        os.environ.get("FLASK_SECRET_KEY")
        or getattr(config, "FLASK_SECRET_KEY", "")
        or secrets.token_hex(32)
    )
    protect_hr_routes(app)

    return app
