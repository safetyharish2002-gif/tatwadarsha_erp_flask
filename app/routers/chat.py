# path: app/routers/chat.py

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    send_from_directory,
    jsonify
)
from app.routers.master import get_db
import os
import uuid
from werkzeug.utils import secure_filename
from functools import wraps

chat_bp = Blueprint("chat", __name__)

# ✅ ADD THIS LINE (FIXES ALL ERRORS)
CHAT_UPLOAD_DIR = "chat_uploads"

# ---------- Helpers ----------

def chat_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "chat_user_id" not in session:
            return redirect(url_for("chat.chat_login"))
        return f(*args, **kwargs)
    return decorated_function


def is_admin():
    return session.get("chat_role") == "admin"


def ensure_upload_folder():
    upload_folder = os.path.join(
        current_app.root_path, "static", "chat_uploads"
    )
    os.makedirs(upload_folder, exist_ok=True)
    return upload_folder


# ✅ ADD THIS (CRITICAL FOR DB SAFETY)
def get_db_safe():
    db = get_db()
    if not db:
        return None
    return db


# ---------- Login / Logout ----------

@chat_bp.route("/chat/login", methods=["GET", "POST"])
def chat_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM chat_users WHERE username=%s AND password=%s AND active=1",
            (username, password)
        )
        user = cursor.fetchone()

        if user:
            session["chat_user_id"] = user["user_id"]
            session["chat_username"] = user["username"]
            session["chat_full_name"] = user.get("full_name") or user["username"]
            session["chat_role"] = user["role"]

            return redirect(url_for("chat.chat_room"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("chat_login.html")


@chat_bp.route("/chat/logout")
def chat_logout():
    session.pop("chat_user_id", None)
    session.pop("chat_username", None)
    session.pop("chat_full_name", None)
    session.pop("chat_role", None)
    return redirect(url_for("chat.chat_login"))


# ---------- Chat Room (List + Selected Request) ----------

@chat_bp.route("/chat/room")
@chat_login_required
def chat_room():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    user_id = session["chat_user_id"]
    role = session["chat_role"]

    # All requests list (for left side)
    if role == "admin":
        cursor.execute("""
            SELECT fr.*, 
                   (SELECT COUNT(*) FROM finance_chat fc WHERE fc.request_id = fr.id) AS msg_count
            FROM finance_requests fr
            ORDER BY fr.created_at DESC
        """)
    else:
        cursor.execute("""
            SELECT fr.*, 
                   (SELECT COUNT(*) FROM finance_chat fc WHERE fc.request_id = fr.id) AS msg_count
            FROM finance_requests fr
            WHERE fr.requester_id = %s
            ORDER BY fr.created_at DESC
        """, (user_id,))
    requests_list = cursor.fetchall()

    # Current selected request
    req_id = request.args.get("request_id", type=int)
    selected_request = None
    chat_messages = []

    if req_id:
        cursor.execute("SELECT * FROM finance_requests WHERE id=%s", (req_id,))
        selected_request = cursor.fetchone()

        if selected_request:
            cursor.execute("""
                SELECT * FROM finance_chat 
                WHERE request_id=%s
                ORDER BY created_at ASC
            """, (req_id,))
            chat_messages = cursor.fetchall()

    return render_template(
        "chat_room.html",
        requests_list=requests_list,
        selected_request=selected_request,
        chat_messages=chat_messages,
        role=role
    )


# ---------- Create New Request (Accountant only) ----------

@chat_bp.route("/chat/request/create", methods=["POST"])
@chat_login_required
def create_request():
    if not session.get("chat_role") == "accountant":
        flash("Only accountants can create requests.", "danger")
        return redirect(url_for("chat.chat_room"))

    amount = request.form.get("amount")
    purpose = request.form.get("purpose", "").strip()
    file = request.files.get("attachment")

    if not amount or not purpose:
        flash("Amount and purpose are required.", "danger")
        return redirect(url_for("chat.chat_room"))

    attachment_path = None
    if file and file.filename:
        upload_folder = ensure_upload_folder()
        filename = secure_filename(file.filename)
        save_path = os.path.join(upload_folder, filename)
        file.save(save_path)
        attachment_path = f"/static/chat_uploads/{filename}"

    db = get_db()
    cursor = db.cursor()

    requester_id = session["chat_user_id"]
    requester_name = session.get("chat_full_name") or session.get("chat_username")

    cursor.execute("""
        INSERT INTO finance_requests (requester_id, requester_name, amount, purpose, attachment)
        VALUES (%s, %s, %s, %s, %s)
    """, (requester_id, requester_name, amount, purpose, attachment_path))
    db.commit()

    flash("Request submitted successfully.", "success")
    return redirect(url_for("chat.chat_room"))


# ---------- Send Message in Chat ----------

@chat_bp.route("/chat/send", methods=["POST"])
@chat_login_required
def chat_send():
    request_id = request.form.get("request_id", type=int)
    message_text = request.form.get("message", "").strip()
    file = request.files.get("file")

    if not request_id:
        flash("No request selected.", "danger")
        return redirect(url_for("chat.chat_room"))

    file_url = None
    if file and file.filename:
        upload_folder = ensure_upload_folder()
        filename = secure_filename(file.filename)
        save_path = os.path.join(upload_folder, filename)
        file.save(save_path)
        file_url = f"/static/chat_uploads/{filename}"

    if not message_text and not file_url:
        flash("Message or file required.", "warning")
        return redirect(url_for("chat.chat_room", request_id=request_id))

    db = get_db()
    cursor = db.cursor()

    sender_id = session["chat_user_id"]
    sender_name = session.get("chat_full_name") or session.get("chat_username")

    cursor.execute("""
        INSERT INTO finance_chat (request_id, sender_id, sender_name, message, file_url)
        VALUES (%s, %s, %s, %s, %s)
    """, (request_id, sender_id, sender_name, message_text, file_url))
    db.commit()

    return redirect(url_for("chat.chat_room", request_id=request_id))


# ---------- Approve / Reject (Admin only) ----------

@chat_bp.route("/chat/request/<int:req_id>/approve", methods=["POST"])
@chat_login_required
def approve_request(req_id):
    if not is_admin():
        flash("Only admin can approve.", "danger")
        return redirect(url_for("chat.chat_room"))

    remarks = request.form.get("remarks", "").strip()
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE finance_requests
        SET status='approved', remarks=%s
        WHERE id=%s
    """, (remarks, req_id))
    db.commit()

    flash("Request approved.", "success")
    return redirect(url_for("chat.chat_room", request_id=req_id))


@chat_bp.route("/chat/request/<int:req_id>/reject", methods=["POST"])
@chat_login_required
def reject_request(req_id):
    if not is_admin():
        flash("Only admin can reject.", "danger")
        return redirect(url_for("chat.chat_room"))

    remarks = request.form.get("remarks", "").strip()
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE finance_requests
        SET status='rejected', remarks=%s
        WHERE id=%s
    """, (remarks, req_id))
    db.commit()

    flash("Request rejected.", "warning")
    return redirect(url_for("chat.chat_room", request_id=req_id))

@chat_bp.route("/api/mobile/chat/login", methods=["POST"])
def mobile_chat_login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    db = get_db_safe()
    if not db:
        return jsonify({"success": False}), 503

    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT user_id, username, full_name, role
        FROM chat_users
        WHERE username=%s AND password=%s AND active=1
    """, (username, password))
    user = cur.fetchone()
    cur.close()
    db.close()

    if not user:
        return jsonify({"success": False}), 401

    return jsonify({
        "success": True,
        "token": f"chat_{user['user_id']}",
        "role": user["role"],
        "name": user["full_name"] or user["username"]
    })
 
@chat_bp.route("/api/mobile/chat/requests", methods=["GET"])
def mobile_chat_requests():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer chat_"):
        return jsonify({"success": False}), 401

    user_id = auth.replace("Bearer chat_", "")

    db = get_db_safe()
    if not db:
        return jsonify({"success": False}), 503

    cur = db.cursor(dictionary=True)
    cur.execute("SELECT role FROM chat_users WHERE user_id=%s", (user_id,))
    user = cur.fetchone()

    if not user:
        cur.close()
        db.close()
        return jsonify({"success": False}), 401

    if user["role"] == "admin":
        cur.execute("""
            SELECT id, amount, purpose, status
            FROM finance_requests
            ORDER BY created_at DESC
        """)
    else:
        cur.execute("""
            SELECT id, amount, purpose, status
            FROM finance_requests
            WHERE requester_id=%s
            ORDER BY created_at DESC
        """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    db.close()

    return jsonify({"success": True, "data": rows})

from datetime import timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

@chat_bp.route("/api/mobile/chat/messages/<int:req_id>", methods=["GET"])
def mobile_chat_messages(req_id):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer chat_"):
        return jsonify({"success": False}), 401

    db = get_db_safe()
    if not db:
        return jsonify({"success": False}), 503

    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT
            sender_id,
            sender_name,
            message,
            attachment,
            created_at
        FROM finance_chat
        WHERE request_id=%s
        ORDER BY created_at ASC
    """, (req_id,))

    rows = cur.fetchall()

    for r in rows:
        # Convert datetime → IST string (Flutter safe)
        if r["created_at"]:
            r["created_at"] = (
                r["created_at"]
                .replace(tzinfo=timezone.utc)
                .astimezone(IST)
                .strftime("%d-%m-%Y %I:%M %p")
            )

        if r["attachment"]:
            r["attachment"] = url_for(
                "chat.chat_attachment",
                filename=r["attachment"],
                _external=True
            )

    cur.close()
    db.close()

    return jsonify({
        "success": True,
        "data": rows
    })


