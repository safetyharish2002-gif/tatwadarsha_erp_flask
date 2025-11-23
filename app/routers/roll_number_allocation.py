# ============================================
# FILE: app/routers/roll_number_allocation.py
# MYSQL VERSION – FINAL & CORRECT
# ============================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import mysql.connector
import os

roll_bp = Blueprint("roll_allocation", __name__, url_prefix="/students")


# --------------------------------------------
#  MYSQL CONNECTION  (FIXED 🔥)
# --------------------------------------------
def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "srv366.hstgr.io"),
        user=os.getenv("MYSQL_USER", "u514260654_test_erp"),
        password=os.getenv("MYSQL_PASSWORD", "Tions@98"),
        database=os.getenv("MYSQL_DATABASE", "u514260654_test_erp"),
        auth_plugin="mysql_native_password"
    )


# --------------------------------------------
#  Load master items (course, department, batch, session)
# --------------------------------------------
def get_master_list(master_name: str):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute("""
            SELECT mi.name 
            FROM masters m 
            JOIN master_items mi ON m.id = mi.master_id
            WHERE m.master_name = %s
            ORDER BY mi.name ASC
        """, (master_name,))

        results = [row["name"] for row in cur.fetchall()]

        cur.close()
        db.close()
        return results

    except Exception as e:
        print("MASTER LOAD ERROR:", e)
        return []


# ===================================================
# 🔹 Load Roll Allocation Page
# ===================================================
@roll_bp.route("/roll_allocation", methods=["GET"])
def roll_allocation():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    try:
        db = get_db()
        cur = db.cursor(dictionary=True)

        # Load students
        cur.execute("SELECT * FROM students ORDER BY name ASC")
        rows = cur.fetchall()

        student_list = []
        for row in rows:
            student_list.append({
                "id": row["id"],
                "name": row.get("name", ""),
                "course": row.get("course", ""),
                "course_key": "",  # Not needed in MySQL version
                "department": row.get("department", ""),
                "batch": row.get("batch", ""),
                "session": row.get("session", ""),
                "roll_no": row.get("roll_no", ""),
                "enrollment_no": row.get("enrollment_no", "")
            })

        cur.close()
        db.close()

        # Dropdown values
        courses = get_master_list("course")
        departments = get_master_list("department")
        batches = get_master_list("batch")
        sessions = get_master_list("session")

        return render_template(
            "students/roll_number_allocation.html",
            students=student_list,
            courses=courses,
            departments=departments,
            batches=batches,
            sessions=sessions,
            title="Roll No / Enrollment Allocation"
        )

    except Exception as e:
        print("ROLL PAGE ERROR:", e)
        flash(f"⚠️ Error loading page: {e}", "danger")
        return redirect(url_for("dashboard"))


# ===================================================
# 🔹 Save Roll / Enrollment Numbers
# ===================================================
@roll_bp.route("/roll_allocation/save", methods=["POST"])
def save_roll_allocation():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        data = request.get_json()
        updates = data.get("updates", [])

        db = get_db()
        cur = db.cursor()

        updated_count = 0

        for item in updates:
            sid = item.get("id")
            roll_no = item.get("roll_no", "").strip()
            enrollment_no = item.get("enrollment_no", "").strip()

            # Same logic as Firebase: register_number == roll_no
            register_number = roll_no

            cur.execute("""
                UPDATE students
                SET roll_no=%s, enrollment_no=%s, register_number=%s
                WHERE id=%s
            """, (roll_no, enrollment_no, register_number, sid))

            updated_count += 1

        db.commit()
        cur.close()
        db.close()

        return jsonify({"success": True, "updated": updated_count})

    except Exception as e:
        print("SAVE ROLL ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500


# ===================================================
# 🔹 Auto Generate TIONS1, TIONS2 ...
# ===================================================
@roll_bp.route("/roll_allocation/generate", methods=["POST"])
def auto_generate_rolls():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        data = request.get_json()
        course = data.get("course")
        batch = data.get("batch")

        if not course or not batch:
            return jsonify({"success": False, "message": "Invalid filters"}), 400

        db = get_db()
        cur = db.cursor(dictionary=True)

        # Filter students
        cur.execute("""
            SELECT id FROM students
            WHERE course=%s AND batch=%s
            ORDER BY name ASC
        """, (course, batch))

        students = cur.fetchall()

        prefix = "TIONS"
        counter = 1
        updated_count = 0

        cur2 = db.cursor()

        for stu in students:
            roll_val = f"{prefix}{counter}"

            cur2.execute("""
                UPDATE students
                SET roll_no=%s, enrollment_no=%s, register_number=%s
                WHERE id=%s
            """, (roll_val, roll_val, roll_val, stu["id"]))

            counter += 1
            updated_count += 1

        db.commit()
        cur.close()
        cur2.close()
        db.close()

        return jsonify({"success": True, "updated": updated_count})

    except Exception as e:
        print("AUTO GEN ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500


# ===================================================
# 🔹 AJAX Filter Students
# ===================================================
@roll_bp.route("/roll_allocation/filter", methods=["POST"])
def filter_students():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        filters = request.get_json()

        course = filters.get("course")
        department = filters.get("department")
        batch = filters.get("batch")
        session_f = filters.get("session")

        query = "SELECT * FROM students WHERE 1=1"
        params = []

        if course:
            query += " AND course=%s"
            params.append(course)
        if department:
            query += " AND department=%s"
            params.append(department)
        if batch:
            query += " AND batch=%s"
            params.append(batch)
        if session_f:
            query += " AND session=%s"
            params.append(session_f)

        db = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        cur.close()
        db.close()

        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "name": row["name"],
                "course": row["course"],
                "course_key": "",
                "department": row["department"],
                "batch": row["batch"],
                "session": row["session"],
                "roll_no": row.get("roll_no", ""),
                "enrollment_no": row.get("enrollment_no", "")
            })

        return jsonify({"success": True, "students": result})

    except Exception as e:
        print("FILTER ERROR:", e)
        return jsonify({"success": False, "message": str(e)}), 500
