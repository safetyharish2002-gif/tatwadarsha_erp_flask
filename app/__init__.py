from flask import Flask
import os

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Secret key for sessions
    app.secret_key = os.environ.get("SECRET_KEY", "tatwadarsha_secret_2025")

    # =====================================================
    # ✅ Import Blueprints Safely
    # =====================================================
    from app.routers.master import master_bp
    from app.routers.students import students_bp
    from app.routers.roll_number_allocation import roll_bp

    # =====================================================
    # ✅ Register Blueprints
    # =====================================================
    app.register_blueprint(master_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(roll_bp)

    # =====================================================
    # ✅ Import Main Routes (Dashboard, Login, etc.)
    # =====================================================
    from app import main

    return app
