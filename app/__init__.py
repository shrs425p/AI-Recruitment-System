from flask import Flask
from app.core import APP_RESOURCE_DIR

def create_app():
    templates_dir = str(APP_RESOURCE_DIR / "app" / "templates")
    static_dir = str(APP_RESOURCE_DIR / "app" / "static")
    
    app = Flask(__name__, template_folder=templates_dir, static_folder=static_dir)
    app.secret_key = "ARS_SECRET_KEY_SUPER_SECURE_123"
    
    return app
