# app/routers/fees.py
"""
Fees blueprint for Tatwadarsha ERP

Screenshot reference (uploaded): /mnt/data/b7541c6d-77fa-48f2-9899-84253f101ef5.png

SQL table suggestions (run these once in your MySQL database if you don't have similar tables):
----------------------------------------------------------------
CREATE TABLE fee_heads (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fee_types (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL -- e.g. 'Full', 'Partial'
);

CREATE TABLE fee_master (
  id INT AUTO_INCREMENT PRIMARY KEY,
  head_id INT NOT NULL,
  type_id INT NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  start_date DATE,
  end_date DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (head_id) REFERENCES fee_heads(id),
  FOREIGN KEY (type_id) REFERENCES fee_types(id)
);

CREATE TABLE assigned_fees (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id VARCHAR(100) NOT NULL, -- matches your students table's student id
  fee_master_id INT NOT NULL,
  assigned_on DATE DEFAULT CURRENT_DATE,
  due_date DATE,
  amount DECIMAL(10,2) NOT NULL,
  status ENUM('Not Paid','Partially Paid','Paid') DEFAULT 'Not Paid',
  FOREIGN KEY (fee_master_id) REFERENCES fee_master(id)
);

CREATE TABLE fee_payments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  assigned_fee_id INT NOT NULL,
  amount_paid DECIMAL(10,2) NOT NULL,
  paid_on DATE DEFAULT CURRENT_DATE,
  payment_mode VARCHAR(100),
  notes TEXT,
  FOREIGN KEY (assigned_fee_id) REFERENCES assigned_fees(id)
);
----------------------------------------------------------------

Usage notes:
- app.config['MYSQL'] should be a dict with keys: host, user, password, database, pool_name(optional), pool_size(optional)
  Example:
    app.config['MYSQL'] = {
      "host": "localhost",
      "user": "youruser",
      "password": "yourpass",
      "database": "erp_db",
      "pool_name": "erp_pool",
      "pool_size": 5
    }

- Register blueprint in your app factory:
    from app.routers.fees import fees_bp
    app.register_blueprint(fees_bp, url_prefix='/fees')

- Templates:
    templates/fee/fee_master.html
    templates/fee/assign_fee.html
    templates/fee/fee_details.html
    templates/fee/head_wise.html
    templates/fee/fee_paid_details.html
    templates/fees.html   <-- main container page (optional)

- This file tries to be defensive and uses parameterized queries.

"""

from flask import Blueprint, render_template, request, current_app, jsonify, redirect, url_for, flash
import mysql.connector
from mysql.connector import pooling
from datetime import datetime, date

fees_bp = Blueprint("fees", __name__, template_folder="../templates/fee")

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
# Main page (single page that can include submenus)
# -----------------------
@fees_bp.route("/", methods=["GET"])
def index():
    # main landing page - could show quick stats or redirect to fee master page
    return render_template("fees.html")


# -----------------------
# 1) Fee Master: manage fee heads, fee types, fee_master entries
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

        # GET -> show lists
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
# AJAX endpoints for frontend convenience
# -----------------------
@fees_bp.route("/api/fee_masters", methods=["GET"])
def api_fee_masters():
    """Return fee_master list as JSON (with head/type names). Optionally filter by head_id."""
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
    """
    Returns students for filter/autocomplete.
    Expects 'q' (search term) and optionally other filters (session/course/branch/batch etc).
    Assumes students table exists with columns: student_id, name, session, course, branch, batch
    """
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
        students = fetchall_dict(cur)
        return jsonify(students)
    finally:
        cur.close()
        conn.close()


# -----------------------
# 2) Assign Fee
#     - filter students, choose fee_head (or fee_master), auto-fill payment type/amount/dates
#     - allocate to student(s)
# -----------------------
@fees_bp.route("/assign", methods=["GET", "POST"])
def assign_fee():
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        # GET: render form with filters
        if request.method == "GET":
            # we need all fee heads and fee masters for selection
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

        # POST: assign
        action = request.form.get("action")
        if action == "assign_single":
            student_id = request.form.get("student_id")
            fee_master_id = request.form.get("fee_master_id")
            # fetch amount and end_date/due info from fee_master
            cur.execute("SELECT amount, end_date FROM fee_master WHERE id=%s", (fee_master_id,))
            master = cur.fetchone()
            if master:
                amount, end_date = master
                due_date = end_date or None
                cur.execute("INSERT INTO assigned_fees (student_id, fee_master_id, due_date, amount) VALUES (%s,%s,%s,%s)",
                            (student_id, fee_master_id, due_date, amount))
                conn.commit()
                flash("Fee assigned to student.", "success")
            else:
                flash("Fee master not found.", "danger")
            return redirect(url_for('fees.assign_fee'))

        if action == "assign_bulk":
            # bulk assignment to filtered students (basically student_ids comma-separated or via filters)
            fee_master_id = request.form.get("fee_master_id")
            student_ids = request.form.get("student_ids")  # expect CSV of student IDs from frontend
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
                    cur.execute("INSERT INTO assigned_fees (student_id, fee_master_id, due_date, amount) VALUES (%s,%s,%s,%s)",
                                (sid, fee_master_id, due_date, amount))
                conn.commit()
                flash(f"Assigned fee to {len(ids)} students.", "success")
            return redirect(url_for('fees.assign_fee'))

    finally:
        cur.close()
        conn.close()


