from flask import Flask
import os

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Secret key for sessions
    app.secret_key = os.environ.get("SECRET_KEY", "tatwadarsha_secret_2025")

    # =====================================================
    # 📁 Configure Upload Folders
    # =====================================================
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    app.config["UPLOAD_FOLDER_FINANCE"] = os.path.join(
        BASE_DIR, "uploads", "finance", "attachment"
    )

    # Create folder if not exists
    os.makedirs(app.config["UPLOAD_FOLDER_FINANCE"], exist_ok=True)

    # =====================================================
    # Import Blueprints
    # =====================================================
    from app.routers.master import master_bp
    from app.routers.students import students_bp
    from app.routers.roll_number_allocation import roll_bp
    from app.routers.finance import finance_bp  # YOU MUST REGISTER THIS TOO

    # Register Blueprints
    app.register_blueprint(master_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(roll_bp)
    app.register_blueprint(finance_bp)  # IMPORTANT

    # Import main routes
    from app import main

    return app
