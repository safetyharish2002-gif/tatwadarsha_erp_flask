# FILE: app/routers/students.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
import pandas as pd
import os
import uuid
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Use the pooled connection (must exist at app/db.py)
from app.db import get_mysql_connection

# Load .env (so this module can connect independently)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ======================================
# 🔹 Blueprint Setup
# ======================================
students_bp = Blueprint("students", __name__)

# ======================================
# 🔹 Convert SQL row → Python dict  (GLOBAL FUNCTION)
# ======================================
def row_to_dict(cursor, row):
    return dict(zip(cursor.column_names, row))


# Columns layout for students (flat table)
STUDENTS_COLUMNS = [
    "id", "admission_date", "batch", "branch", "course", "department", "enrollment_no",
    "last_exam_passed", "previous_school", "register_number", "registration_no", "roll_no",
    "session", "tenth_board", "tenth_percent", "twelfth_board", "twelfth_percent",
    "name", "gender", "dob", "blood_group", "email", "aadhaar", "phone", "address",
    "caste", "religion", "father_name", "father_mobile", "father_occupation",
    "mother_name", "mother_mobile", "guardian_name", "guardian_mobile", "guardian_email",
    "annual_income", "account_holder", "account_number", "bank_name", "ifsc",
    "aadhaar_url", "marksheet_url", "migration_url", "photo_url", "tc_url", "created_at"
]

# Dropouts flat columns (student fields + dropout meta)
DROPOUTS_COLUMNS = [
    "id", "dropout_date", "dropout_reason", "dropout_remarks", "student_id",
    "admission_date", "batch", "branch", "course", "department", "enrollment_no",
    "last_exam_passed", "previous_school", "register_number", "registration_no",
    "roll_no", "session", "tenth_board", "tenth_percent", "twelfth_board",
    "twelfth_percent", "name", "gender", "dob", "blood_group", "email", "aadhaar",
    "phone", "address", "caste", "religion", "father_name", "father_mobile",
    "father_occupation", "mother_name", "mother_mobile", "guardian_name",
    "guardian_mobile", "guardian_email", "annual_income", "account_holder",
    "account_number", "bank_name", "ifsc", "aadhaar_url", "marksheet_url",
    "migration_url", "photo_url", "tc_url", "created_at"
]

# ======================================
# 🔹 Helper Function
# ======================================
def is_logged_in():
    """Check login session."""
    return session.get("logged_in", False)

def build_nested_student_from_row(rowd):
    """
    Take a flat student row dict and return nested structure:
    {
      personal: {...},
      academic: {...},
      family: {...},
      bank: {...},
      documents: {...},
      <other top-level fields if needed>
    }
    """
    personal = {
        "name": rowd.get("name"),
        "dob": rowd.get("dob"),
        "gender": rowd.get("gender"),
        "religion": rowd.get("religion"),
        "caste": rowd.get("caste"),
        "aadhaar": rowd.get("aadhaar"),
        "blood_group": rowd.get("blood_group"),
        "email": rowd.get("email"),
        "phone": rowd.get("phone"),
        "address": rowd.get("address"),
    }

    academic = {
        "session": rowd.get("session"),
        "course": rowd.get("course"),
        "branch": rowd.get("branch"),
        "department": rowd.get("department"),
        "batch": rowd.get("batch"),
        "register_number": rowd.get("register_number"),
        "admission_date": rowd.get("admission_date"),
        "previous_school": rowd.get("previous_school"),
        "tenth_board": rowd.get("tenth_board"),
        "tenth_percent": rowd.get("tenth_percent"),
        "twelfth_board": rowd.get("twelfth_board"),
        "twelfth_percent": rowd.get("twelfth_percent"),
        "last_exam_passed": rowd.get("last_exam_passed"),
        "roll_no": rowd.get("roll_no"),
        "registration_no": rowd.get("registration_no"),
        "enrollment_no": rowd.get("enrollment_no")
    }

    family = {
        "father_name": rowd.get("father_name"),
        "father_occupation": rowd.get("father_occupation"),
        "father_mobile": rowd.get("father_mobile"),
        "mother_name": rowd.get("mother_name"),
        "mother_mobile": rowd.get("mother_mobile"),
        "guardian_name": rowd.get("guardian_name"),
        "guardian_mobile": rowd.get("guardian_mobile"),
        "guardian_email": rowd.get("guardian_email"),
        "annual_income": rowd.get("annual_income")
    }

    bank = {
        "account_holder": rowd.get("account_holder"),
        "account_number": rowd.get("account_number"),
        "ifsc": rowd.get("ifsc"),
        "bank_name": rowd.get("bank_name")
    }

    documents = {
        "photo_url": rowd.get("photo_url"),
        "marksheet_url": rowd.get("marksheet_url"),
        "aadhaar_url": rowd.get("aadhaar_url"),
        "tc_url": rowd.get("tc_url"),
        "migration_url": rowd.get("migration_url"),
    }

    nested = {
        "personal": personal,
        "academic": academic,
        "family": family,
        "bank": bank,
        "documents": documents
    }

    nested["id"] = rowd.get("id")
    nested["created_at"] = rowd.get("created_at")

    # Add flat aliases so templates expecting flat structure still work
    nested["name"] = personal.get("name")
    nested["phone"] = personal.get("phone")
    nested["email"] = personal.get("email")
    nested["course"] = academic.get("course")
    nested["department"] = academic.get("department")
    nested["batch"] = academic.get("batch")
    nested["session"] = academic.get("session")
    nested["register_number"] = academic.get("register_number")
    nested["roll_no"] = academic.get("roll_no")
    nested["registration_no"] = academic.get("registration_no")
    nested["enrollment_no"] = academic.get("enrollment_no")

    return nested

