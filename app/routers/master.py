# app/routers/master.py
# MYSQL VERSION – FIXED & FINAL
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
import mysql.connector
import os
import uuid
from datetime import datetime

master_bp = Blueprint("master", __name__, url_prefix="/master")


def get_db():
    """
    Create a new MySQL connection.
    Reads env vars (supports both MYSQL_DB and MYSQL_DATABASE to be tolerant with .env).
    Raises an exception early if required config missing.
    """
    host = os.getenv("MYSQL_HOST")
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    # support either MYSQL_DB or MYSQL_DATABASE
    database = os.getenv("MYSQL_DB") or os.getenv("MYSQL_DATABASE")

    if not (host and user and password and database):
        raise RuntimeError("Missing MySQL configuration. Please set MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD and MYSQL_DB (or MYSQL_DATABASE).")

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        auth_plugin="mysql_native_password",
        connection_timeout=10,
        # You may tune other params here
    )


# ---- helpers ----
def _is_logged_in():
    return session.get("logged_in", False)


def _normalize_name(name: str) -> str:
    return name.strip().replace(" ", "_").lower()


# ---- ensure master exists & return id ----
def ensure_master_exists(master_name):
    """
    Ensure a row exists in masters table for master_name.
    Returns the integer id of the master row.
    Uses buffered cursor to avoid 'Unread result found' errors.
    """
    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor(dictionary=True, buffered=True)
        cur.execute("SELECT id FROM masters WHERE master_name = %s", (master_name,))
        row = cur.fetchone()
        if row:
            return row["id"]

        # Insert new master
        cur.execute("INSERT INTO masters (master_name) VALUES (%s)", (master_name,))
        db.commit()
        # cur.lastrowid returns integer id
        master_id = cur.lastrowid
        return master_id
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                current_app.logger.exception("Failed to close cursor in ensure_master_exists")
        if db:
            try:
                db.close()
            except Exception:
                current_app.logger.exception("Failed to close db connection in ensure_master_exists")


# ---- Render master page ----
@master_bp.route("/<master_name>")
def master_page(master_name):
    if not _is_logged_in():
        return redirect(url_for("login"))

    master_name_norm = _normalize_name(master_name)
    # ensure exists but ignore returned id here
    try:
        ensure_master_exists(master_name_norm)
    except Exception as e:
        current_app.logger.exception("Failed ensure_master_exists for %s: %s", master_name_norm, e)
        # still render page; master will be created lazily in list/add endpoints
    title = master_name_norm.replace("_", " ").title()
    return render_template("master.html", master_name=master_name_norm, title=title)


# ---- List items ----
@master_bp.route("/<master_name>/items", methods=["GET"])
def list_items(master_name):
    if not _is_logged_in():
        return jsonify({"error": True, "message": "Unauthorized"}), 401

    master_name_norm = _normalize_name(master_name)
    try:
        master_id = ensure_master_exists(master_name_norm)
    except Exception as e:
        current_app.logger.exception("ensure_master_exists failed: %s", e)
        return jsonify({"success": False, "message": "Failed to ensure master exists"}), 500

    db = None
    cur = None
    try:
        db = get_db()
        # buffered cursor to avoid unread result issues when multiple queries used on same connection
        cur = db.cursor(dictionary=True, buffered=True)
        cur.execute("""
            SELECT id, master_id, name, created_at
            FROM master_items
            WHERE master_id = %s
            ORDER BY created_at DESC
        """, (master_id,))
        items = cur.fetchall()
        return jsonify({"success": True, "items": items})
    except Exception as e:
        current_app.logger.exception("Error loading master items: %s", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                current_app.logger.exception("Failed to close cursor in list_items")
        if db:
            try:
                db.close()
            except Exception:
                current_app.logger.exception("Failed to close connection in list_items")


# ---- Add item ----
@master_bp.route("/<master_name>/items", methods=["POST"])
def add_item(master_name):
    if not _is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    master_name_norm = _normalize_name(master_name)
    try:
        master_id = ensure_master_exists(master_name_norm)
    except Exception as e:
        current_app.logger.exception("ensure_master_exists failed: %s", e)
        return jsonify({"success": False, "message": "Failed to ensure master exists"}), 500

    payload = request.get_json(silent=True) or request.form.to_dict()
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Name required"}), 400

    db = None
    cur = None
    try:
        item_id = str(uuid.uuid4())
        created_at = datetime.utcnow()

        db = get_db()
        cur = db.cursor(buffered=True)
        cur.execute("""
            INSERT INTO master_items (id, master_id, name, created_at)
            VALUES (%s, %s, %s, %s)
        """, (item_id, master_id, name, created_at))
        db.commit()
        return jsonify({"success": True, "id": item_id})
    except Exception as e:
        current_app.logger.exception("Error adding master item: %s", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                current_app.logger.exception("Failed to close cursor in add_item")
        if db:
            try:
                db.close()
            except Exception:
                current_app.logger.exception("Failed to close connection in add_item")


# ---- Update item ----
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
        return jsonify({"success": True, "id": item_id})
    except Exception as e:
        current_app.logger.exception("Error updating item: %s", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                current_app.logger.exception("Failed to close cursor in update_item")
        if db:
            try:
                db.close()
            except Exception:
                current_app.logger.exception("Failed to close connection in update_item")


# ---- Delete item ----
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
        return jsonify({"success": True, "id": item_id})
    except Exception as e:
        current_app.logger.exception("Error deleting item: %s", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                current_app.logger.exception("Failed to close cursor in delete_item")
        if db:
            try:
                db.close()
            except Exception:
                current_app.logger.exception("Failed to close connection in delete_item")
