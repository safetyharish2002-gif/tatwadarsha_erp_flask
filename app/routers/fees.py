# path: app/routers/fees.py
"""
"""
import json
"""


Final & Corrected Fees Module — Tatwadarsha ERP
- Clean routing (NO duplicate /assign route)
- Fully MySQL compatible
- Works with main.py's blueprint registration
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, current_app
from app.routers.master import get_db
import uuid
from datetime import datetime
import os
import json
from werkzeug.utils import secure_filename

# Uploads folder - adjust if you want different path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # project root approx
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'payments')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx'}

fees_bp = Blueprint("fees", __name__, template_folder="../../templates/fees", url_prefix="/fees")

# -----------------------
# Helpers
# -----------------------
def _is_logged_in():
    return session.get("logged_in", False)

def gen_uuid():
    return str(uuid.uuid4())

def fetchall_dict(cur):
    cols = [c[0] for c in cur.description] if cur.description else []
    rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]

def fetchone_dict(cur):
    row = cur.fetchone()
    if not row:
        return None
    cols = [c[0] for c in cur.description]
    return dict(zip(cols, row))

def make_receipt_no(prefix="REC"):
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suf = uuid.uuid4().hex[:4].upper()
    return f"{prefix}{ts[-10:]}{suf}"

# -----------------------
# Pages
# -----------------------
@fees_bp.route("/master")
def page_master():
    if not _is_logged_in():
        return redirect(url_for("login"))
    return render_template("fees/master.html", title="Fees Master")

@fees_bp.route("/assign")
def page_assign():
    """Only page render (GET only)"""
    if not _is_logged_in():
        return redirect(url_for("login"))

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()

        # Fee heads
        cur.execute("SELECT id, name, amount FROM fee_heads ORDER BY name")
        heads = fetchall_dict(cur)

        # Optional fee structures
        try:
            cur.execute("""
                SELECT id, course, session, branch, department, batch, head_id, amount
                FROM fee_structures ORDER BY created_at DESC
            """)
            structures = fetchall_dict(cur)
        except Exception:
            structures = []

        return render_template("fees/assign.html", title="Fees Assign", heads=heads, structures=structures)

    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/collect")
def page_collect():
    if not _is_logged_in():
        return redirect(url_for("login"))
    return render_template("fees/collect.html", title="Collect Fees")

@fees_bp.route("/receipts")
def page_receipts():
    if not _is_logged_in():
        return redirect(url_for("login"))
    return render_template("fees/receipts.html", title="Fee Receipts")

@fees_bp.route("/reports")
def page_reports():
    if not _is_logged_in():
        return redirect(url_for("login"))
    return render_template("fees/reports.html", title="Fees Reports")

# -----------------------
# Fee Heads APIs
# -----------------------
@fees_bp.route("/api/heads", methods=["GET"])
def api_heads_list():
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            SELECT id, name, amount, start_date, end_date, due_date, status, created_at
            FROM fee_heads ORDER BY created_at DESC
        """)
        items = fetchall_dict(cur)
        return jsonify({"success": True, "items": items})

    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/api/heads", methods=["POST"])
def api_heads_add():
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    amount = data.get("amount")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    due_date = data.get("due_date")
    status = data.get("status") or "active"

    if not name:
        return jsonify({"success": False, "message": "Name required"}), 400
    if not amount:
        return jsonify({"success": False, "message": "Amount required"}), 400

    try:
        amount_val = float(amount)
    except:
        return jsonify({"success": False, "message": "Invalid amount"}), 400

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        hid = gen_uuid()
        cur.execute("""
            INSERT INTO fee_heads (id, name, amount, start_date, end_date, due_date, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (hid, name, amount_val, start_date, end_date, due_date, status))
        db.commit()
        return jsonify({"success": True, "id": hid})

    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/api/heads/<head_id>", methods=["PUT"])
def api_heads_update(head_id):
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    amount = data.get("amount")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    due_date = data.get("due_date")
    status = data.get("status") or "active"

    if not name or amount is None:
        return jsonify({"success": False, "message": "Name & amount required"}), 400

    try:
        amount_val = float(amount)
    except:
        return jsonify({"success": False, "message": "Invalid amount"}), 400

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            UPDATE fee_heads 
            SET name=%s, amount=%s, start_date=%s, end_date=%s, due_date=%s, status=%s
            WHERE id=%s
        """, (name, amount_val, start_date, end_date, due_date, status, head_id))
        db.commit()
        return jsonify({"success": True})

    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/api/heads/<head_id>", methods=["DELETE"])