def flatten_collections_from_form(form):
    """
    Collect structured student data from incoming form (same mapping as original).
    Returns a flat dict ready to insert/update students table (keys match STUDENTS_COLUMNS).
    """
    # personal
    name = form.get("name")
    dob = form.get("dob")
    gender = form.get("gender")
    religion = form.get("religion")
    caste = form.get("caste")
    aadhaar = form.get("aadhaar")
    blood_group = form.get("blood_group")
    email = form.get("email")
    phone = form.get("phone")
    address = form.get("address")

    # academic
    session_v = form.get("session")
    course = form.get("course")
    branch = form.get("branch")
    department = form.get("department")
    batch = form.get("batch")
    register_number = form.get("register_number")
    admission_date = form.get("admission_date")
    previous_school = form.get("previous_school")
    tenth_board = form.get("tenth_board")
    tenth_percent = form.get("tenth_percent")
    twelfth_board = form.get("twelfth_board")
    twelfth_percent = form.get("twelfth_percent")
    last_exam_passed = form.get("last_exam_passed")
    enrollment_no = form.get("enrollment_no")
    registration_no = form.get("registration_no")
    roll_no = form.get("roll_no")
    # family
    father_name = form.get("father_name")
    father_occupation = form.get("father_occupation")
    father_mobile = form.get("father_mobile")
    mother_name = form.get("mother_name")
    mother_mobile = form.get("mother_mobile")
    guardian_name = form.get("guardian_name")
    guardian_mobile = form.get("guardian_mobile")
    guardian_email = form.get("guardian_email")
    annual_income = form.get("annual_income")

    # bank
    account_holder = form.get("account_holder")
    account_number = form.get("account_number")
    ifsc = form.get("ifsc")
    bank_name = form.get("bank_name")

    # documents
    photo_url = form.get("photo_url")
    marksheet_url = form.get("marksheet_url")
    aadhaar_url = form.get("aadhaar_url")
    tc_url = form.get("tc_url")
    migration_url = form.get("migration_url")

    # created_at
    created_at = datetime.utcnow()

    flat = {
        "admission_date": admission_date,
        "batch": batch,
        "branch": branch,
        "course": course,
        "department": department,
        "enrollment_no": enrollment_no,
        "last_exam_passed": last_exam_passed,
        "previous_school": previous_school,
        "register_number": register_number,
        "registration_no": registration_no,
        "roll_no": roll_no,
        "session": session_v,
        "tenth_board": tenth_board,
        "tenth_percent": tenth_percent,
        "twelfth_board": twelfth_board,
        "twelfth_percent": twelfth_percent,
        "name": name,
        "gender": gender,
        "dob": dob,
        "blood_group": blood_group,
        "email": email,
        "aadhaar": aadhaar,
        "phone": phone,
        "address": address,
        "caste": caste,
        "religion": religion,
        "father_name": father_name,
        "father_mobile": father_mobile,
        "father_occupation": father_occupation,
        "mother_name": mother_name,
        "mother_mobile": mother_mobile,
        "guardian_name": guardian_name,
        "guardian_mobile": guardian_mobile,
        "guardian_email": guardian_email,
        "annual_income": annual_income,
        "account_holder": account_holder,
        "account_number": account_number,
        "bank_name": bank_name,
        "ifsc": ifsc,
        "aadhaar_url": aadhaar_url,
        "marksheet_url": marksheet_url,
        "migration_url": migration_url,
        "photo_url": photo_url,
        "tc_url": tc_url,
        "created_at": created_at
    }
    return flat

# ======================================
# 🔹 Students Home (Add Form)
# ======================================
@students_bp.route("/students")
def students_home():
    """Main Students form page."""
    if not is_logged_in():
        return redirect(url_for("login"))
    # Always pass an empty dict to prevent Jinja rendering issues
    return render_template("students/add_student.html", title="Add Student", mode="add", student={})