@chat_bp.route("/api/mobile/chat/request/add", methods=["POST"])
def mobile_chat_request_add():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer chat_"):
        return jsonify({"success": False}), 401

    user_id = auth.replace("Bearer chat_", "")
    amount = request.form.get("amount")
    purpose = request.form.get("purpose")

    if not amount or not purpose:
        return jsonify({"success": False}), 400

    db = get_db_safe()
    if not db:
        return jsonify({"success": False}), 503

    cur = db.cursor(dictionary=True)
    cur.execute("SELECT full_name, role FROM chat_users WHERE user_id=%s", (user_id,))
    user = cur.fetchone()

    if not user or user["role"] != "accountant":
        cur.close()
        db.close()
        return jsonify({"success": False}), 403

    attachment = None
    if "attachment" in request.files:
        file = request.files["attachment"]
        if file and file.filename:
            upload_dir = os.path.join(current_app.static_folder, CHAT_UPLOAD_DIR)
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file.save(os.path.join(upload_dir, filename))
            attachment = f"/static/{CHAT_UPLOAD_DIR}/{filename}"

    cur.execute("""
        INSERT INTO finance_requests
        (requester_id, requester_name, amount, purpose, attachment, status, created_at)
        VALUES (%s, %s, %s, %s, %s, 'pending', NOW())
    """, (
        user_id,
        user["full_name"],
        amount,
        purpose,
        attachment
    ))

    db.commit()
    cur.close()
    db.close()

    return jsonify({"success": True})