def api_heads_delete(head_id):
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM fee_heads WHERE id=%s", (head_id,))
        db.commit()
        return jsonify({"success": True})

    finally:
        if cur: cur.close()
        if db: db.close()

# -----------------------
# Assign Fees (NO ROUTE CONFLICT)
# -----------------------
@fees_bp.route("/assign/save", methods=["POST"])
def assign_save():
    """Handles both single & bulk assignment."""
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    action = request.form.get("action")
    db = None
    cur = None

    try:
        db = get_db()
        cur = db.cursor()

        # SINGLE assignment
        if action == "assign_single":
            student_id = request.form.get("student_id")
            head_id = request.form.get("head_id")
            amount = request.form.get("amount")
            due_date = request.form.get("due_date")

            if not student_id or not head_id or not amount:
                return jsonify({"success": False, "message": "Missing fields"}), 400

            amount_val = float(amount)
            aid = gen_uuid()

            cur.execute("""
                INSERT INTO assigned_fees (id, student_id, head_id, amount, due_date, status, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (aid, student_id, head_id, amount_val, due_date, "Not Paid", datetime.utcnow()))

            db.commit()
            return jsonify({"success": True, "id": aid})

        # BULK assignment
        if action == "assign_bulk":
            head_id = request.form.get("head_id")
            amount = request.form.get("amount")
            student_ids = request.form.get("student_ids")
            due_date = request.form.get("due_date")

            if not head_id or not amount or not student_ids:
                return jsonify({"success": False, "message": "Missing fields"}), 400

            amount_val = float(amount)
            ids = student_ids.split(",")

            for sid in ids:
                sid = sid.strip()
                if not sid:
                    continue
                aid = gen_uuid()
                cur.execute("""
                    INSERT INTO assigned_fees (id, student_id, head_id, amount, due_date, status, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (aid, sid, head_id, amount_val, due_date, "Not Paid", datetime.utcnow()))

            db.commit()
            return jsonify({"success": True})

        return jsonify({"success": False, "message": "Unknown action"}), 400

    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/collect/pay", methods=["POST"])
def collect_payment():
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    # Accept both JSON body and multipart/form-data (FormData). Prefer request.form/request.files if available.
    data = {}
    if request.content_type and request.content_type.startswith('multipart/'):
        # multipart/form-data -> use request.form and request.files
        data.update(request.form.to_dict())
        # If client sent a JSON 'meta' string, keep it as dict
        if data.get('meta') and isinstance(data['meta'], str):
            try:
                data['meta'] = json.loads(data['meta'])
            except:
                data['meta'] = {}
        # attach files
        file = request.files.get('file')
    else:
        # JSON body
        try:
            data = request.get_json(silent=True) or {}
        except:
            data = request.form.to_dict()
        file = None

    # support both payload shapes:
    # - JSON shape with payments array (legacy)
    # - FormData shape with assigned_fee_id directly
    payments = data.get('payments')
    if payments and isinstance(payments, list) and len(payments) > 0:
        p = payments[0]
        assigned_id = p.get('assigned_id') or data.get('assigned_fee_id')
        head_id = p.get('head_id')
        amount = p.get('amount')
        mode_name = p.get('mode') or p.get('payment_mode_id') or p.get('payment_mode_name')
        payment_date = p.get('payment_date') or p.get('paid_on') or data.get('paid_on')
        payment_time = p.get('payment_time') or ''
        remark = p.get('remark') or ''
        meta = p.get('meta') or {}
    else:
        assigned_id = data.get('assigned_fee_id') or data.get('assigned_id')
        amount = data.get('amount')
        mode_name = data.get('payment_mode_id') or data.get('mode') or data.get('payment_mode_name')
        payment_date = data.get('paid_on') or data.get('payment_date')
        payment_time = data.get('payment_time') or ''
        remark = data.get('remark') or ''
        meta = data.get('meta') or {}

    student_id = data.get('student_id') or data.get('student')

    if not assigned_id or not amount or not mode_name or not student_id:
        return jsonify({"success": False, "message": "Missing payment fields"}), 400

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()

        # Determine payment_mode_id
        # If client sent an id, try to find by id, otherwise try by name
        payment_mode_id = None
        # if mode_name looks like uuid/id and exists in DB
        cur.execute("SELECT id, name FROM payment_modes WHERE id=%s LIMIT 1", (mode_name,))
        row = cur.fetchone()
        if row:
            payment_mode_id = row[0]
        else:
            cur.execute("SELECT id, name FROM payment_modes WHERE name=%s LIMIT 1", (mode_name,))
            row = cur.fetchone()
            if row:
                payment_mode_id = row[0]

        if not payment_mode_id:
            return jsonify({"success": False, "message": "Payment mode not found"}), 400

        # Handle file saving (if multipart upload)
        file_path_db = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXT:
                return jsonify({"success": False, "message": "File type not allowed"}), 400
            # ensure unique filename
            safe_name = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(UPLOAD_FOLDER, safe_name)
            file.save(save_path)
            # store relative path or absolute, as you prefer
            # I'll store relative path from project root (uploads/payments/...)
            rel_path = os.path.relpath(save_path, BASE_DIR)
            file_path_db = rel_path.replace("\\", "/")

        # Insert payment
        payid = gen_uuid()
        paid_on = f"{payment_date} {payment_time}".strip() if payment_date else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            INSERT INTO fee_payments 
                (id, assigned_fee_id, student_id, amount, payment_mode_id,
                 reference_no, meta_json, file_path, paid_on, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            payid,
            assigned_id,
            student_id,
            float(amount),
            payment_mode_id,
            meta.get("reference_no") or meta.get("utr") or '',
            json.dumps(meta) if meta else None,
            file_path_db,
            paid_on,
            datetime.utcnow()
        ))

        # Recalculate status and update assigned_fees
        cur.execute("SELECT COALESCE(SUM(amount),0) FROM fee_payments WHERE assigned_fee_id=%s", (assigned_id,))
        paid_sum = cur.fetchone()[0] or 0
        cur.execute("SELECT amount FROM assigned_fees WHERE id=%s", (assigned_id,))
        total_amount_row = cur.fetchone()
        total_amount = total_amount_row[0] if total_amount_row else 0

        if paid_sum >= total_amount:
            new_status = "Paid"
        elif paid_sum > 0:
            new_status = "Partially Paid"
        else:
            new_status = "Not Paid"

        cur.execute("UPDATE assigned_fees SET status=%s WHERE id=%s", (new_status, assigned_id))

        # Create receipt
        receipt_id = gen_uuid()
        receipt_no = make_receipt_no()
        cur.execute("""
            INSERT INTO fee_receipts (id, payment_id, receipt_no, created_at)
            VALUES (%s,%s,%s,%s)
        """, (receipt_id, payid, receipt_no, datetime.utcnow()))

        db.commit()

        # For developer convenience: return saved file path (if any) as file_url
        file_url = file_path_db if file_path_db else None

        return jsonify({
            "success": True,
            "payment_id": payid,
            "receipt_id": receipt_id,
            "receipt_no": receipt_no,
            "file_url": file_url
        })
    except Exception as e:
        print("Error in collect_payment:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if cur: cur.close()
        if db: db.close()

# -----------------------
# Receipt List
# -----------------------
@fees_bp.route("/api/receipts", methods=["GET"])
def api_receipts_list():
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    student_id = request.args.get("student_id")
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()

        q = """
            SELECT r.id as receipt_id, r.receipt_no, r.created_at as receipt_at,
                   fp.id as payment_id, fp.amount as paid_amount, fp.paid_on,
                   af.student_id, af.head_id, fh.name as head_name,
                   pm.name as payment_mode
            FROM fee_receipts r
            JOIN fee_payments fp ON r.payment_id = fp.id
            JOIN assigned_fees af ON fp.assigned_fee_id = af.id
            LEFT JOIN fee_heads fh ON af.head_id = fh.id
            LEFT JOIN payment_modes pm ON fp.payment_mode_id = pm.id
            WHERE 1=1
        """

        params = []

        if student_id:
            q += " AND af.student_id=%s"; params.append(student_id)
        if date_from:
            q += " AND r.created_at >= %s"; params.append(date_from)
        if date_to:
            q += " AND r.created_at <= %s"; params.append(date_to)

        q += " ORDER BY r.created_at DESC LIMIT 500"

        cur.execute(q, tuple(params))
        return jsonify({"success": True, "items": fetchall_dict(cur)})

    finally:
        if cur: cur.close()
        if db: db.close()

# -----------------------
# Payments Detail List
# -----------------------
@fees_bp.route("/api/payments", methods=["GET"])
def api_payments_list():
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    student_id = request.args.get("student_id")
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()

        q = """
            SELECT fp.id, fp.amount, fp.paid_on, fp.reference_no,
                   pm.name as payment_mode,
                   af.id as assigned_id, af.student_id,
                   fh.name as head_name
            FROM fee_payments fp
            JOIN assigned_fees af ON fp.assigned_fee_id = af.id
            LEFT JOIN fee_heads fh ON af.head_id = fh.id
            LEFT JOIN payment_modes pm ON fp.payment_mode_id = pm.id
            WHERE 1=1
        """

        params = []

        if student_id:
            q += " AND af.student_id=%s"; params.append(student_id)
        if date_from:
            q += " AND fp.paid_on >= %s"; params.append(date_from)
        if date_to:
            q += " AND fp.paid_on <= %s"; params.append(date_to)

        q += " ORDER BY fp.paid_on DESC LIMIT 500"

        cur.execute(q, tuple(params))
        return jsonify({"success": True, "items": fetchall_dict(cur)})

    finally:
        if cur: cur.close()
        if db: db.close()

# -----------------------
# Reports Summary
# -----------------------
@fees_bp.route("/api/reports/summary", methods=["GET"])
def api_reports_summary():
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    head_id = request.args.get("head_id")
    payment_mode_id = request.args.get("payment_mode_id")
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    db = None
    cur = None

    try:
        db = get_db()
        cur = db.cursor()

        q = """
            SELECT fh.id as head_id, fh.name as head_name,
                   pm.id as payment_mode_id, pm.name as payment_mode,
                   SUM(fp.amount) as total_collected,
                   COUNT(fp.id) as payments_count
            FROM fee_payments fp
            JOIN assigned_fees af ON fp.assigned_fee_id = af.id
            LEFT JOIN fee_heads fh ON af.head_id = fh.id
            LEFT JOIN payment_modes pm ON fp.payment_mode_id = pm.id
            WHERE 1=1
        """

        params = []

        if head_id:
            q += " AND fh.id=%s"; params.append(head_id)
        if payment_mode_id:
            q += " AND pm.id=%s"; params.append(payment_mode_id)
        if date_from:
            q += " AND fp.paid_on >= %s"; params.append(date_from)
        if date_to:
            q += " AND fp.paid_on <= %s"; params.append(date_to)

        q += " GROUP BY fh.id, pm.id ORDER BY fh.name, pm.name"

        cur.execute(q, tuple(params))
        return jsonify({"success": True, "rows": fetchall_dict(cur)})

    finally:
        if cur: cur.close()
        if db: db.close()
@fees_bp.route("/receipt/view/<receipt_id>")
def view_receipt(receipt_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()

        cur.execute("""
            SELECT r.receipt_no, r.created_at,
                   fp.amount, fp.paid_on, fp.reference_no,
                   af.student_id,
                   fh.name AS head_name,
                   pm.name AS payment_mode
            FROM fee_receipts r
            JOIN fee_payments fp ON r.payment_id = fp.id
            JOIN assigned_fees af ON fp.assigned_fee_id = af.id
            LEFT JOIN fee_heads fh ON af.head_id = fh.id
            LEFT JOIN payment_modes pm ON fp.payment_mode_id = pm.id
            WHERE r.id = %s
        """, (receipt_id,))
        data = cur.fetchone()

        if not data:
            return "Receipt not found", 404

        cols = [c[0] for c in cur.description]
        receipt = dict(zip(cols, data))

        return render_template("fees/receipt_print.html", receipt=receipt)

    finally:
        if cur: cur.close()
        if db: db.close()
# -----------------------
# Fee Structures (CRUD) + assign-from-structure
# -----------------------
@fees_bp.route("/structure")
def page_structure():
    if not _is_logged_in():
        return redirect(url_for("login"))
    return render_template("fees/structure.html", title="Fee Structure")

@fees_bp.route("/api/structures", methods=["GET"])
def api_structures_list():
    if not _is_logged_in():
        return jsonify({"success": False}), 401
    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT id, course, session, branch, department, batch, head_id, amount, created_at FROM fee_structures ORDER BY created_at DESC")
        return jsonify({"success": True, "items": fetchall_dict(cur)})
    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/api/structures", methods=["POST"])
def api_structures_add():
    if not _is_logged_in():
        return jsonify({"success": False}), 401
    data = request.get_json(silent=True) or request.form
    course = (data.get("course") or "").strip()
    session_v = (data.get("session") or "").strip()
    branch = (data.get("branch") or "").strip()
    department = (data.get("department") or "").strip()
    batch = (data.get("batch") or "").strip()
    head_id = (data.get("head_id") or "").strip()
    amount = data.get("amount")
    if not head_id or not amount:
        return jsonify({"success": False, "message": "head_id and amount required"}), 400
    try:
        amount_val = float(amount)
    except:
        return jsonify({"success": False, "message": "Invalid amount"}), 400
    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        sid = gen_uuid()
        cur.execute("""
            INSERT INTO fee_structures (id, course, session, branch, department, batch, head_id, amount, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (sid, course, session_v, branch, department, batch, head_id, amount_val, datetime.utcnow()))
        db.commit()
        return jsonify({"success": True, "id": sid})
    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/api/structures/<sid>", methods=["PUT"])
def api_structures_update(sid):
    if not _is_logged_in():
        return jsonify({"success": False}), 401
    data = request.get_json(silent=True) or request.form
    course = (data.get("course") or "").strip()
    session_v = (data.get("session") or "").strip()
    branch = (data.get("branch") or "").strip()
    department = (data.get("department") or "").strip()
    batch = (data.get("batch") or "").strip()
    head_id = (data.get("head_id") or "").strip()
    amount = data.get("amount")
    if not head_id or amount is None:
        return jsonify({"success": False, "message": "head_id and amount required"}), 400
    try:
        amount_val = float(amount)
    except:
        return jsonify({"success": False, "message": "Invalid amount"}), 400
    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            UPDATE fee_structures SET course=%s, session=%s, branch=%s, department=%s, batch=%s, head_id=%s, amount=%s
            WHERE id=%s
        """, (course, session_v, branch, department, batch, head_id, amount_val, sid))
        db.commit()
        return jsonify({"success": True})
    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/api/structures/<sid>", methods=["DELETE"])
def api_structures_delete(sid):
    if not _is_logged_in():
        return jsonify({"success": False}), 401
    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM fee_structures WHERE id=%s", (sid,))
        db.commit()
        return jsonify({"success": True})
    finally:
        if cur: cur.close()
        if db: db.close()

# Assign students from fee_structure (bulk apply a structure to matching students)
@fees_bp.route("/assign/from-structure", methods=["POST"])
def assign_from_structure():
    """
    POST form fields:
      structure_id - id of fee_structures
      filter_student_ids (optional) - comma separated to limit
    This assigns assigned_fees for all students matching the structure fields (course/session/branch/department/batch).
    """
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    structure_id = request.form.get("structure_id")
    filter_ids = request.form.get("filter_student_ids")  # optional

    if not structure_id:
        return jsonify({"success": False, "message": "structure_id required"}), 400

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        # fetch structure
        cur.execute("SELECT course, session, branch, department, batch, head_id, amount FROM fee_structures WHERE id=%s", (structure_id,))
        srow = cur.fetchone()
        if not srow:
            return jsonify({"success": False, "message": "Structure not found"}), 404
        course, session_v, branch, department, batch, head_id, amount = srow

        # build student filter
        where = []
        params = []
        if course:
            where.append("course=%s"); params.append(course)
        if session_v:
            where.append("session=%s"); params.append(session_v)
        if branch:
            where.append("branch=%s"); params.append(branch)
        if department:
            where.append("department=%s"); params.append(department)
        if batch:
            where.append("batch=%s"); params.append(batch)
        if filter_ids:
            ids = [i.strip() for i in filter_ids.split(",") if i.strip()]
            if ids:
                where.append("id IN (" + ",".join(["%s"]*len(ids)) + ")")
                params.extend(ids)

        condition = ("WHERE " + " AND ".join(where)) if where else ""
        # select students
        cur.execute(f"SELECT id FROM students {condition}", tuple(params))
        studs = [r[0] for r in cur.fetchall()]

        count = 0
        for sid in studs:
            aid = gen_uuid()
            cur.execute("""
                INSERT INTO assigned_fees (id, student_id, head_id, amount, due_date, status, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (aid, sid, head_id, amount, None, "Not Paid", datetime.utcnow()))
            count += 1

        db.commit()
        return jsonify({"success": True, "assigned": count})

    finally:
        if cur: cur.close()
        if db: db.close()


# -----------------------
# Pending Fees & Defaulter (basic)
# -----------------------
@fees_bp.route("/pending")
def page_pending():
    if not _is_logged_in():
        return redirect(url_for("login"))
    return render_template("fees/pending.html", title="Pending Fees")

@fees_bp.route("/api/pending", methods=["GET"])
def api_pending_list():
    """
    Query params:
      student_id, course, batch, overdue_only = 1
    Returns assigned_fees rows with calculated paid_sum and balance.
    """
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    student_id = request.args.get("student_id")
    course = request.args.get("course")
    batch = request.args.get("batch")
    overdue_only = request.args.get("overdue_only")  # "1" for yes

    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()

        q = """
            SELECT af.id as assigned_id, af.student_id, af.head_id, af.amount as due_amount,
                   af.due_date, af.status, s.name as student_name, s.course, s.batch
            FROM assigned_fees af
            LEFT JOIN students s ON af.student_id = s.id
            WHERE 1=1
        """
        params = []
        if student_id:
            q += " AND af.student_id=%s"; params.append(student_id)
        if course:
            q += " AND s.course=%s"; params.append(course)
        if batch:
            q += " AND s.batch=%s"; params.append(batch)

        cur.execute(q, tuple(params))
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
        result = []
        for row in rows:
            rd = dict(zip(cols, row))
            aid = rd["assigned_id"]
            # calculate paid sum
            cur.execute("SELECT COALESCE(SUM(amount),0) FROM fee_payments WHERE assigned_fee_id=%s", (aid,))
            paid = cur.fetchone()[0] or 0
            balance = (rd["due_amount"] or 0) - paid
            rd["paid_sum"] = float(paid)
            rd["balance"] = float(balance)
            # mark overdue if due_date < today and balance>0
            overdue = False
            if rd.get("due_date"):
                try:
                    due_dt = rd.get("due_date")
                    # due_dt may be date/datetime - compare strings safely by converting
                    if isinstance(due_dt, (str,)):
                        from datetime import datetime as _dt
                        due_obj = _dt.strptime(due_dt.split()[0], "%Y-%m-%d")
                    else:
                        due_obj = due_dt
                    if due_obj.date() < datetime.utcnow().date() and balance > 0:
                        overdue = True
                except Exception:
                    overdue = False
            rd["overdue"] = overdue
            # if overdue_only requested skip non-overdue
            if overdue_only and overdue_only == "1" and not overdue:
                continue
            result.append(rd)

        return jsonify({"success": True, "items": result})

    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/api/assigned", methods=["GET"])
def api_assigned_student():
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    student_id = request.args.get("student_id")
    if not student_id:
        return jsonify({"success": False, "message": "student_id required"}), 400

    db = None
    cur = None

    try:
        db = get_db()
        cur = db.cursor()

        # Fetch assigned fees with department
        cur.execute("""
            SELECT 
                af.id AS assigned_id,
                af.student_id,
                af.head_id,
                af.amount AS assigned_amount,
                af.due_date,
                af.status AS assigned_status,
                fh.name AS head_name,

                -- Student academic for grouping
                s.department,

                -- Calculate paid amount
                (SELECT COALESCE(SUM(fp.amount),0) 
                 FROM fee_payments fp 
                 WHERE fp.assigned_fee_id = af.id) AS paid_amount

            FROM assigned_fees af
            LEFT JOIN fee_heads fh ON fh.id = af.head_id
            LEFT JOIN students s ON s.id = af.student_id
            WHERE af.student_id = %s
            ORDER BY s.department, fh.name
        """, (student_id,))

        rows = fetchall_dict(cur)

        # Group by department
        groups = {}
        for r in rows:
            dept = r.get("department") or "Unknown"
            r["balance"] = float(r["assigned_amount"]) - float(r["paid_amount"])

            if dept not in groups:
                groups[dept] = []

            groups[dept].append(r)

        # Convert to array
        final_groups = []
        for dept, items in groups.items():
            final_groups.append({
                "department": dept,
                "items": items
            })

        return jsonify({
            "success": True,
            "student": student_id,
            "groups": final_groups
        })

    finally:
        if cur: cur.close()
        if db: db.close()

@fees_bp.route("/api/payment_modes", methods=["GET"])
def api_pm_list():
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, name, fields, created_at FROM payment_modes ORDER BY created_at DESC")
    items = fetchall_dict(cur)
    cur.close()
    db.close()
    return jsonify({"success": True, "items": items})
@fees_bp.route("/api/payment_modes", methods=["POST"])
def api_pm_add():
    if not _is_logged_in():
        return jsonify({"success": False}), 401

    name = request.form.get("name", "").strip()
    fields_raw = request.form.get("fields") or "[]"

    try:
        fields = json.loads(fields_raw)
    except:
        fields = []

    if not name:
        return jsonify({"success": False, "message": "Name required"}), 400

    # File upload handling
    file = request.files.get("file")
    file_path = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        stored = f"{uuid.uuid4().hex}_{filename}"
        save_path = os.path.join(UPLOAD_FOLDER, stored)
        file.save(save_path)

        # Store relative path
        file_path = os.path.relpath(save_path, BASE_DIR).replace("\\", "/")

    db = get_db()
    cur = db.cursor()
    pid = gen_uuid()

    cur.execute("""
        INSERT INTO payment_modes (id, name, fields, file_path, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (pid, name, json.dumps(fields), file_path, datetime.utcnow()))
    
    db.commit()
    cur.close()
    db.close()

    return jsonify({"success": True, "id": pid})