# ======================================
# 🔹 View Students
# ======================================
@students_bp.route("/students/view")
def view_students():
    """Display list of all students."""
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    students = []
    if not conn:
        flash("⚠️ Database connection failed.", "danger")
        return render_template("students/view_students.html", title="View Students", students=students)

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM students")
        rows = cur.fetchall()
        # use cursor.description for column names (compatible)
        cols = [d[0] for d in cur.description]
        for row in rows:
            rowd = dict(zip(cols, row))
            # maintain previous structure expectations: nested object
            nested = build_nested_student_from_row(rowd)
            students.append(nested)
        cur.close()
    except Exception as e:
        print("⚠️ Fetch students failed:", e)
        flash(f"⚠️ Error loading students: {e}", "danger")
        students = []
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return render_template("students/view_students.html", title="View Students", students=students)

# ======================================
# 🔹 Add Student (GET + POST)
# ======================================
@students_bp.route("/students/add", methods=["GET", "POST"])
def add_student():
    """Add new student to MySQL."""
    if not is_logged_in():
        return redirect(url_for("login"))

    # GET → Blank form
    if request.method == "GET":
        return render_template("students/add_student.html", title="Add Student", mode="add", student={})

    # POST → Save record
    conn = get_mysql_connection()
    if not conn:
        flash("⚠️ DB connection failed.", "danger")
        return redirect(url_for("students.add_student"))

    try:
        flat = flatten_collections_from_form(request.form)
        # generate id
        student_id = uuid.uuid4().hex

        # Ensure order and that missing keys won't raise KeyError
        cols = ["id"] + [c for c in STUDENTS_COLUMNS if c != "id"]
        # For every col except id, pull value from flat (may be None if not provided)
        vals = [student_id] + [flat.get(c) for c in cols if c != "id"]

        placeholders = ", ".join(["%s"] * len(cols))
        col_sql = ", ".join(cols)

        cur = conn.cursor()
        cur.execute(f"INSERT INTO students ({col_sql}) VALUES ({placeholders})", tuple(vals))
        conn.commit()
        cur.close()

        flash("✅ Student added successfully!", "success")
        print("✅ Student added successfully!")
        return redirect(url_for("students.view_students"))
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("⚠️ Add student error:", e)
        flash(f"❌ Error adding student: {e}", "danger")
        return redirect(url_for("students.add_student"))
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ======================================
# 🔹 Edit Student (GET)
# ======================================
@students_bp.route("/students/edit/<string:student_id>", methods=["GET"])
def edit_student(student_id):
    """Load existing student for editing."""
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    if not conn:
        flash("⚠️ DB connection failed.", "danger")
        return redirect(url_for("students.view_students"))

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            flash("⚠️ Student not found!", "danger")
            return redirect(url_for("students.view_students"))
        cols = [d[0] for d in cur.description]
        rowd = dict(zip(cols, row))
        nested = build_nested_student_from_row(rowd)
        cur.close()
        return render_template(
            "students/add_student.html",
            title="Edit Student",
            mode="edit",
            student=nested,
            student_id=student_id
        )
    except Exception as e:
        print("⚠️ Edit fetch error:", e)
        flash(f"❌ Error loading student: {e}", "danger")
        return redirect(url_for("students.view_students"))
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ======================================
# 🔹 Update Student (POST)
# ======================================
@students_bp.route("/students/update/<string:student_id>", methods=["POST"])
def update_student(student_id):
    """Update an existing student in MySQL safely (merge form with existing)."""
    if not is_logged_in():
        return redirect(url_for("login"))
    conn = get_mysql_connection()
    if not conn:
        flash("⚠️ DB connection failed.", "danger")
        return redirect(url_for("students.view_students"))

    try:
        flat = flatten_collections_from_form(request.form)

        # Fetch existing DB record — prevents overwriting with blank values
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        existing_row = cur.fetchone()
        if not existing_row:
            cur.close()
            flash("⚠️ Student not found!", "danger")
            return redirect(url_for("students.view_students"))
        cols = [d[0] for d in cur.description]
        existing = dict(zip(cols, existing_row))

        # Merge new values with existing
        updates = []
        params = []
        for col in STUDENTS_COLUMNS:
            if col == "id":
                continue
            new_val = flat.get(col)
            # If new value is empty, keep old value
            if new_val is None or (isinstance(new_val, str) and new_val.strip() == ""):
                value_to_set = existing.get(col)
            else:
                value_to_set = new_val

            updates.append(f"{col} = %s")
            params.append(value_to_set)

        params.append(student_id)

        cur.execute(f"UPDATE students SET {', '.join(updates)} WHERE id = %s", tuple(params))
        conn.commit()
        cur.close()

        flash("🔄 Student updated successfully!", "success")
        print(f"📝 Updated student {student_id}")
        return redirect(url_for("students.view_students"))
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("⚠️ Update student error:", e)
        flash(f"❌ Error updating student: {e}", "danger")
        return redirect(url_for("students.view_students"))
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ======================================
# 🔹 Delete Student
# ======================================
@students_bp.route("/students/delete/<string:student_id>", methods=["POST"])
def delete_student(student_id):
    """Delete student record."""
    if not is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    conn = get_mysql_connection()
    if not conn:
        flash("⚠️ DB connection failed.", "danger")
        return redirect(url_for("students.view_students"))

    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM students WHERE id = %s", (student_id,))
        conn.commit()
        cur.close()
        print(f"🗑️ Deleted student {student_id}")
        flash("🗑️ Student deleted successfully!", "success")
        return redirect(url_for("students.view_students"))
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("⚠️ Delete failed:", e)
        flash(f"❌ Error deleting student: {e}", "danger")
        return redirect(url_for("students.view_students"))
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ======================================
# 🔹 Helper: Collect Form Data (original nested-> we map to flat)
# ======================================
def collect_student_data(request):
    """Return nested structure like original function did, but built from form."""
    # This mirrors the original collect_student_data but uses form fields.
    # We keep this function to preserve any callers.
    personal = {
        "name": request.form.get("name"),
        "dob": request.form.get("dob"),
        "gender": request.form.get("gender"),
        "religion": request.form.get("religion"),
        "caste": request.form.get("caste"),
        "aadhaar": request.form.get("aadhaar"),
        "blood_group": request.form.get("blood_group"),
        "email": request.form.get("email"),
        "phone": request.form.get("phone"),
        "address": request.form.get("address"),
    }

    academic = {
        "session": request.form.get("session"),
        "course": request.form.get("course"),
        "branch": request.form.get("branch"),
        "department": request.form.get("department"),
        "batch": request.form.get("batch"),
        "register_number": request.form.get("register_number"),
        "admission_date": request.form.get("admission_date"),
        "previous_school": request.form.get("previous_school"),
        "tenth_board": request.form.get("tenth_board"),
        "tenth_percent": request.form.get("tenth_percent"),
        "twelfth_board": request.form.get("twelfth_board"),
        "twelfth_percent": request.form.get("twelfth_percent"),
        "last_exam_passed": request.form.get("last_exam_passed"),
    }

    family = {
        "father_name": request.form.get("father_name"),
        "father_occupation": request.form.get("father_occupation"),
        "father_mobile": request.form.get("father_mobile"),
        "mother_name": request.form.get("mother_name"),
        "mother_mobile": request.form.get("mother_mobile"),
        "guardian_name": request.form.get("guardian_name"),
        "guardian_mobile": request.form.get("guardian_mobile"),
        "guardian_email": request.form.get("guardian_email"),
        "annual_income": request.form.get("annual_income"),
    }

    bank = {
        "account_holder": request.form.get("account_holder"),
        "account_number": request.form.get("account_number"),
        "ifsc": request.form.get("ifsc"),
        "bank_name": request.form.get("bank_name"),
    }

    documents = {
        "photo_url": request.form.get("photo_url"),
        "marksheet_url": request.form.get("marksheet_url"),
        "aadhaar_url": request.form.get("aadhaar_url"),
        "tc_url": request.form.get("tc_url"),
        "migration_url": request.form.get("migration_url"),
    }

    return {
        "personal": personal,
        "academic": academic,
        "family": family,
        "bank": bank,
        "documents": documents,
    }

