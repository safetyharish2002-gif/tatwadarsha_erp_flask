# ====================================================
# FILE: app/routers/auth.py  (FLASK VERSION)
# ====================================================

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import os
from datetime import timedelta

auth_bp = Blueprint("auth", __name__)

# --------------------------------------------
#  LOGIN CONFIG (ENV VARIABLES)
# --------------------------------------------
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin@")

SESSION_HOURS = 8


# ====================================================
# LOGIN PAGE (GET)
# ====================================================
@auth_bp.route("/login", methods=["GET"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("dashboard.dashboard"))

    return render_template("login.html", title="Login", error=None)


# ====================================================
# LOGIN SUBMISSION (POST)
# ====================================================
@auth_bp.route("/login", methods=["POST"])
def login_action():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    # Validate credentials
    if username == ADMIN_USER and password == ADMIN_PASS:
        session["logged_in"] = True
        session["username"] = username
        session.permanent = True
        session.permanent_session_lifetime = timedelta(hours=SESSION_HOURS)

        flash("Welcome back, Admin!", "success")
        return redirect(url_for("dashboard.dashboard"))

    # Invalid
    return render_template("login.html",
                           title="Login",
                           error="Invalid username or password. Please try again.")


# ====================================================
# LOGOUT
# ====================================================
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("auth.login_page"))
