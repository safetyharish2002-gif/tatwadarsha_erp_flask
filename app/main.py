import logging
logging.getLogger('werkzeug').disabled = True

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, make_response
)
import os
from dotenv import load_dotenv
from datetime import timedelta, datetime
import mysql.connector
from mysql.connector import Error
import uuid

# ======================================
# Flask App Setup
# ======================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load Environment Variables (look one level up for .env)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)
app.secret_key = os.getenv("SECRET_KEY", "tatwadarsha_secret_2025")
app.permanent_session_lifetime = timedelta(hours=6)

UPLOAD_FOLDER_FINANCE = os.path.join(BASE_DIR, "uploads", "finance")
os.makedirs(UPLOAD_FOLDER_FINANCE, exist_ok=True)
app.config["UPLOAD_FOLDER_FINANCE"] = UPLOAD_FOLDER_FINANCE
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS_FINANCE = {"pdf", "jpg", "jpeg", "png"}

# ======================================
# Database helper functions
# ======================================
def get_db_connection():
    """Create MySQL connection (Hostinger). Uses .env when available."""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "srv366.hstgr.io"),
            user=os.getenv("MYSQL_USER", "u514260654_testerp"),
            password=os.getenv("MYSQL_PASSWORD", "Tions@98"),
            database=os.getenv("MYSQL_DB", "u514260654_test_erp"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            autocommit=False,
            auth_plugin=os.getenv("MYSQL_AUTH_PLUGIN", "mysql_native_password")
        )
        return conn
    except Error as e:
        # Use print instead of logging to make errors visible in basic consoles
        print(f"❌ MySQL Connection Error: {e}")
        return None


def row_to_dict(cursor, row):
    """Convert row into dict using cursor column names (works with non-dict cursor)."""
    return dict(zip(cursor.column_names, row))


def fetch_student_by_id(conn, table, student_id):
    """Return dict of a student row from given table or None."""
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM `{table}` WHERE id=%s", (student_id,))
        row = cur.fetchone()
        if not row:
            return None
        return row_to_dict(cur, row)
    finally:
        try:
            cur.close()
        except Exception:
            pass


# ======================================
# Students & Dropouts Columns
# ======================================
STUDENTS_COLUMNS = [
    "id", "admission_date", "batch", "branch", "course", "department",
    "enrollment_no", "last_exam_passed", "previous_school", "register_number",
    "registration_no", "roll_no", "session", "tenth_board", "tenth_percent",
    "twelfth_board", "twelfth_percent", "name", "gender", "dob",
    "blood_group", "email", "aadhaar", "phone", "address", "caste",
    "religion", "father_name", "father_mobile", "father_occupation",
    "mother_name", "mother_mobile", "guardian_name", "guardian_mobile",
    "guardian_email", "annual_income", "account_holder", "account_number",
    "bank_name", "ifsc", "aadhaar_url", "marksheet_url", "migration_url",
    "photo_url", "tc_url", "created_at"
]

DROPOUTS_COLUMNS = [
    "id", "dropout_date", "dropout_reason", "dropout_remarks", "student_id",
    "admission_date", "batch", "branch", "course", "department",
    "enrollment_no", "last_exam_passed", "previous_school", "register_number",
    "registration_no", "roll_no", "session", "tenth_board", "tenth_percent",
    "twelfth_board", "twelfth_percent", "name", "gender", "dob",
    "blood_group", "email", "aadhaar", "phone", "address", "caste",
    "religion", "father_name", "father_mobile", "father_occupation",
    "mother_name", "mother_mobile", "guardian_name", "guardian_mobile",
    "guardian_email", "annual_income", "account_holder", "account_number",
    "bank_name", "ifsc", "aadhaar_url", "marksheet_url", "migration_url",
    "photo_url", "tc_url", "created_at"
]


