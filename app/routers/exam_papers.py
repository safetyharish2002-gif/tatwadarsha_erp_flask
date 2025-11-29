SCAN_API_TOKEN = "Tatwadarsha@2025"

# FILE: app/routers/exam_papers.py

from flask import (
    Blueprint, render_template, request, jsonify,
    flash, redirect, url_for, send_from_directory
)
from werkzeug.utils import secure_filename
from datetime import datetime
import os

from app.main import get_db_connection  # uses your existing DB helper

# -------------------------------------------------------------------
# Paths & config
# -------------------------------------------------------------------
# this file is app/routers/exam_papers.py
ROUTERS_DIR = os.path.dirname(os.path.abspath(__file__))      # .../app/routers
APP_DIR     = os.path.dirname(ROUTERS_DIR)                    # .../app
PROJECT_DIR = os.path.dirname(APP_DIR)                        # .../Tatwadarsha_ERP_WEB

# Real folder where PDFs/JPGs are stored:
UPLOAD_FOLDER = os.path.join(PROJECT_DIR, "static", "exam_papers")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "doc", "docx"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


exam_papers_bp = Blueprint("exam_papers", __name__, url_prefix="/exam-papers")


# -------------------------------------------------------------------
# UI PAGES
# -------------------------------------------------------------------
@exam_papers_bp.route("/add")
def add_exam_paper():
    """Main page: search student + upload + list for that student."""
    return render_template("exam_papers/add.html")


@exam_papers_bp.route("/list")
def list_exam_papers_page():
    """(Optional) global list page – keep for future, or simple placeholder."""
    return render_template("exam_papers/list.html")


# -------------------------------------------------------------------
# Serve files (VIEW)
# -------------------------------------------------------------------
@exam_papers_bp.route("/file/<path:filename>")
def view_exam_paper(filename):
    """
    Send the stored file from PROJECT_ROOT/static/exam_papers.
    `filename` is just the stored file name (column file_url).
    """
    full_path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.isfile(full_path):
        # Helpful debug in console
        print("⚠️ Exam paper not found on disk:", full_path)
        return "File Not Found", 404

    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=False)


# -------------------------------------------------------------------
# API: Search Student
# -------------------------------------------------------------------
@exam_papers_bp.route("/api/search_student")
def api_search_student():
    q = (request.args.get("q") or "").lower().strip()
    if not q:
        return jsonify({"success": False, "students": [], "msg": "Empty query"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "students": [], "msg": "DB error"}), 500

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, name, register_number, roll_no, batch, course
            FROM students
            WHERE LOWER(name) LIKE %s
               OR LOWER(register_number) LIKE %s
               OR LOWER(roll_no) LIKE %s
            LIMIT 20
            """,
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        )
        rows = cur.fetchall()
        students = [dict(zip(cur.column_names, row)) for row in rows]
        return jsonify({"success": True, "students": students})
    finally:
        cur.close()
        conn.close()


# -------------------------------------------------------------------
# API: Get papers for a student (LIST)
# -------------------------------------------------------------------
@exam_papers_bp.route("/api/get_all")
def api_get_all_papers():
    q = (request.args.get("q") or "").lower()
    from_date = request.args.get("from")  # YYYY-MM-DD
    to_date = request.args.get("to")      # YYYY-MM-DD

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "papers": [], "msg": "DB error"}), 500
    cur = conn.cursor()

    try:
        query = """
            SELECT ep.id, ep.subject, ep.exam_name, ep.year,
                   ep.uploaded_at, ep.file_url,
                   s.name, s.roll_no
            FROM exam_papers ep
            LEFT JOIN students s ON ep.student_id = s.id
            WHERE 1=1
        """

        params = []

        if q:
            query += """ AND (
                LOWER(s.name) LIKE %s
                OR LOWER(s.roll_no) LIKE %s
                OR LOWER(s.register_number) LIKE %s
            )"""
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]

        if from_date:
            query += " AND DATE(ep.uploaded_at) >= %s"
            params.append(from_date)

        if to_date:
            query += " AND DATE(ep.uploaded_at) <= %s"
            params.append(to_date)

        query += " ORDER BY ep.uploaded_at DESC"

        cur.execute(query, params)
        rows = cur.fetchall()
        papers = [dict(zip(cur.column_names, row)) for row in rows]

        return jsonify({"success": True, "papers": papers})

    except Exception as e:
        print("❌ api_get_all_papers error:", e)
        return jsonify({"success": False, "papers": []})
    finally:
        cur.close()
        conn.close()

@exam_papers_bp.route("/api/get_papers")
def api_get_papers():
    student_id = request.args.get("student_id")
    if not student_id:
        return jsonify({"success": False, "papers": [], "msg": "Missing student_id"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "papers": [], "msg": "DB error"}), 500

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, subject, exam_name, year, uploaded_at, file_url
            FROM exam_papers
            WHERE student_id = %s
            ORDER BY uploaded_at DESC
            """,
            (student_id,),
        )
        rows = cur.fetchall()
        papers = [dict(zip(cur.column_names, row)) for row in rows]
        return jsonify({"success": True, "papers": papers})
    finally:
        cur.close()
        conn.close()


