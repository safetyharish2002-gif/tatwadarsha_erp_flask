# ====================================================
# FILE: app/routers/auth.py  (FLASK VERSION + JWT API)
# ====================================================

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import os
from datetime import timedelta
import jwt
import datetime

auth_bp = Blueprint("auth", __name__)

# --------------------------------------------
# LOGIN CONFIG (ENV VARIABLES)
# --------------------------------------------
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin@")
SESSION_HOURS = 8

# JWT Secret Key
from app.jwt_utils import SECRET_KEY as JWT_SECRET

# ====================================================
# LOGIN PAGE (WEB - GET)
# ====================================================
@auth_bp.route("/login", methods=["GET"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("dashboard.dashboard"))

    return render_template("login.html", title="Login", error=None)


# ====================================================
# LOGIN SUBMISSION (WEB - POST)
# ====================================================
@auth_bp.route("/login", methods=["POST"])
def login_action():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if username == ADMIN_USER and password == ADMIN_PASS:
        session["logged_in"] = True
        session["username"] = username
        session.permanent = True
        session.permanent_session_lifetime = timedelta(hours=SESSION_HOURS)

        flash("Welcome back, Admin!", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("login.html",
                           title="Login",
                           error="Invalid username or password. Please try again.")

# ====================================================
# LOGOUT (WEB)
# ====================================================
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("auth.login_page"))


# ====================================================
# 📱 MOBILE APP LOGIN (API - POST)
# ====================================================
@auth_bp.route("/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "Missing credentials"}), 400

    if username != ADMIN_USER or password != ADMIN_PASS:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    # Create JWT token
    payload = {
        "username": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=SESSION_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # Convert bytes to string if needed
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return jsonify({
        "success": True,
        "token": token,
        "username": username,
    }), 200