# ======================================
# Import Blueprints (deferred after app created)
# ======================================
try:
    from app.routers.master import master_bp
    from app.routers.students import students_bp
    from app.routers.roll_number_allocation import roll_bp
    from app.routers.dashboard import dashboard_bp
    from app.routers.fees import fees_bp   # ✅ ADD THIS LINE
    from app.routers.exam_papers import exam_papers_bp
    from app.routers.finance import finance_bp    
    from app.routers.chat import chat_bp
    from app.routers.auth import auth_bp

    # Register blueprints only if imports succeed
    app.register_blueprint(master_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(roll_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(fees_bp)
    app.register_blueprint(exam_papers_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(auth_bp, url_prefix="/api")

except Exception as e:
    print("⚠️ Warning: Blueprint import/register failed:", e)


# ======================================
# Admin Credentials
# ======================================
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin@")


# ======================================
# MASTERS helper
# ======================================
def get_masters_list():
    """Return dict { master_name: {item_id: name} }"""
    conn = get_db_connection()
    if not conn:
        return {}
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, master_name FROM masters")
        masters_rows = cur.fetchall()

        # Map master id -> name
        masters_map = {}
        for r in masters_rows:
            # r is (id, master_name)
            masters_map[int(r[0])] = r[1]

        cur.execute("SELECT id, master_id, name FROM master_items")
        rows = cur.fetchall()

        result = {}
        for item_id, master_id, name in rows:
            mname = masters_map.get(int(master_id))
            if not mname:
                continue
            if mname not in result:
                result[mname] = {}
            # ensure key is string to be JSON-friendly in templates
            result[mname][str(item_id)] = name

        return result

    except Exception as e:
        print("Error in get_masters_list:", e)
        return {}
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ======================================
# Global Context
# ======================================
@app.context_processor
def inject_globals():
    try:
        masters_menu = get_masters_list() or {}
    except Exception:
        masters_menu = {}

    username = session.get("username", "Admin") if session.get("logged_in") else None

    return {
        "masters_menu": masters_menu,
        "username": username
    }


# ======================================
# AUTH
# ======================================
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            flash("Welcome back, Admin!", "success")
            # dashboard blueprint endpoint assumed to be 'dashboard.dashboard'
            return redirect(url_for("dashboard.dashboard"))
        else:
            flash("Invalid credentials", "danger")
            return render_template("login.html"), 401

    if session.get("logged_in"):
        return redirect(url_for("dashboard.dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ======================================
# DROPOUT PAGE
# ======================================
@app.route("/dropout_students")
def dropout_students_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    if not conn:
        return "DB Error", 500

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM dropouts ORDER BY dropout_date DESC")
        rows = cur.fetchall()

        dropouts = [dict(zip(cur.column_names, row)) for row in rows]

        return render_template("students/dropout_student.html", dropouts=dropouts)

    except Exception as e:
        print("Dropout page error:", e)
        return "Error", 500
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ======================================
# API GET STUDENTS + DROPOUTS
# ======================================
@app.route("/api/get_students")
def api_get_students():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    course = request.args.get("course", "")
    year = request.args.get("year", "")
    semester = request.args.get("semester", "")
    section = request.args.get("section", "")
    search = (request.args.get("search") or "").lower()

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "DB error"}), 500

    cur = None
    try:
        cur = conn.cursor()

        where = []
        params = []

        if course:
            where.append("course=%s"); params.append(course)
        if year:
            where.append("batch=%s"); params.append(year)
        if semester:
            where.append("semester=%s"); params.append(semester)
        if section:
            where.append("section=%s"); params.append(section)

        condition = "WHERE " + " AND ".join(where) if where else ""

        cur.execute(f"SELECT * FROM students {condition}", tuple(params))
        student_rows = cur.fetchall()

        students = []
        for row in student_rows:
            rd = dict(zip(cur.column_names, row))
            st = {
                "id": rd.get("id"),
                "personal": {
                    "name": rd.get("name"),
                    "phone": rd.get("phone"),
                },
                "academic": {
                    "course": rd.get("course"),
                    "batch": rd.get("batch"),
                    "semester": rd.get("semester"),
                    "register_number": rd.get("register_number"),
                    "roll_no": rd.get("roll_no"),
                    "session": rd.get("session")
                }
            }

            hay = f"{rd.get('name','')} {rd.get('register_number','')} {rd.get('phone','')}".lower()
            if search and search not in hay:
                continue

            students.append(st)

        # Dropouts
        cur.execute("SELECT * FROM dropouts")
        drows = cur.fetchall()
        dropouts = [dict(zip(cur.column_names, r)) for r in drows]

        return jsonify({"success": True, "students": students, "dropouts": dropouts})

    except Exception as e:
        print("API get_students error:", e)
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ======================================
# MARK DROP
# ======================================
@app.route("/mark_dropout", methods=["POST"])
def mark_dropout_api():
    if not session.get("logged_in"):
        return jsonify({"success": False}), 403

    data = request.get_json()
    student_id = data.get("student_id")
    dropout_date = data.get("dropout_date")
    reason = data.get("reason", "")
    remarks = data.get("remarks", "")

    if not student_id:
        return jsonify({"success": False, "message": "Missing ID"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "msg": "DB error"}), 500

    cur = None
    try:
        cur = conn.cursor()
        # fetch student
        cur.execute("SELECT * FROM students WHERE id=%s", (student_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "msg": "Not found"}), 404

        student = dict(zip(cur.column_names, row))

        # insert into dropouts
        cols, vals = [], []

        for col in DROPOUTS_COLUMNS:
            if col == "id":
                cols.append("id"); vals.append(student_id)
            elif col == "dropout_date":
                cols.append("dropout_date"); vals.append(dropout_date)
            elif col == "dropout_reason":
                cols.append("dropout_reason"); vals.append(reason)
            elif col == "dropout_remarks":
                cols.append("dropout_remarks"); vals.append(remarks)
            elif col == "student_id":
                cols.append("student_id"); vals.append(student_id)
            else:
                cols.append(col); vals.append(student.get(col))

        placeholders = ", ".join(["%s"] * len(vals))
        col_sql = ", ".join(cols)

        cur.execute(f"INSERT INTO dropouts ({col_sql}) VALUES ({placeholders})", tuple(vals))

        # delete from students
        cur.execute("DELETE FROM students WHERE id=%s", (student_id,))
        conn.commit()

        return jsonify({"success": True})

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("Mark dropout error:", e)
        return jsonify({"success": False, "msg": str(e)}), 500

    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ======================================
# MARK ADMIT
# ======================================
@app.route("/mark_admit", methods=["POST"])
def mark_admit_api():
    if not session.get("logged_in"):
        return jsonify({"success": False}), 403

    data = request.get_json()
    student_id = data.get("student_id")

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False}), 500

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM dropouts WHERE id=%s", (student_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Not found"}), 404

        drop_row = dict(zip(cur.column_names, row))

        # prepare student data
        student_data = {}
        for col in STUDENTS_COLUMNS:
            if col == "id":
                student_data[col] = student_id
            else:
                student_data[col] = drop_row.get(col)

        cols = ", ".join(student_data.keys())
        placeholders = ", ".join(["%s"] * len(student_data))
        cur.execute(f"INSERT INTO students ({cols}) VALUES ({placeholders})", tuple(student_data.values()))

        cur.execute("DELETE FROM dropouts WHERE id=%s", (student_id,))
        conn.commit()
        return jsonify({"success": True})

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("Mark admit error:", e)
        return jsonify({"success": False, "msg": str(e)}), 500

    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ======================================
# Debug: Show all routes
# ======================================
with app.app_context():
    try:
        print("\nRegistered Routes:")
        for rule in app.url_map.iter_rules():
            print(rule)
        print("====================================\n")
    except Exception as e:
        print("Could not print routes:", e)
        
# ======================================
# Serve Exam Paper Files
# ======================================
from flask import send_from_directory

EXAM_PAPER_PATH = os.path.join(BASE_DIR, "static", "exam_papers")

@app.route("/exam-files/<path:filename>")
def exam_files(filename):
    try:
        return send_from_directory(EXAM_PAPER_PATH, filename, as_attachment=False)
    except Exception as e:
        print("File serve error:", e)
        return "File Not Found", 404

# ======================================
# RUN APPLICATION
# ======================================
if __name__ == "__main__":
    print("🚀 Tatwadarsha ERP NEXT GEN — Flask Server Running")
    # debug=True is okay while developing, but avoid in production
    app.run(host="0.0.0.0", port=5000, debug=True)
