# app/routers/fees.py
"""
Fees blueprint for Tatwadarsha ERP
"""

from flask import Blueprint, render_template, request, current_app, jsonify, redirect, url_for, flash
import mysql.connector
from mysql.connector import pooling
from datetime import datetime, date

fees_bp = Blueprint("fees", template_folder="../templates/fee")

# Lazy-created connection pool singleton stored on blueprint
_conn_pool = None


def get_pool():
    global _conn_pool
    if _conn_pool is None:
        cfg = current_app.config.get("MYSQL") or {}
        pool_name = cfg.get("pool_name", "erp_pool")
        pool_size = cfg.get("pool_size", 5)
        _conn_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name=pool_name,
            pool_size=pool_size,
            host=cfg.get("host", "localhost"),
            user=cfg.get("user", "root"),
            password=cfg.get("password", ""),
            database=cfg.get("database", ""),
            charset="utf8mb4"
        )
    return _conn_pool


def get_db_conn():
    pool = get_pool()
    return pool.get_connection()


# -----------------------
# Helper utilities
# -----------------------
def fetchall_dict(cursor):
    cols = [c[0] for c in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    return [dict(zip(cols, row)) for row in rows]


# -----------------------
# Main page
# -----------------------
@fees_bp.route("/", methods=["GET"])
def index():
    return render_template("fees.html")


# -----------------------
# 1) Fee Master
# -----------------------
@fees_bp.route("/master", methods=["GET", "POST"])
def fee_master():
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            action = request.form.get("action")

            if action == "add_head":
                name = request.form.get("head_name")
                desc = request.form.get("head_desc")
                if name:
                    cur.execute("INSERT INTO fee_heads (name, description) VALUES (%s, %s)", (name, desc))
                    conn.commit()
                    flash("Fee head added.", "success")
                return redirect(url_for('fees.fee_master'))

            if action == "add_type":
                tname = request.form.get("type_name")
                if tname:
                    cur.execute("INSERT INTO fee_types (name) VALUES (%s)", (tname,))
                    conn.commit()
                    flash("Fee type added.", "success")
                return redirect(url_for('fees.fee_master'))

            if action == "add_master":
                head_id = request.form.get("head_id")
                type_id = request.form.get("type_id")
                amount = request.form.get("amount") or 0
                start_date = request.form.get("start_date") or None
                end_date = request.form.get("end_date") or None
                cur.execute(
                    "INSERT INTO fee_master (head_id, type_id, amount, start_date, end_date) VALUES (%s,%s,%s,%s,%s)",
                    (head_id, type_id, amount, start_date or None, end_date or None)
                )
                conn.commit()
                flash("Fee master entry added.", "success")
                return redirect(url_for('fees.fee_master'))

        cur.execute("SELECT * FROM fee_heads ORDER BY name")
        heads = fetchall_dict(cur)

        cur.execute("SELECT * FROM fee_types ORDER BY name")
        types = fetchall_dict(cur)

        cur.execute("""
            SELECT fm.*, fh.name AS head_name, ft.name AS type_name
            FROM fee_master fm
            JOIN fee_heads fh ON fm.head_id = fh.id
            JOIN fee_types ft ON fm.type_id = ft.id
            ORDER BY fm.created_at DESC
        """)
        masters = fetchall_dict(cur)

        return render_template("fee_master.html", heads=heads, types=types, masters=masters)

    finally:
        cur.close()
        conn.close()


@fees_bp.route("/master/delete/<int:master_id>", methods=["POST"])
def delete_fee_master(master_id):
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM fee_master WHERE id=%s", (master_id,))
        conn.commit()
        flash("Fee master entry deleted.", "warning")
        return redirect(url_for('fees.fee_master'))
    finally:
        cur.close()
        conn.close()


# -----------------------
# AJAX Endpoints
# -----------------------
@fees_bp.route("/api/fee_masters", methods=["GET"])
def api_fee_masters():
    head_id = request.args.get("head_id")
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        q = """
        SELECT fm.id, fm.amount, fm.start_date, fm.end_date, fh.name as head_name, ft.name as type_name
        FROM fee_master fm
        JOIN fee_heads fh ON fm.head_id = fh.id
        JOIN fee_types ft ON fm.type_id = ft.id
        """
        params = []
        if head_id:
            q += " WHERE fm.head_id = %s"
            params.append(head_id)
        cur.execute(q, tuple(params))
        data = fetchall_dict(cur)
        return jsonify(data)
    finally:
        cur.close()
        conn.close()


@fees_bp.route("/api/students_search", methods=["GET"])
def api_students_search():
    qterm = request.args.get("q", "").strip()
    session_f = request.args.get("session")
    course_f = request.args.get("course")

    conn = get_db_conn()
    cur = conn.cursor()
    try:
        sql = "SELECT student_id, name, session, course, branch, batch FROM students WHERE 1=1"
        params = []

        if qterm:
            sql += " AND (student_id LIKE %s OR name LIKE %s)"
            like = f"%{qterm}%"
            params.extend([like, like])

        if session_f:
            sql += " AND session = %s"; params.append(session_f)
        if course_f:
            sql += " AND course = %s"; params.append(course_f)

        sql += " LIMIT 100"
        cur.execute(sql, tuple(params))
        return jsonify(fetchall_dict(cur))
    finally:
        cur.close()
        conn.close()


# -----------------------
# 2) Assign Fee
# -----------------------
@fees_bp.route("/assign", methods=["GET", "POST"])
def assign_fee():
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        if request.method == "GET":
            cur.execute("SELECT id, name FROM fee_heads ORDER BY name")
            heads = fetchall_dict(cur)

            cur.execute("""
                SELECT fm.id, fm.amount, fm.start_date, fm.end_date, fh.name head_name, ft.name type_name
                FROM fee_master fm
                JOIN fee_heads fh ON fm.head_id = fh.id
                JOIN fee_types ft ON fm.type_id = ft.id
                ORDER BY fh.name, fm.start_date DESC
            """)
            masters = fetchall_dict(cur)
            return render_template("assign_fee.html", heads=heads, masters=masters)

        action = request.form.get("action")

        if action == "assign_single":
            student_id = request.form.get("student_id")
            fee_master_id = request.form.get("fee_master_id")

            cur.execute("SELECT amount, end_date FROM fee_master WHERE id=%s", (fee_master_id,))
            master = cur.fetchone()

            if master:
                amount, end_date = master
                due_date = end_date or None

                cur.execute("""
                    INSERT INTO assigned_fees (student_id, fee_master_id, due_date, amount)
                    VALUES (%s,%s,%s,%s)
                """, (student_id, fee_master_id, due_date, amount))
                conn.commit()
                flash("Fee assigned to student.", "success")
            else:
                flash("Fee master not found.", "danger")

            return redirect(url_for('fees.assign_fee'))

        if action == "assign_bulk":
            fee_master_id = request.form.get("fee_master_id")
            student_ids = request.form.get("student_ids")

            if student_ids:
                ids = [s.strip() for s in student_ids.split(",") if s.strip()]
                cur.execute("SELECT amount, end_date FROM fee_master WHERE id=%s", (fee_master_id,))
                master = cur.fetchone()

                if not master:
                    flash("Fee master not found.", "danger")
                    return redirect(url_for('fees.assign_fee'))

                amount, end_date = master
                due_date = end_date or None

                for sid in ids:
                    cur.execute("""
                        INSERT INTO assigned_fees (student_id, fee_master_id, due_date, amount)
                        VALUES (%s,%s,%s,%s)
                    """, (sid, fee_master_id, due_date, amount))

                conn.commit()
                flash(f"Assigned fee to {len(ids)} students.", "success")

            return redirect(url_for('fees.assign_fee'))

    finally:
        cur.close()
        conn.close()


# -----------------------
# 3) Fee Details (Assigned fees + payments)
# -----------------------
@fees_bp.route("/details", methods=["GET", "POST"])
def fee_details():
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            action = request.form.get("action")

            if action == "add_payment":
                assigned_fee_id = request.form.get("assigned_fee_id")
                amount_paid = float(request.form.get("amount_paid") or 0)
                payment_mode = request.form.get("payment_mode")
                notes = request.form.get("notes")

                cur.execute("""
                    INSERT INTO fee_payments (assigned_fee_id, amount_paid, paid_on, payment_mode, notes)
                    VALUES (%s,%s,%s,%s,%s)
                """, (assigned_fee_id, amount_paid, date.today(), payment_mode, notes))

                cur.execute("SELECT SUM(amount_paid) FROM fee_payments WHERE assigned_fee_id=%s", (assigned_fee_id,))
                paid_sum = cur.fetchone()[0] or 0

                cur.execute("SELECT amount FROM assigned_fees WHERE id=%s", (assigned_fee_id,))
                total_amount = cur.fetchone()[0] or 0

                if paid_sum >= total_amount:
                    new_status = "Paid"
                elif paid_sum > 0:
                    new_status = "Partially Paid"
                else:
                    new_status = "Not Paid"

                cur.execute("UPDATE assigned_fees SET status=%s WHERE id=%s", (new_status, assigned_fee_id))
                conn.commit()
                flash("Payment recorded.", "success")

                return redirect(url_for('fees.fee_details'))

        student_id = request.args.get("student_id")
        status_f = request.args.get("status")

        sql = """
            SELECT af.id AS assigned_id, af.student_id, af.amount AS assigned_amount, af.due_date, af.status,
                   fm.id as fee_master_id, fm.amount as master_amount,
                   fh.name as head_name, ft.name as type_name
            FROM assigned_fees af
            JOIN fee_master fm ON af.fee_master_id = fm.id
            JOIN fee_heads fh ON fm.head_id = fh.id
            JOIN fee_types ft ON fm.type_id = ft.id
            WHERE 1=1
        """
        params = []

        if student_id:
            sql += " AND af.student_id = %s"; params.append(student_id)

        if status_f:
            sql += " AND af.status = %s"; params.append(status_f)

        sql += " ORDER BY af.assigned_on DESC LIMIT 500"

        cur.execute(sql, tuple(params))
        assigned = fetchall_dict(cur)

        return render_template("fee_details.html", assigned=assigned)

    finally:
        cur.close()
        conn.close()


# -----------------------
# 4) Head-wise
# -----------------------
@fees_bp.route("/head-wise", methods=["GET"])
def head_wise():
    head_id = request.args.get("head_id")
    status_f = request.args.get("status")

    conn = get_db_conn()
    cur = conn.cursor()
    try:
        sql = """
            SELECT af.id as assigned_id, af.student_id, af.amount, af.status,
                   fh.id as head_id, fh.name as head_name
            FROM assigned_fees af
            JOIN fee_master fm ON af.fee_master_id = fm.id
            JOIN fee_heads fh ON fm.head_id = fh.id
            WHERE 1=1
        """
        params = []

        if head_id:
            sql += " AND fh.id = %s"; params.append(head_id)

        if status_f:
            sql += " AND af.status = %s"; params.append(status_f)

        sql += " ORDER BY af.assigned_on DESC LIMIT 1000"

        cur.execute(sql, tuple(params))
        rows = fetchall_dict(cur)

        cur.execute("SELECT id, name FROM fee_heads ORDER BY name")
        heads = fetchall_dict(cur)

        return render_template("head_wise.html", rows=rows, heads=heads, selected_head=head_id, selected_status=status_f)
    finally:
        cur.close()
        conn.close()


# -----------------------
# 5) Fee Paid Details
# -----------------------
@fees_bp.route("/payments", methods=["GET"])
def fee_payments_list():
    student_id = request.args.get("student_id")
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    conn = get_db_conn()
    cur = conn.cursor()
    try:
        sql = """
            SELECT fp.id, fp.amount_paid, fp.paid_on, fp.payment_mode, fp.notes,
                   af.id as assigned_id, af.student_id, af.amount as assigned_amount,
                   fh.name as head_name
            FROM fee_payments fp
            JOIN assigned_fees af ON fp.assigned_fee_id = af.id
            JOIN fee_master fm ON af.fee_master_id = fm.id
            JOIN fee_heads fh ON fm.head_id = fh.id
            WHERE 1=1
        """
        params = []

        if student_id:
            sql += " AND af.student_id = %s"; params.append(student_id)
        if date_from:
            sql += " AND fp.paid_on >= %s"; params.append(date_from)
        if date_to:
            sql += " AND fp.paid_on <= %s"; params.append(date_to)

        sql += " ORDER BY fp.paid_on DESC LIMIT 200"

        cur.execute(sql, tuple(params))
        payments = fetchall_dict(cur)

        return render_template("fee_paid_details.html", payments=payments)

    finally:
        cur.close()
        conn.close()


# -----------------------
# Helper API
# -----------------------
@fees_bp.route("/api/assigned/<int:assigned_id>", methods=["GET"])
def api_get_assigned(assigned_id):
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT af.*, fm.amount as master_amount, fh.name as head_name, ft.name as type_name
            FROM assigned_fees af
            JOIN fee_master fm ON af.fee_master_id = fm.id
            JOIN fee_heads fh ON fm.head_id = fh.id
            JOIN fee_types ft ON fm.type_id = ft.id
            WHERE af.id = %s
        """, (assigned_id,))
        row = cur.fetchone()

        if not row:
            return jsonify({"error": "not found"}), 404

        cols = [c[0] for c in cur.description]
        data = dict(zip(cols, row))

        cur.execute("""
            SELECT id, amount_paid, paid_on, payment_mode, notes
            FROM fee_payments
            WHERE assigned_fee_id = %s
            ORDER BY paid_on DESC
        """, (assigned_id,))
        data["payments"] = fetchall_dict(cur)

        return jsonify(data)

    finally:
        cur.close()
        conn.close()


# -----------------------
# CLEAN URL WRAPPER ROUTES (Option B)
# -----------------------
@fees_bp.route("/structure")
def fee_structure_redirect():
    return redirect(url_for("fees.head_wise"))


@fees_bp.route("/collect")
def fee_collect_redirect():
    return redirect(url_for("fees.fee_details"))


@fees_bp.route("/receipts")
def fee_receipts_redirect():
    return redirect(url_for("fees.fee_payments_list"))


@fees_bp.route("/pending")
def fee_pending_redirect():
    return redirect(url_for("fees.fee_details", status="Not Paid"))


@fees_bp.route("/defaulters")
def fee_defaulters_redirect():
    return redirect(url_for("fees.head_wise", status="Not Paid"))


@fees_bp.route("/reports")
def fee_reports_redirect():
    return redirect(url_for("fees.fee_payments_list"))