# ======================================
# 🔹 Download Sample Excel
# ======================================
@students_bp.route("/students/sample", methods=["GET"])
def download_sample():
    """Download sample Excel template for bulk upload."""
    sample_path = os.path.join(os.path.dirname(__file__), "..", "static", "sample_students.xlsx")
    return send_from_directory(os.path.dirname(sample_path), "sample_students.xlsx", as_attachment=True)

# ======================================
# 🔹 Bulk Upload Students
# ======================================
@students_bp.route("/students/bulk_upload", methods=["GET", "POST"])
def bulk_upload_students():
    """Bulk upload students via Excel/CSV."""
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("students/bulk_upload.html", title="Bulk Upload Students")

    file = request.files.get("file")
    if not file or file.filename == "":
        flash("⚠️ Please select an Excel or CSV file!", "danger")
        return redirect(url_for("students.bulk_upload_students"))

    conn = get_mysql_connection()
    if not conn:
        flash("⚠️ DB connection failed.", "danger")
        return redirect(url_for("students.bulk_upload_students"))

    try:
        if file.filename.endswith(".xlsx"):
            df = pd.read_excel(file)
        elif file.filename.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            flash("❌ Invalid file type! Please upload .xlsx or .csv", "danger")
            return redirect(url_for("students.bulk_upload_students"))

        required_cols = ["Name", "Roll No", "Department", "Course", "Branch", "Batch", "Session"]
        for col in required_cols:
            if col not in df.columns:
                flash("❌ Invalid file format. Use the sample template!", "danger")
                return redirect(url_for("students.bulk_upload_students"))

        added = 0
        cur = conn.cursor()
        for _, row in df.iterrows():
            # Build flat record
            flat = {
                "name": str(row.get("Name", "")).strip(),
                "roll_no": str(row.get("Roll No", "")).strip(),
                "department": str(row.get("Department", "")).strip(),
                "course": str(row.get("Course", "")).strip(),
                "branch": str(row.get("Branch", "")).strip(),
                "batch": str(row.get("Batch", "")).strip(),
                "session": str(row.get("Session", "")).strip(),
                "register_number": str(row.get("Register Number", "")).strip() if "Register Number" in row else ""
            }
            student_id = uuid.uuid4().hex
            cols = ["id"] + list(flat.keys()) + ["created_at"]
            vals = [student_id] + [flat[k] for k in flat.keys()] + [datetime.utcnow()]
            placeholders = ", ".join(["%s"] * len(vals))
            col_sql = ", ".join(cols)
            cur.execute(f"INSERT INTO students ({col_sql}) VALUES ({placeholders})", tuple(vals))
            added += 1

        conn.commit()
        cur.close()

        flash(f"✅ Successfully uploaded {added} students!", "success")
        return redirect(url_for("students.bulk_upload_students"))

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("⚠️ Bulk upload error:", e)
        flash(f"❌ Error processing file: {e}", "danger")
        return redirect(url_for("students.bulk_upload_students"))
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ======================================
# 🔹 DROPOUT STUDENTS PAGE (HTML PAGE)
# ======================================
@students_bp.route("/dropout_students")
def dropout_students_page():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("students/dropout_students.html", title="Dropout Students")