# -----------------------
# 3) Fee Details - list assigned fees, filters, and add payment
# -----------------------
@fees_bp.route("/details", methods=["GET", "POST"])
def fee_details():
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        # POST: add payment for an assigned_fee
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add_payment":
                assigned_fee_id = request.form.get("assigned_fee_id")
                amount_paid = float(request.form.get("amount_paid") or 0)
                payment_mode = request.form.get("payment_mode")
                notes = request.form.get("notes")
                # insert payment
                cur.execute("INSERT INTO fee_payments (assigned_fee_id, amount_paid, paid_on, payment_mode, notes) VALUES (%s,%s,%s,%s,%s)",
                            (assigned_fee_id, amount_paid, date.today(), payment_mode, notes))
                # update assigned fee status
                # compute sum paid for assigned_fee
                cur.execute("SELECT SUM(amount_paid) FROM fee_payments WHERE assigned_fee_id=%s", (assigned_fee_id,))
                paid_sum = cur.fetchone()[0] or 0
                # get assigned_fees.amount
                cur.execute("SELECT amount FROM assigned_fees WHERE id=%s", (assigned_fee_id,))
                total_amount = cur.fetchone()[0] or 0
                new_status = "Not Paid"
                if paid_sum >= total_amount:
                    new_status = "Paid"
                elif 0 < paid_sum < total_amount:
                    new_status = "Partially Paid"
                cur.execute("UPDATE assigned_fees SET status=%s WHERE id=%s", (new_status, assigned_fee_id))
                conn.commit()
                flash("Payment recorded.", "success")
                return redirect(url_for('fees.fee_details'))

        # GET: list assigned fees with filters
        student_id = request.args.get("student_id")
        session_f = request.args.get("session")
        course_f = request.args.get("course")
        status_f = request.args.get("status")  # Paid/Not Paid/Partially Paid

        sql = """
            SELECT af.id AS assigned_id, af.student_id, af.amount AS assigned_amount, af.due_date, af.status,
                   fm.id as fee_master_id, fm.amount as master_amount, fh.name as head_name, ft.name as type_name
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

        # For payment forms, fetch recent payments if needed
        return render_template("fee_details.html", assigned=assigned)

    finally:
        cur.close()
        conn.close()


# -----------------------
# 4) Head-wise Fee Details (filter students by head & payment status)
# -----------------------
@fees_bp.route("/head-wise", methods=["GET"])
def head_wise():
    head_id = request.args.get("head_id")
    status_f = request.args.get("status")  # Paid / Not Paid / Partially Paid
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        sql = """
            SELECT af.id as assigned_id, af.student_id, af.amount, af.status, fh.id as head_id, fh.name as head_name
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
        # fetch all heads for filter dropdown
        cur.execute("SELECT id, name FROM fee_heads ORDER BY name")
        heads = fetchall_dict(cur)
        return render_template("head_wise.html", rows=rows, heads=heads, selected_head=head_id, selected_status=status_f)
    finally:
        cur.close()
        conn.close()


# -----------------------
# 5) Fee Paid Details - date-wise and student filters for payment records
# -----------------------
@fees_bp.route("/payments", methods=["GET"])
def fee_payments_list():
    student_id = request.args.get("student_id")
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    session_f = request.args.get("session")
    course_f = request.args.get("course")

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
        # If students table has session/course filters, those can be added here via a JOIN
        sql += " ORDER BY fp.paid_on DESC LIMIT 200"
        cur.execute(sql, tuple(params))
        payments = fetchall_dict(cur)
        return render_template("fee_paid_details.html", payments=payments)
    finally:
        cur.close()
        conn.close()


# -----------------------
# Small helper route: get assigned fee detail by id (could be used by AJAX)
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
        # include payments
        cur.execute("SELECT id, amount_paid, paid_on, payment_mode, notes FROM fee_payments WHERE assigned_fee_id = %s ORDER BY paid_on DESC", (assigned_id,))
        payments = fetchall_dict(cur)
        data["payments"] = payments
        return jsonify(data)
    finally:
        cur.close()
        conn.close()