@chat_bp.route("/api/mobile/chat/request/status", methods=["POST"])
def mobile_chat_request_status():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer chat_"):
        return jsonify({"success": False}), 401

    user_id = auth.replace("Bearer chat_", "")
    data = request.json or {}

    req_id = data.get("request_id")
    status = data.get("status")

    if status not in ("approved", "rejected"):
        return jsonify({"success": False}), 400

    db = get_db_safe()
    if not db:
        return jsonify({"success": False}), 503

    cur = db.cursor(dictionary=True)
    cur.execute("SELECT role FROM chat_users WHERE user_id=%s", (user_id,))
    user = cur.fetchone()

    if not user or user["role"] != "admin":
        cur.close()
        db.close()
        return jsonify({"success": False}), 403

    cur.execute("""
        UPDATE finance_requests
        SET status=%s
        WHERE id=%s
    """, (status, req_id))

    db.commit()
    cur.close()
    db.close()

    return jsonify({"success": True})

@chat_bp.route("/api/mobile/chat/send", methods=["POST"])
def mobile_chat_send():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer chat_"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    user_id = auth.replace("Bearer chat_", "")

    request_id = request.form.get("request_id")
    message = request.form.get("message", "").strip()

    if not request_id:
        return jsonify({"success": False, "message": "request_id required"}), 400

    if not message and "attachment" not in request.files:
        return jsonify({
            "success": False,
            "message": "Message or attachment required"
        }), 400

    db = get_db_safe()
    if not db:
        return jsonify({"success": False, "message": "DB busy"}), 503

    cur = db.cursor(dictionary=True)

    # Get sender details
    cur.execute(
        "SELECT full_name FROM chat_users WHERE user_id=%s",
        (user_id,)
    )
    user = cur.fetchone()

    if not user:
        cur.close()
        db.close()
        return jsonify({"success": False}), 401

    attachment_name = None

    # Handle attachment
    if "attachment" in request.files:
        file = request.files["attachment"]
        if file and file.filename:
            upload_dir = os.path.join(
                current_app.root_path, "static", "chat_uploads"
            )
            os.makedirs(upload_dir, exist_ok=True)

            attachment_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file.save(os.path.join(upload_dir, attachment_name))

    # Insert message
    cur.execute("""
        INSERT INTO finance_chat
        (request_id, sender_id, sender_name, message, attachment, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (
        request_id,
        user_id,
        user["full_name"],
        message,
        attachment_name
    ))

    db.commit()
    cur.close()
    db.close()

    return jsonify({"success": True})

@chat_bp.route("/chat/attachment/<path:filename>")
def chat_attachment(filename):
    upload_dir = os.path.join(
        current_app.root_path, "static", "chat_uploads"
    )
    return send_from_directory(upload_dir, filename, as_attachment=False)
