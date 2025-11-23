# ============================================
# FILE: app/routers/dashboard.py
# MYSQL VERSION – FINAL CLEANED
# ============================================

from flask import Blueprint, render_template, session, redirect, url_for
import mysql.connector
import os

dashboard_bp = Blueprint("dashboard", __name__)

# --------------------------------------------
#  MYSQL CONNECTION
# --------------------------------------------
def get_db():
    """Return a fresh MySQL connection."""
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "srv366.hstgr.io"),
        user=os.getenv("MYSQL_USER", "u514260654_testerp"),
        password=os.getenv("MYSQL_PASSWORD", "Tions@98"),
        database=os.getenv("MYSQL_DATABASE", "u514260654_test_erp"),
        auth_plugin="mysql_native_password"
    )

# ============================================
#  Dashboard Route
# ============================================
@dashboard_bp.route("/dashboard")
def dashboard():
    """Render Dashboard statistics & charts."""

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    try:
        db = get_db()
        cur = db.cursor(dictionary=True)

        # TOTAL STUDENTS
        cur.execute("SELECT COUNT(*) AS total FROM students")
        total_students = cur.fetchone()["total"]

        # DROPOUT STUDENTS
        cur.execute("SELECT COUNT(*) AS total FROM dropouts")
        dropout_students = cur.fetchone()["total"]

        # BSC NURSING (Yearly + Sem)
        cur.execute("""
            SELECT COUNT(*) AS total FROM students
            WHERE course IN ('BSC NURSING YEARLY', 'BSC NURSING SEM', 'BSC NURSING')
        """)
        bsc_students = cur.fetchone()["total"]

        # MSC NURSING
        cur.execute("SELECT COUNT(*) AS total FROM students WHERE course = 'MSC NURSING'")
        msc_students = cur.fetchone()["total"]

        # BATCH CHART
        cur.execute("""
            SELECT COALESCE(batch, '') AS batch, COUNT(*) AS count
            FROM students
            GROUP BY batch
            ORDER BY batch ASC
        """)
        rows = cur.fetchall()
        chart_labels = [(r["batch"] or "Unknown") for r in rows]
        chart_values = [r["count"] for r in rows]

        cur.close()
        db.close()

        return render_template(
            "dashboard.html",
            title="Dashboard",
            total_students=total_students,
            dropout_students=dropout_students,
            bsc_students=bsc_students,
            msc_students=msc_students,
            chart_labels=chart_labels,
            chart_values=chart_values
        )

    except Exception as e:
        print("DASHBOARD ERROR:", e)

        try: db.close()
        except: pass

        return render_template(
            "dashboard.html",
            title="Dashboard",
            total_students=0,
            dropout_students=0,
            bsc_students=0,
            msc_students=0,
            chart_labels=[],
            chart_values=[]
        )
