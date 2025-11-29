# ============================================
# app/routers/master.py
# FINAL STABLE VERSION (NO LOGIC CHANGED)
# ============================================

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
import mysql.connector
import os
import uuid
from datetime import datetime

master_bp = Blueprint("master", __name__, url_prefix="/master")


# ============================================
# Database Connection
# ============================================
def get_db():
    """
    Global MySQL connection for ALL modules (fees, students, masters).
    Reads .env values safely.
    """
    host = os.getenv("MYSQL_HOST")
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    database = os.getenv("MYSQL_DB") or os.getenv("MYSQL_DATABASE")

    if not (host and user and password and database):
        raise RuntimeError("❌ Missing MySQL environment variables.")

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        auth_plugin="mysql_native_password",
        connection_timeout=10
    )


# ============================================
# Helpers
# ============================================
def _is_logged_in():
    return session.get("logged_in", False)


def _normalize_name(name: str) -> str:
    return name.strip().replace(" ", "_").lower()


# ============================================
# Ensure master exists & return its ID
# ============================================
def ensure_master_exists(master_name):
    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor(dictionary=True, buffered=True)

        cur.execute("SELECT id FROM masters WHERE master_name=%s", (master_name,))
        row = cur.fetchone()

        if row:
            return row["id"]

        cur.execute(
            "INSERT INTO masters (master_name) VALUES (%s)",
            (master_name,)
        )
        db.commit()
        return cur.lastrowid

    except Exception as e:
        current_app.logger.exception("ensure_master_exists error: %s", e)
        raise e
    finally:
        if cur:
            try: cur.close()
            except: pass
        if db:
            try: db.close()
            except: pass


# ============================================
# PAGE RENDER
# ============================================
@master_bp.route("/<master_name>")
def master_page(master_name):
    if not _is_logged_in():
        return redirect(url_for("login"))

    master_name_norm = _normalize_name(master_name)

    # Guarantee master exists
    try:
        ensure_master_exists(master_name_norm)
    except Exception:
        pass

    title = master_name_norm.replace("_", " ").title()

    return render_template("master.html", master_name=master_name_norm, title=title)


# ============================================
# LIST ITEMS
# ============================================
@master_bp.route("/<master_name>/items", methods=["GET"])
def list_items(master_name):
    if not _is_logged_in():
        return jsonify({"error": True, "message": "Unauthorized"}), 401

    master_name_norm = _normalize_name(master_name)
    master_id = ensure_master_exists(master_name_norm)

    db = None
    cur = None

    try:
        db = get_db()
        cur = db.cursor(dictionary=True, buffered=True)

        cur.execute("""
            SELECT id, master_id, name, created_at
            FROM master_items
            WHERE master_id=%s
            ORDER BY created_at DESC
        """, (master_id,))

        items = cur.fetchall()

        return jsonify({"success": True, "items": items})

    finally:
        if cur:
            try: cur.close()
            except: pass
        if db:
            try: db.close()
            except: pass


# ============================================
# ADD ITEM
# ============================================
@master_bp.route("/<master_name>/items", methods=["POST"])
def add_item(master_name):
    if not _is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    master_name_norm = _normalize_name(master_name)
    master_id = ensure_master_exists(master_name_norm)

    payload = request.get_json(silent=True) or request.form.to_dict()
    name = (payload.get("name") or "").strip()

    if not name:
        return jsonify({"success": False, "message": "Name required"}), 400

    db = None
    cur = None

    try:
        item_id = str(uuid.uuid4())

        db = get_db()
        cur = db.cursor(buffered=True)

        cur.execute("""
            INSERT INTO master_items (id, master_id, name, created_at)
            VALUES (%s, %s, %s, %s)
        """, (item_id, master_id, name, datetime.utcnow()))

        db.commit()

        return jsonify({"success": True, "id": item_id})

    finally:
        if cur: 
            try: cur.close()
            except: pass
        if db:
            try: db.close()
            except: pass


# ============================================
# UPDATE ITEM
# ============================================
@master_bp.route("/<master_name>/items/<item_id>", methods=["PUT"])
def update_item(master_name, item_id):
    if not _is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or request.form.to_dict()
    name = (payload.get("name") or "").strip()

    if not name:
        return jsonify({"success": False, "message": "Name required"}), 400

    db = None
    cur = None

    try:
        db = get_db()
        cur = db.cursor(buffered=True)

        cur.execute("UPDATE master_items SET name=%s WHERE id=%s", (name, item_id))
        db.commit()

        return jsonify({"success": True})

    finally:
        if cur:
            try: cur.close()
            except: pass
        if db:
            try: db.close()
            except: pass


# ============================================
# DELETE ITEM
# ============================================
@master_bp.route("/<master_name>/items/<item_id>", methods=["DELETE"])
def delete_item(master_name, item_id):
    if not _is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = None
    cur = None

    try:
        db = get_db()
        cur = db.cursor(buffered=True)

        cur.execute("DELETE FROM master_items WHERE id=%s", (item_id,))
        db.commit()

        return jsonify({"success": True})

    finally:
        if cur:
            try: cur.close()
            except: pass
        if db:
            try: db.close()
            except: pass