# -------------------------------------------------------------------
# API: Upload (AJAX – NO PAGE REFRESH)
# -------------------------------------------------------------------
@exam_papers_bp.route("/api/upload", methods=["POST"])
def api_upload_exam_paper():
    """
    Handles AJAX upload. Expects form-data:
      student_id, subject_name, exam_name, year, file
    Returns JSON and does NOT refresh the page.
    """
    student_id = request.form.get("student_id")
    subject = request.form.get("subject_name")
    exam_name = request.form.get("exam_name")
    year = request.form.get("year")
    file = request.files.get("file")

    if not student_id:
        return jsonify({"success": False, "msg": "Student not selected"}), 400
    if not file or not file.filename:
        return jsonify({"success": False, "msg": "No file uploaded"}), 400
    if not allowed_file(file.filename):
        return jsonify({"success": False, "msg": "Invalid file type"}), 400

    # Unique safe filename
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    fname = f"{timestamp}_{secure_filename(file.filename)}"
    save_path = os.path.join(UPLOAD_FOLDER, fname)
    file.save(save_path)

    # We store ONLY the filename, not the whole path
    file_url_value = fname

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "msg": "DB error"}), 500

    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO exam_papers (student_id, subject, exam_name, year, file_url)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (student_id, subject, exam_name, year, file_url_value),
        )
        conn.commit()

        new_id = cur.lastrowid
        cur.execute(
            """
            SELECT id, subject, exam_name, year, uploaded_at, file_url
            FROM exam_papers
            WHERE id = %s
            """,
            (new_id,),
        )
        row = cur.fetchone()
        paper = dict(zip(cur.column_names, row))

        return jsonify({"success": True, "msg": "File uploaded", "paper": paper})
    except Exception as e:
        conn.rollback()
        print("❌ Upload exam paper error:", e)
        return jsonify({"success": False, "msg": "Upload failed"}), 500
    finally:
        cur.close()
        conn.close()


# -------------------------------------------------------------------
# (Optional) Classic POST route (kept for safety/backwards compatibility)
# -------------------------------------------------------------------
@exam_papers_bp.route("/upload", methods=["POST"])
def upload_exam_paper_legacy():
    """
    Old behaviour: form POST that redirects back with flash.
    Internally calls the same logic as api_upload_exam_paper.
    """
    # Just call the API and then redirect with flash.
    resp = api_upload_exam_paper()
    if isinstance(resp, tuple):
        data, status = resp
    else:
        data, status = resp, 200

    if hasattr(data, "get_json"):
        data = data.get_json()

    if status == 200 and data.get("success"):
        flash("File uploaded successfully", "success")
    else:
        flash(data.get("msg", "Upload failed"), "danger")

    return redirect(url_for("exam_papers.add_exam_paper"))


# -------------------------------------------------------------------
# API: Delete paper
# -------------------------------------------------------------------
@exam_papers_bp.route("/api/delete", methods=["POST"])
def api_delete_paper():
    paper_id = request.form.get("paper_id")
    if not paper_id:
        return jsonify({"success": False, "msg": "Missing paper_id"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "msg": "DB error"}), 500

    cur = conn.cursor()
    try:
        # First get filename
        cur.execute("SELECT file_url FROM exam_papers WHERE id = %s", (paper_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "msg": "Record not found"}), 404

        filename = row[0]
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            # not fatal, but log
            print("⚠️ Could not delete file from disk:", e)

        cur.execute("DELETE FROM exam_papers WHERE id = %s", (paper_id,))
        conn.commit()

        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        print("❌ Delete exam paper error:", e)
        return jsonify({"success": False, "msg": "Delete failed"}), 500
    finally:
        cur.close()
        conn.close()