# ======================================
# 🔹 API: Get Students + Dropouts
# ======================================
@students_bp.route("/api/get_students", methods=["GET"])
def api_get_students():
    if not is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        # Filters
        session_f     = request.args.get("session", "").strip()
        course_f      = request.args.get("course", "").strip()
        branch_f      = request.args.get("branch", "").strip()
        department_f  = request.args.get("department", "").strip()
        batch_f       = request.args.get("year", "").strip()
        search_f      = request.args.get("search", "").strip().lower()

        conn = get_mysql_connection()
        if not conn:
            return jsonify({"success": False, "message": "DB connection failed"}), 500

        cur = conn.cursor()

        # WHERE filters
        where_clauses = []
        params = []

        if session_f:
            where_clauses.append("session = %s"); params.append(session_f)
        if course_f:
            where_clauses.append("course = %s"); params.append(course_f)
        if branch_f:
            where_clauses.append("branch = %s"); params.append(branch_f)
        if department_f:
            where_clauses.append("department = %s"); params.append(department_f)
        if batch_f:
            where_clauses.append("batch = %s"); params.append(batch_f)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # ------------------------
        # ACTIVE STUDENTS
        # ------------------------
        cur.execute(f"SELECT * FROM students {where_sql}", tuple(params))
        student_rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

        students_list = []
        for row in student_rows:
            rowd = dict(zip(cols, row))
            nested = build_nested_student_from_row(rowd)

            # search
            hay = " ".join([
                (nested.get("personal") or {}).get("name", ""),
                (nested.get("academic") or {}).get("register_number", ""),
                (nested.get("personal") or {}).get("phone", "")
            ]).lower()

            if search_f and search_f not in hay:
                continue

            students_list.append(nested)

        # ------------------------
        # DROPOUT STUDENTS (with FULL DETAILS)
        # ------------------------
        cur.execute("SELECT * FROM dropouts")
        drop_rows = cur.fetchall()
        dcols = [d[0] for d in cur.description]

        dropouts = []
        for drow in drop_rows:
            d = dict(zip(dcols, drow))

            dropouts.append({
                "id": d.get("id"),

                "personal": {
                    "name": d.get("name"),
                    "dob": d.get("dob"),
                    "gender": d.get("gender"),
                    "religion": d.get("religion"),
                    "caste": d.get("caste"),
                    "aadhaar": d.get("aadhaar"),
                    "blood_group": d.get("blood_group"),
                    "email": d.get("email"),
                    "phone": d.get("phone"),
                    "address": d.get("address")
                },

                "academic": {
                    "session": d.get("session"),
                    "course": d.get("course"),
                    "branch": d.get("branch"),
                    "department": d.get("department"),
                    "batch": d.get("batch"),
                    "register_number": d.get("register_number"),
                    "admission_date": d.get("admission_date"),
                    "previous_school": d.get("previous_school"),
                    "tenth_board": d.get("tenth_board"),
                    "tenth_percent": d.get("tenth_percent"),
                    "twelfth_board": d.get("twelfth_board"),
                    "twelfth_percent": d.get("twelfth_percent"),
                    "last_exam_passed": d.get("last_exam_passed"),
                    "roll_no": d.get("roll_no"),
                    "enrollment_no": d.get("enrollment_no"),
                    "registration_no": d.get("registration_no")
                },

                "family": {
                    "father_name": d.get("father_name"),
                    "father_occupation": d.get("father_occupation"),
                    "father_mobile": d.get("father_mobile"),
                    "mother_name": d.get("mother_name"),
                    "mother_mobile": d.get("mother_mobile"),
                    "guardian_name": d.get("guardian_name"),
                    "guardian_mobile": d.get("guardian_mobile"),
                    "guardian_email": d.get("guardian_email"),
                    "annual_income": d.get("annual_income")
                },

                "bank": {
                    "account_holder": d.get("account_holder"),
                    "account_number": d.get("account_number"),
                    "bank_name": d.get("bank_name"),
                    "ifsc": d.get("ifsc")
                },

                "documents": {
                    "photo_url": d.get("photo_url"),
                    "aadhaar_url": d.get("aadhaar_url"),
                    "marksheet_url": d.get("marksheet_url"),
                    "migration_url": d.get("migration_url"),
                    "tc_url": d.get("tc_url")
                },

                "dropout": {
                    "date": d.get("dropout_date"),
                    "reason": d.get("dropout_reason"),
                    "remarks": d.get("dropout_remarks")
                }
            })

        cur.close()
        try:
            conn.close()
        except Exception:
            pass

        return jsonify({
            "success": True,
            "students": students_list,
            "dropouts": dropouts
        })

    except Exception as e:
        print("⚠️ GET STUDENTS API ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500


# ======================================
# 🔹 Mark Student as Dropped
# ======================================
@students_bp.route("/api/mark_dropout", methods=["POST"])
def mark_dropout():
    if not is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        data = request.get_json(force=True)
        student_id = data.get("student_id")
        dropout_date = data.get("date") or data.get("dropout_date")
        reason = data.get("reason") or data.get("dropout_reason")
        remarks = data.get("remarks") or data.get("dropout_remarks")

        if not student_id:
            return jsonify({"success": False, "message": "Missing student ID"}), 400
        if not dropout_date:
            return jsonify({"success": False, "message": "Missing dropout date"}), 400

        conn = get_mysql_connection()
        if not conn:
            return jsonify({"success": False, "message": "DB connection failed"}), 500

        cur = conn.cursor()

        # Fetch student
        cur.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            try: conn.close()
            except: pass
            return jsonify({"success": False, "message": "Student not found"}), 404

        cols = [d[0] for d in cur.description]
        student_row = dict(zip(cols, row))

        # Insert into dropouts
        cols = []
        vals = []

        for c in DROPOUTS_COLUMNS:
            if c == "id":
                cols.append("id"); vals.append(student_id)
            elif c == "dropout_date":
                cols.append("dropout_date"); vals.append(dropout_date)
            elif c == "dropout_reason":
                cols.append("dropout_reason"); vals.append(reason)
            elif c == "dropout_remarks":
                cols.append("dropout_remarks"); vals.append(remarks)
            elif c == "student_id":
                cols.append("student_id"); vals.append(student_id)
            else:
                cols.append(c); vals.append(student_row.get(c))

        placeholders = ", ".join(["%s"] * len(vals))
        col_sql = ", ".join(cols)

        cur.execute(
            f"INSERT INTO dropouts ({col_sql}) VALUES ({placeholders})",
            tuple(vals)
        )

        # Delete from students
        cur.execute("DELETE FROM students WHERE id = %s", (student_id,))
        conn.commit()

        cur.close()
        try: conn.close()
        except: pass

        return jsonify({"success": True})

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("DROP ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500


# ======================================
# 🔹 Mark Admit (Restore Student)
# ======================================
@students_bp.route("/mark_admit", methods=["POST"])
def mark_admit():
    if not is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        data = request.get_json(force=True, silent=True) or {}
        student_id = data.get("student_id")

        if not student_id:
            return jsonify({"success": False, "message": "Missing student_id"}), 400

        conn = get_mysql_connection()
        if not conn:
            return jsonify({"success": False, "message": "DB connection failed"}), 500

        cur = conn.cursor()

        # Get dropout row
        cur.execute("SELECT * FROM dropouts WHERE id = %s", (student_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            try: conn.close()
            except: pass
            return jsonify({"success": False, "message": "Dropout record not found"}), 404

        dcols = [d[0] for d in cur.description]
        drop_row = dict(zip(dcols, row))

        # Build insert map for students table
        student_map = {}
        for c in STUDENTS_COLUMNS:
            if c == "id":
                student_map[c] = student_id
            else:
                student_map[c] = drop_row.get(c)

        cols = ", ".join(student_map.keys())
        placeholders = ", ".join(["%s"] * len(student_map))

        cur.execute(
            f"INSERT INTO students ({cols}) VALUES ({placeholders})",
            tuple(student_map.values())
        )

        # Delete from dropouts
        cur.execute("DELETE FROM dropouts WHERE id = %s", (student_id,))
        conn.commit()

        cur.close()
        try: conn.close()
        except: pass

        return jsonify({"success": True})

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("ERROR in mark_admit:", e)
        return jsonify({"success": False, "message": str(e)}), 500

# ============================
# 🔵 PROMOTE STUDENTS PAGE
# ============================
@students_bp.route("/students/promote", methods=["GET"])
def promote_page():
    """Render Promote Students Page."""
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("students/promote_students.html", title="Promote Students")

# ============================
# 🔵 API — FETCH STUDENTS FOR PROMOTION
# ============================
@students_bp.route("/api/promote_get_students", methods=["GET"])
def api_promote_get_students():
    """
    Filters: session, course, branch, department, batch
    Returns active students only.
    """
    if not is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    session_f     = request.args.get("session", "").strip()
    course_f      = request.args.get("course", "").strip()
    branch_f      = request.args.get("branch", "").strip()
    department_f  = request.args.get("department", "").strip()
    batch_f       = request.args.get("batch", "").strip()

    conn = get_mysql_connection()
    if not conn:
        return jsonify({"success": False, "message": "DB connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM students")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        result = []
        for row in rows:
            rowd = dict(zip(cols, row))
            a = {
                "session": rowd.get("session"),
                "course": rowd.get("course"),
                "branch": rowd.get("branch"),
                "department": rowd.get("department"),
                "batch": rowd.get("batch")
            }

            # apply filters
            if session_f and a.get("session") != session_f:
                continue
            if course_f and a.get("course") != course_f:
                continue
            if branch_f and a.get("branch") != branch_f:
                continue
            if department_f and a.get("department") != department_f:
                continue
            if batch_f and a.get("batch") != batch_f:
                continue

            nested = build_nested_student_from_row(rowd)
            result.append(nested)

        cur.close()
        try: conn.close()
        except: pass
        return jsonify({"success": True, "students": result})
    except Exception as e:
        print("PROMOTE FETCH ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500

# ============================
# 🔵 API — APPLY PROMOTION
# ============================
@students_bp.route("/api/promote_students", methods=["POST"])
def api_promote_students():
    """
    Payload Example:
    {
       "student_ids": ["-Oi12...", "-Oiw8..."],
       "updates": { "session": "2025-26", "course": "BSC NURSING", ... }
    }
    """
    if not is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        payload = request.get_json(force=True)
        student_ids = payload.get("student_ids") or []
        updates     = payload.get("updates") or {}

        if not student_ids:
            return jsonify({"success": False, "message": "No student ids provided"}), 400
        if not updates:
            return jsonify({"success": False, "message": "No updates provided"}), 400

        conn = get_mysql_connection()
        if not conn:
            return jsonify({"success": False, "message": "DB connection failed"}), 500

        cur = conn.cursor()
        updated_count = 0
        for sid in student_ids:
            # fetch current student row
            cur.execute("SELECT * FROM students WHERE id = %s", (sid,))
            row = cur.fetchone()
            if not row:
                continue
            cols = [d[0] for d in cur.description]
            rowd = dict(zip(cols, row))

            # build academic update mapping
            set_clauses = []
            params = []
            for k, v in updates.items():
                # Only update columns that exist in students table
                if k in rowd:
                    set_clauses.append(f"{k} = %s")
                    params.append(v)
                else:
                    # also allow updating common academic fields mapped in db
                    if k in ["session", "course", "branch", "department", "batch", "register_number", "roll_no"]:
                        set_clauses.append(f"{k} = %s")
                        params.append(v)
            if not set_clauses:
                continue
            params.append(sid)
            cur.execute(f"UPDATE students SET {', '.join(set_clauses)} WHERE id = %s", tuple(params))
            updated_count += 1

        conn.commit()
        cur.close()
        try: conn.close()
        except: pass
        return jsonify({"success": True, "updated": updated_count})

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("PROMOTE ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500

# ============================
# 🔵 SESSION-WISE STUDENTS PAGE
# ============================
@students_bp.route("/students/session-wise", methods=["GET"])
def session_wise_page():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("students/session_wise_student.html", title="Session Wise Students")

# ============================
# 🔵 SESSION-WISE STUDENTS DATA (API)
# ============================
@students_bp.route("/students/session-wise-data", methods=["GET"])
def session_wise_data():
    """
    Returns an ARRAY of full nested student objects filtered by:
      - session
      - course
      - branch
      - department
      - batch
    """
    if not is_logged_in():
        return jsonify([])

    try:
        session_f    = (request.args.get("session") or "").strip()
        course_f     = (request.args.get("course") or "").strip()
        branch_f     = (request.args.get("branch") or "").strip()
        department_f = (request.args.get("department") or "").strip()
        batch_f      = (request.args.get("batch") or "").strip()

        conn = get_mysql_connection()
        if not conn:
            return jsonify([])

        cur = conn.cursor()
        cur.execute("SELECT * FROM students")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        result = []
        for row in rows:
            rowd = dict(zip(cols, row))
            a = rowd  # academic fields are keys on top-level in rowd

            if session_f and (a.get("session") or "") != session_f:
                continue
            if course_f and (a.get("course") or "") != course_f:
                continue
            if branch_f and (a.get("branch") or "") != branch_f:
                continue
            if department_f and (a.get("department") or "") != department_f:
                continue
            if batch_f and (a.get("batch") or "") != batch_f:
                continue

            nested = build_nested_student_from_row(rowd)
            result.append(nested)

        cur.close()
        try: conn.close()
        except: pass
        return jsonify(result)
    except Exception as e:
        print("⚠️ SESSION WISE DATA ERROR:", e)
        return jsonify([])

# End of file
# ======================================
# 🔐 STUDENT LOGIN REQUIRED DECORATOR
# ======================================
import jwt
from functools import wraps
from flask import current_app

def student_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        token = auth.split(" ", 1)[1]
        try:
            payload = jwt.decode(
                token,
                current_app.config.get("SECRET_KEY", "tatwadarsha_secret"),
                algorithms=["HS256"]
            )
            request.student_id = payload["student_id"]
        except Exception:
            return jsonify({"success": False, "message": "Invalid or expired token"}), 401

        return f(*args, **kwargs)
    return wrapper
# ======================================
# 👤 API — STUDENT PROFILE (MOBILE)
# ======================================
@students_bp.route("/api/student/profile", methods=["GET"])
@student_login_required
def api_student_profile():
    conn = get_mysql_connection()
    if not conn:
        return jsonify({"success": False, "message": "DB connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE id = %s", (request.student_id,))
        row = cur.fetchone()

        if not row:
            return jsonify({"success": False, "message": "Student not found"}), 404

        cols = [d[0] for d in cur.description]
        rowd = dict(zip(cols, row))

        profile = build_nested_student_from_row(rowd)

        return jsonify({
            "success": True,
            "student": profile
        })

    finally:
        try: conn.close()
        except: pass
# ======================================
# 📁 FILE SAVE HELPER
# ======================================
def save_student_file(file, subfolder, prefix):
    filename = f"{prefix}_{request.student_id}_{uuid.uuid4().hex}.jpg"
    upload_dir = os.path.join("uploads", "students", subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    path = os.path.join(upload_dir, filename)
    file.save(path)

    return f"/uploads/students/{subfolder}/{filename}"
# ======================================
# 📸 API — UPDATE STUDENT PHOTO
# ======================================
@students_bp.route("/api/student/update-photo", methods=["POST"])
@student_login_required
def api_update_student_photo():
    if "photo" not in request.files:
        return jsonify({"success": False, "message": "Photo required"}), 400

    photo = request.files["photo"]
    photo_url = save_student_file(photo, "photos", "photo")

    conn = get_mysql_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE students SET photo_url = %s WHERE id = %s",
        (photo_url, request.student_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "photo_url": photo_url})
# ======================================
# 📄 API — UPLOAD 10TH MARKSHEET
# ======================================
@students_bp.route("/api/student/upload/marksheet_10", methods=["POST"])
@student_login_required
def api_upload_10th_marksheet():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "File required"}), 400

    url = save_student_file(request.files["file"], "marksheets", "marksheet")

    conn = get_mysql_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE students SET marksheet_url = %s WHERE id = %s",
        (url, request.student_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "marksheet_url": url})
# ======================================
# 🪪 API — UPLOAD AADHAAR
# ======================================
@students_bp.route("/api/student/upload/aadhaar", methods=["POST"])
@student_login_required
def api_upload_aadhaar():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "File required"}), 400

    url = save_student_file(request.files["file"], "aadhaar", "aadhaar")

    conn = get_mysql_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE students SET aadhaar_url = %s WHERE id = %s",
        (url, request.student_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "aadhaar_url": url})
# ======================================
# 📜 API — UPLOAD TRANSFER CERTIFICATE
# ======================================
@students_bp.route("/api/student/upload/tc", methods=["POST"])
@student_login_required
def api_upload_tc():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "File required"}), 400

    url = save_student_file(request.files["file"], "tc", "tc")

    conn = get_mysql_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE students SET tc_url = %s WHERE id = %s",
        (url, request.student_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "tc_url": url})
# ======================================
# 📑 API — UPLOAD MIGRATION CERTIFICATE
# ======================================
@students_bp.route("/api/student/upload/migration", methods=["POST"])
@student_login_required
def api_upload_migration():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "File required"}), 400

    url = save_student_file(request.files["file"], "migration", "migration")

    conn = get_mysql_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE students SET migration_url = %s WHERE id = %s",
        (url, request.student_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "migration_url": url})
