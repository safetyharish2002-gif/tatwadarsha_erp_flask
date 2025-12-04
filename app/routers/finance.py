from app.routers.master import get_db
from flask import session, jsonify
import uuid
from datetime import datetime, date
# FILE: app/routers/finance.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, session
from app.db import get_mysql_connection

finance_bp = Blueprint("finance", __name__)

# ---------------------------------------
# Login Session Check
# ---------------------------------------
def is_logged_in():
    return session.get("logged_in", False)


# ---------------------------------------
# Cash & Bank Master Page
# ---------------------------------------
@finance_bp.route("/finance/cash-bank")
def cash_bank_master():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS bank_accounts ("
        "id INT PRIMARY KEY AUTO_INCREMENT, "
        "account_type VARCHAR(20), "
        "account_name VARCHAR(100), "
        "account_holder_name VARCHAR(100), "
        "account_number VARCHAR(30), "
        "ifsc_code VARCHAR(20), "
        "branch_name VARCHAR(100), "
        "opening_balance DECIMAL(12,2)"
        ")"
    )

    cur.execute("SELECT * FROM bank_accounts ORDER BY id DESC")
    accounts = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    data = [dict(zip(cols, row)) for row in accounts]

    cur.close()
    conn.close()

    return render_template(
        "finance/cash_bank_master.html",
        title="Cash & Bank Master",
        accounts=data,
    )


# ---------------------------------------
# Add Cash / Bank Account
# ---------------------------------------
@finance_bp.route("/finance/add-account", methods=["POST"])
def add_account():
    if not is_logged_in():
        return jsonify({"success": False}), 403

    data = request.form
    conn = get_mysql_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO bank_accounts 
        (account_type, account_name, account_holder_name, account_number,
         ifsc_code, branch_name, opening_balance)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """,
        (
            data.get("account_type"),
            data.get("account_name"),
            data.get("account_holder_name"),
            data.get("account_number"),
            data.get("ifsc_code"),
            data.get("branch_name"),
            data.get("opening_balance"),
        ),
    )

    conn.commit()
    cur.close()
    conn.close()

    flash("✔ Account Added Successfully!", "success")
    return redirect(url_for("finance.cash_bank_master"))

# ---------------------------------------
# File upload helpers
# ---------------------------------------
from werkzeug.utils import secure_filename
import os
import uuid
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
    session,
    current_app,
)
def fetchall_dict(cur):
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, r)) for r in cur.fetchall()]

from flask import send_from_directory

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------
# Bank Deposit (With Date Filters)
# ---------------------------------------
@finance_bp.route("/finance/bank-deposit", methods=["GET", "POST"])
def bank_deposit():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch BANK accounts for dropdown
    cur.execute("SELECT id, account_name FROM bank_accounts WHERE account_type='BANK'")
    bank_accounts = cur.fetchall()

    # ---------- POST: Save Transaction ----------
    if request.method == "POST":
        account_id = request.form.get("account_id")
        amount = request.form.get("amount")
        description = request.form.get("description")
        tx_date = request.form.get("tx_date")

        tx_id = uuid.uuid4().hex
        attachment_url = None

        # File Upload
        file = request.files.get("attachment")
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{tx_id}_{file.filename}")
            upload_dir = current_app.config["UPLOAD_FOLDER_FINANCE"]
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            attachment_url = filename

        try:
            # Insert Transaction (DEPOSIT to BANK)
            cur.execute("""
                INSERT INTO finance_transactions
                (id, account_id, transaction_mode, transaction_type, amount,
                 description, attachment_url, tx_date)
                VALUES (%s, %s, 'BANK', 'DEPOSIT', %s, %s, %s, %s)
            """, (tx_id, account_id, amount, description, attachment_url, tx_date))

            # ❌ DO NOT TOUCH opening_balance HERE
            conn.commit()
            flash("💰 Bank Deposit Recorded Successfully!", "success")
            return redirect(url_for("finance.bank_deposit"))

        except Exception as e:
            conn.rollback()
            flash(f"❌ Error: {e}", "danger")

    # ---------- GET: Load Deposit History ----------
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    query = """
        SELECT ft.id, ft.amount, ft.description, ft.tx_date, ft.attachment_url,
               ba.account_name
        FROM finance_transactions ft
        JOIN bank_accounts ba ON ft.account_id = ba.id
        WHERE ft.transaction_type = 'DEPOSIT'
    """

    filters = []
    values = []

    if from_date:
        filters.append("ft.tx_date >= %s")
        values.append(from_date)

    if to_date:
        filters.append("ft.tx_date <= %s")
        values.append(to_date)

    if filters:
        query += " AND " + " AND ".join(filters)

    query += " ORDER BY ft.tx_date DESC"

    cur.execute(query, tuple(values))
    deposits = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "finance/bank_deposit.html",
        title="Bank Deposit",
        bank_accounts=bank_accounts,
        deposits=deposits,
        from_date=from_date,
        to_date=to_date
    )

# ---------------------------------------
# Delete Bank Deposit (no opening_balance revert)
# ---------------------------------------
@finance_bp.route("/finance/bank-deposit/delete/<string:tx_id>", methods=["POST"])
def delete_deposit(tx_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT account_id, amount
            FROM finance_transactions
            WHERE id=%s AND transaction_type='DEPOSIT'
        """, (tx_id,))
        tx = cur.fetchone()

        if not tx:
            flash("Record not found!", "danger")
        else:
            # Just delete the transaction; balances come from ledger logic
            cur.execute("DELETE FROM finance_transactions WHERE id=%s", (tx_id,))
            conn.commit()
            flash("🗑 Deposit deleted successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("finance.bank_deposit"))

# ---------------------------------------
# Self Withdrawal (Bank -> Cash)
# ---------------------------------------
@finance_bp.route("/finance/self-withdrawal", methods=["GET", "POST"])
def self_withdrawal():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    # Load all bank accounts (only BANK type)
    cur.execute("SELECT id, account_name FROM bank_accounts WHERE account_type='BANK'")
    bank_accounts = cur.fetchall()

    # Get CASH account (must exist)
    cur.execute("SELECT id FROM bank_accounts WHERE account_type='CASH' LIMIT 1")
    cash_row = cur.fetchone()
    if not cash_row:
        flash("⚠️ Add a CASH account first in Cash & Bank Master!", "warning")
        return redirect(url_for("finance.cash_bank_master"))

    cash_account_id = cash_row["id"]

    # POST: Save new withdrawal
    if request.method == "POST":
        account_id = request.form.get("account_id")
        amount = float(request.form.get("amount"))
        description = request.form.get("description")
        tx_date = request.form.get("tx_date")

        # File upload
        attachment_url = None
        file = request.files.get("attachment")
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
            upload_path = os.path.join(current_app.config["UPLOAD_FOLDER_FINANCE"], filename)
            os.makedirs(upload_path.rsplit(os.sep, 1)[0], exist_ok=True)
            file.save(upload_path)
            attachment_url = filename

        try:
            # Record BANK side withdrawal (money moving out of bank)
            cur.execute("""
                INSERT INTO finance_transactions
                (account_id, transaction_mode, transaction_type, amount,
                 description, attachment_url, tx_date)
                VALUES (%s, 'BANK', 'WITHDRAWAL', %s, %s, %s, %s)
            """, (account_id, amount, description, attachment_url, tx_date))

            # ❌ Do not touch opening_balance of BANK or CASH here
            conn.commit()
            flash("💸 Cash received from bank successfully!", "success")
            return redirect(url_for("finance.self_withdrawal"))

        except Exception as e:
            conn.rollback()
            flash(f"❌ Error: {e}", "danger")

    # ------------------------------------------
    # GET: Load withdrawal history with filters
    # ------------------------------------------
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    query = """
        SELECT t.id, t.amount, t.description, t.tx_date, t.attachment_url,
               a.account_name
        FROM finance_transactions t
        JOIN bank_accounts a ON t.account_id = a.id
        WHERE t.transaction_type = 'WITHDRAWAL'
    """

    filters = []
    values = []

    if from_date:
        filters.append("t.tx_date >= %s")
        values.append(from_date)

    if to_date:
        filters.append("t.tx_date <= %s")
        values.append(to_date)

    if filters:
        query += " AND " + " AND ".join(filters)

    query += " ORDER BY t.tx_date DESC"

    cur.execute(query, tuple(values))
    withdrawals = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "finance/self_withdrawal.html",
        title="Self Withdrawal",
        bank_accounts=bank_accounts,
        withdrawals=withdrawals,
        from_date=from_date,
        to_date=to_date
    )

# ---------------------------------------
# Delete Self Withdrawal (no opening_balance revert)
# ---------------------------------------
@finance_bp.route("/finance/self-withdrawal/delete/<string:tx_id>", methods=["POST"])
def delete_withdrawal(tx_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT account_id, amount
            FROM finance_transactions
            WHERE id=%s AND transaction_type='WITHDRAWAL'
        """, (tx_id,))
        tx = cur.fetchone()

        if not tx:
            flash("Record not found!", "danger")
        else:
            # Only delete transaction; balances handled via reports
            cur.execute("DELETE FROM finance_transactions WHERE id=%s", (tx_id,))
            conn.commit()
            flash("🗑 Withdrawal deleted successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"❌ Error: {e}", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("finance.self_withdrawal"))

# ---------------------------------------
# Expense Entry (with Categories + Edit/Delete)
# ---------------------------------------
@finance_bp.route("/finance/expense", methods=["GET", "POST"])
def expense_entry():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    if not conn:
        flash("DB connection failed", "danger")
        return redirect(url_for("finance.cash_bank_master"))

    form_type = request.form.get("form_type") if request.method == "POST" else None
    cur = conn.cursor(dictionary=True)

    # ---- CATEGORY ADD / DELETE (MODAL) ----
    if request.method == "POST" and form_type in ("add_category", "delete_category"):
        try:
            if form_type == "add_category":
                category_name = (request.form.get("category_name") or "").strip()
                if category_name:
                    cur.execute(
                        """
                        INSERT INTO expense_categories (category_name)
                        VALUES (%s)
                    """,
                        (category_name,),
                    )
                    conn.commit()
                    flash("✔ Expense Category Added!", "success")

            elif form_type == "delete_category":
                cid = request.form.get("category_id")
                cur.execute("DELETE FROM expense_categories WHERE id=%s", (cid,))
                conn.commit()
                flash("🗑️ Category Deleted!", "success")

        except Exception as e:
            conn.rollback()
            flash(f"❌ Category Error: {e}", "danger")

        cur.close()
        conn.close()
        return redirect(url_for("finance.expense_entry"))

    # ---- UPDATE EXISTING EXPENSE ----
    if request.method == "POST" and form_type == "update_expense":
        expense_id = int(request.form.get("expense_id"))
        new_account_id = int(request.form.get("account_id"))
        new_amount = float(request.form.get("amount"))
        new_category = request.form.get("category")
        new_desc = request.form.get("description")
        new_date = request.form.get("tx_date")

        try:
            cur.execute(
                """
                SELECT account_id, amount, attachment_url
                FROM finance_transactions
                WHERE id=%s AND transaction_type='EXPENSE'
            """,
                (expense_id,),
            )
            old = cur.fetchone()
            if not old:
                flash("Expense not found for update.", "danger")
            else:
                old_attach = old["attachment_url"]

                # determine transaction mode from new account
                cur.execute(
                    "SELECT account_type FROM bank_accounts WHERE id=%s", (new_account_id,)
                )
                acc = cur.fetchone()
                if not acc:
                    flash("Account not found.", "danger")
                else:
                    new_mode = "CASH" if acc["account_type"] == "CASH" else "BANK"

                    # file update
                    file = request.files.get("attachment")
                    if file and allowed_file(file.filename):
                        filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
                        upload_path = os.path.join(
                            current_app.config["UPLOAD_FOLDER_FINANCE"], filename
                        )
                        os.makedirs(upload_path.rsplit(os.sep, 1)[0], exist_ok=True)
                        file.save(upload_path)
                        new_attach = filename
                    else:
                        new_attach = old_attach

                    # ❌ Do NOT adjust opening_balance anymore; only update transaction
                    cur.execute(
                        """
                        UPDATE finance_transactions
                        SET account_id=%s,
                            transaction_mode=%s,
                            amount=%s,
                            category=%s,
                            description=%s,
                            attachment_url=%s,
                            tx_date=%s
                        WHERE id=%s
                    """,
                        (
                            new_account_id,
                            new_mode,
                            new_amount,
                            new_category,
                            new_desc,
                            new_attach,
                            new_date,
                            expense_id,
                        ),
                    )

                    conn.commit()
                    flash("✏ Expense updated successfully!", "success")

        except Exception as e:
            conn.rollback()
            flash(f"❌ Update error: {e}", "danger")

        cur.close()
        conn.close()
        return redirect(url_for("finance.expense_entry"))

    # ---- CREATE NEW EXPENSE ----
    if request.method == "POST" and form_type == "expense":
        account_id = int(request.form.get("account_id"))
        amount = float(request.form.get("amount"))
        category = request.form.get("category")
        description = request.form.get("description")
        tx_date = request.form.get("tx_date")

        try:
            # determine mode from account_type
            cur.execute("SELECT account_type FROM bank_accounts WHERE id=%s", (account_id,))
            acc = cur.fetchone()
            if not acc:
                flash("Account not found.", "danger")
            else:
                mode = "CASH" if acc["account_type"] == "CASH" else "BANK"

                file = request.files.get("attachment")
                attachment_url = None
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
                    upload_path = os.path.join(
                        current_app.config["UPLOAD_FOLDER_FINANCE"], filename
                    )
                    os.makedirs(upload_path.rsplit(os.sep, 1)[0], exist_ok=True)
                    file.save(upload_path)
                    attachment_url = filename

                # insert transaction only
                cur.execute(
                    """
                    INSERT INTO finance_transactions
                    (account_id, transaction_mode, transaction_type, amount, category,
                     description, attachment_url, tx_date)
                    VALUES (%s, %s, 'EXPENSE', %s, %s, %s, %s, %s)
                """,
                    (
                        account_id,
                        mode,
                        amount,
                        category,
                        description,
                        attachment_url,
                        tx_date,
                    ),
                )

                # ❌ Do NOT reduce opening_balance here
                conn.commit()
                flash("💸 Expense Entry Saved!", "success")

        except Exception as e:
            conn.rollback()
            flash(f"❌ Expense Error: {e}", "danger")

        cur.close()
        conn.close()
        return redirect(url_for("finance.expense_entry"))

    # ==========================
    # GET: Load data for page
    # ==========================
    # accounts
    cur_accounts = conn.cursor(dictionary=True)
    cur_accounts.execute(
        """
        SELECT id, account_type, account_name
        FROM bank_accounts
        ORDER BY account_type, account_name
    """
    )
    accounts = cur_accounts.fetchall()

    # categories
    cur_cats = conn.cursor(dictionary=True)
    cur_cats.execute("SELECT id, category_name FROM expense_categories ORDER BY category_name ASC")
    categories = cur_cats.fetchall()

    # expenses
    cur_exp = conn.cursor(dictionary=True)
    cur_exp.execute(
        """
        SELECT ft.*, ba.account_name, ba.account_type
        FROM finance_transactions ft
        LEFT JOIN bank_accounts ba ON ft.account_id = ba.id
        WHERE ft.transaction_type = 'EXPENSE'
        ORDER BY ft.tx_date DESC, ft.id DESC
    """
    )
    expense_rows = cur_exp.fetchall()

    cur_accounts.close()
    cur_cats.close()
    cur_exp.close()
    conn.close()

    return render_template(
        "finance/expense_entry.html",
        title="Expense Entry",
        accounts=accounts,
        categories=categories,
        expense_rows=expense_rows,
    )


# ---------------------------------------
# Delete Expense (no opening_balance revert)
# ---------------------------------------
@finance_bp.route("/finance/expense/delete/<int:tx_id>", methods=["POST"])
def delete_expense(tx_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    if not conn:
        flash("DB connection failed", "danger")
        return redirect(url_for("finance.expense_entry"))

    cur = conn.cursor(dictionary=True)
    try:
        # get transaction
        cur.execute(
            """
            SELECT account_id, amount
            FROM finance_transactions
            WHERE id=%s AND transaction_type='EXPENSE'
        """,
            (tx_id,),
        )
        row = cur.fetchone()
        if not row:
            flash("Expense not found.", "danger")
        else:
            # Just delete; balance comes from ledger logic
            cur.execute("DELETE FROM finance_transactions WHERE id=%s", (tx_id,))
            conn.commit()
            flash("🗑 Expense deleted.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"❌ Delete error: {e}", "danger")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("finance.expense_entry"))


# ---------------------------------------
# Serve Finance Attachments Securely
# ---------------------------------------
@finance_bp.route("/finance/attachment/<path:filename>")
def finance_attachment(filename):
    if not is_logged_in():
        return "Unauthorized", 403
    folder = current_app.config["UPLOAD_FOLDER_FINANCE"]
    return send_from_directory(folder, filename)


# ✅ ALIAS ROUTE so old templates using
#    'finance.finance_attachment_view'
#    still work without changes
@finance_bp.route("/finance/attachment-view/<path:filename>")
def finance_attachment_view(filename):
    # Reuse the same logic
    return finance_attachment(filename)

# ---------------------------------------
# Income Entry (Manual)
# ---------------------------------------
@finance_bp.route("/finance/income", methods=["GET", "POST"])
def income_entry():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    if not conn:
        flash("DB connection failed", "danger")
        return redirect(url_for("finance.cash_bank_master"))

    form_type = request.form.get("form_type") if request.method == "POST" else None
    cur = conn.cursor(dictionary=True)

    # ---- Ensure income_categories table exists ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS income_categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category_name VARCHAR(100) NOT NULL,
            is_active TINYINT(1) DEFAULT 1
        )
    """)

    # ========== CATEGORY ADD / DELETE (MODAL) ==========
    if request.method == "POST" and form_type in ("add_income_category", "delete_income_category"):
        try:
            if form_type == "add_income_category":
                category_name = (request.form.get("category_name") or "").strip()
                if category_name:
                    cur.execute("""
                        INSERT INTO income_categories (category_name, is_active)
                        VALUES (%s, 1)
                    """, (category_name,))
                    conn.commit()
                    flash("✔ Income Category Added!", "success")

            elif form_type == "delete_income_category":
                cid = request.form.get("category_id")
                cur.execute("DELETE FROM income_categories WHERE id=%s", (cid,))
                conn.commit()
                flash("🗑️ Income Category Deleted!", "success")

        except Exception as e:
            conn.rollback()
            flash(f"❌ Income Category Error: {e}", "danger")

        cur.close()
        conn.close()
        return redirect(url_for("finance.income_entry"))

    # ========== CREATE NEW MANUAL INCOME ==========
    if request.method == "POST" and form_type == "income":
        account_id = int(request.form.get("account_id"))
        amount = float(request.form.get("amount"))
        category_name = request.form.get("category")
        description = request.form.get("description")
        tx_date = request.form.get("tx_date")

        try:
            # determine mode from account_type
            cur.execute("SELECT account_type FROM bank_accounts WHERE id=%s", (account_id,))
            acc = cur.fetchone()
            if not acc:
                flash("Account not found.", "danger")
            else:
                mode = "CASH" if acc["account_type"] == "CASH" else "BANK"

                # File upload
                attachment_url = None
                file = request.files.get("attachment")
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
                    upload_path = os.path.join(current_app.config["UPLOAD_FOLDER_FINANCE"], filename)
                    os.makedirs(upload_path.rsplit(os.sep, 1)[0], exist_ok=True)
                    file.save(upload_path)
                    attachment_url = filename

                tx_id = uuid.uuid4().hex

                # insert transaction as INCOME only
                cur.execute("""
                    INSERT INTO finance_transactions
                    (id, account_id, transaction_mode, transaction_type, amount, category,
                     description, attachment_url, tx_date)
                    VALUES (%s, %s, %s, 'INCOME', %s, %s, %s, %s, %s)
                """, (tx_id, account_id, mode, amount, category_name, description, attachment_url, tx_date))

                # ❌ Do NOT update opening_balance here
                conn.commit()
                flash("💰 Income Entry Saved!", "success")

        except Exception as e:
            conn.rollback()
            flash(f"❌ Income Error: {e}", "danger")

        cur.close()
        conn.close()
        return redirect(url_for("finance.income_entry"))

    # ========== GET: LOAD DATA + APPLY FILTERS ==========
    # accounts (Cash + Bank)
    cur_accounts = conn.cursor(dictionary=True)
    cur_accounts.execute("""
        SELECT id, account_type, account_name
        FROM bank_accounts
        ORDER BY account_type, account_name
    """)
    accounts = cur_accounts.fetchall()

    # income categories
    cur_cats = conn.cursor(dictionary=True)
    cur_cats.execute("SELECT id, category_name FROM income_categories WHERE is_active=1 ORDER BY category_name ASC")
    categories = cur_cats.fetchall()

    # filters
    from_date = request.args.get("from_date") or ""
    to_date = request.args.get("to_date") or ""
    category_filter = request.args.get("category") or ""

    cur_inc = conn.cursor(dictionary=True)
    query = """
        SELECT t.*, ba.account_name, ba.account_type
        FROM finance_transactions t
        LEFT JOIN bank_accounts ba ON t.account_id = ba.id
        WHERE t.transaction_type = 'INCOME'
    """
    params = []

    if from_date:
        query += " AND t.tx_date >= %s"
        params.append(from_date)

    if to_date:
        query += " AND t.tx_date <= %s"
        params.append(to_date)

    if category_filter and category_filter != "ALL":
        query += " AND t.category = %s"
        params.append(category_filter)

    query += " ORDER BY t.tx_date DESC, t.id DESC"

    cur_inc.execute(query, tuple(params))
    income_rows = cur_inc.fetchall()

    cur_accounts.close()
    cur_cats.close()
    cur_inc.close()
    conn.close()

    return render_template(
        "finance/income_entry.html",
        title="Income Entry",
        accounts=accounts,
        categories=categories,
        income_rows=income_rows,
        from_date=from_date,
        to_date=to_date,
        category_filter=category_filter,
    )


# ---------------------------------------
# Delete Income (no opening_balance revert)
# ---------------------------------------
@finance_bp.route("/finance/income/delete/<string:tx_id>", methods=["POST"])
def delete_income(tx_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_mysql_connection()
    if not conn:
        flash("DB connection failed", "danger")
        return redirect(url_for("finance.income_entry"))

    cur = conn.cursor(dictionary=True)
    try:
        # get transaction
        cur.execute("""
            SELECT account_id, amount
            FROM finance_transactions
            WHERE id=%s AND transaction_type='INCOME'
        """, (tx_id,))
        row = cur.fetchone()
        if not row:
            flash("Income record not found.", "danger")
        else:
            # only delete transaction; balances come from ledger logic
            cur.execute("DELETE FROM finance_transactions WHERE id=%s", (tx_id,))
            conn.commit()
            flash("🗑 Income deleted.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"❌ Delete income error: {e}", "danger")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("finance.income_entry"))

# ---------------------------------------
# 📊 Finance Reports – Main Page
# ---------------------------------------
@finance_bp.route("/finance/reports")
def finance_reports_page():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("finance/ledger_reports.html")


# ---------------------------------------
# 📌 API – Accounts for dropdown
#    (IF you already have this route, do NOT duplicate it)
# ---------------------------------------
@finance_bp.route("/finance/api/accounts", methods=["GET"])
def api_finance_accounts():
    if not is_logged_in():
        return jsonify({"success": False}), 401

    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    try:
        conn.ping(reconnect=True)
    except:
        conn = get_mysql_connection()
        cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, account_name, account_type
        FROM bank_accounts
        ORDER BY account_type, account_name
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify({"success": True, "accounts": rows})

# ---------------------------------------
# 📌 API – Expense Categories for Filters
# ---------------------------------------
@finance_bp.route("/finance/api/expense-categories")
def api_expense_categories():
    if not is_logged_in():
        return jsonify({"success": False}), 401

    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, category_name AS name
        FROM expense_categories
        ORDER BY category_name
    """)
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return jsonify({"success": True, "categories": rows})


# ---------------------------------------
# 📌 API – Income Categories for Filters
# ---------------------------------------
@finance_bp.route("/finance/api/income-categories")
def api_income_categories():
    if not is_logged_in():
        return jsonify({"success": False}), 401

    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, category_name AS name
        FROM income_categories
        WHERE is_active = 1
        ORDER BY category_name
    """)
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return jsonify({"success": True, "categories": rows})

# ---------------------------------------
# 🧮 Helper – Build ledger response
# ---------------------------------------
def build_ledger_response(rows, opening_balance):
    """
    Correct opening balance handling:
    - Start from actual DB stored opening_balance
    - DO NOT add any first transaction inside filtered date range into opening
    """
    if opening_balance is None:
        opening_balance = 0.0

    balance = float(opening_balance)
    total_in = 0.0
    total_out = 0.0

    for r in rows:
        amt = float(r.get("amount") or 0)
        tx_type = (r.get("transaction_type") or "").upper()

        # Format display date
        txd = r.get("tx_date")
        try:
            if isinstance(txd, (datetime, date)):
                r["display_date"] = txd.strftime("%d-%m-%Y")
            else:
                r["display_date"] = datetime.strptime(str(txd), "%Y-%m-%d").strftime("%d-%m-%Y")
        except:
            r["display_date"] = str(txd)

        # Apply as running transactions (NOT opening)
        if tx_type in ("INCOME", "DEPOSIT"):
            total_in += amt
            balance += amt
            r["in_amount"] = amt
            r["out_amount"] = 0.0
        else:
            total_out += amt
            balance -= amt
            r["in_amount"] = 0.0
            r["out_amount"] = amt

        r["running_balance"] = balance

    return jsonify({
        "opening_balance": round(opening_balance, 2),
        "total_in": round(total_in, 2),
        "total_out": round(total_out, 2),
        "closing_balance": round(balance, 2),
        "rows": rows
    })

# ---------------------------------------
# 💵 CASH report API
# ---------------------------------------
@finance_bp.route("/finance/api/cash-report")
def api_cash_report():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    account_id = request.args.get("account_id")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    tx_type = (request.args.get("tx_type") or "ALL").upper()
    income_cat = request.args.get("income_cat") or "ALL"
    expense_cat = request.args.get("expense_cat") or "ALL"

    if not account_id or not from_date or not to_date:
        return jsonify({"error": "Missing filters"}), 400

    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    try:
        conn.ping(reconnect=True)
    except:
        conn = get_mysql_connection()
        cur = conn.cursor(dictionary=True)

    # Opening balance (static opening_balance + transactions BEFORE from_date)
    cur.execute("""
    SELECT 
        COALESCE(ba.opening_balance, 0)
        +
        COALESCE(SUM(
            CASE 
                WHEN ft.transaction_type IN ('INCOME','DEPOSIT') THEN ft.amount
                ELSE -ft.amount
            END
        ), 0) AS opening
    FROM bank_accounts ba
    LEFT JOIN finance_transactions ft 
        ON ba.id = ft.account_id
        AND ft.transaction_mode='CASH'
        AND ft.tx_date < %s
    WHERE ba.id=%s
    """, (from_date, account_id))

    opening = float(cur.fetchone()["opening"] or 0)

    # Transactions
    query = """
        SELECT id, tx_date, transaction_type, amount, description,
               receipt_no, payment_mode, category, income_category,
               utr_no, attachment_url
        FROM finance_transactions
        WHERE transaction_mode='CASH'
          AND account_id=%s
          AND tx_date BETWEEN %s AND %s
    """
    params = [account_id, from_date, to_date]

    if tx_type != "ALL":
        query += " AND transaction_type=%s"
        params.append(tx_type)

    if tx_type == "INCOME" and income_cat != "ALL":
        query += " AND income_category=%s"
        params.append(income_cat)

    if tx_type == "EXPENSE" and expense_cat != "ALL":
        query += " AND category=%s"
        params.append(expense_cat)

    query += " ORDER BY tx_date ASC, id ASC"

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return build_ledger_response(rows, opening)


# ---------------------------------------
# 🏦 BANK report API
# ---------------------------------------
@finance_bp.route("/finance/api/bank-report")
def api_bank_report():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    account_id = request.args.get("account_id")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    tx_type = (request.args.get("tx_type") or "ALL").upper()
    income_cat = request.args.get("income_cat") or "ALL"
    expense_cat = request.args.get("expense_cat") or "ALL"

    if not account_id or not from_date or not to_date:
        return jsonify({"error": "Missing filters"}), 400

    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    try:
        conn.ping(reconnect=True)
    except:
        conn = get_mysql_connection()
        cur = conn.cursor(dictionary=True)

    # Opening balance (static opening_balance + transactions BEFORE from_date)
    cur.execute("""
    SELECT 
        COALESCE(ba.opening_balance, 0)
        +
        COALESCE(SUM(
            CASE 
                WHEN ft.transaction_type IN ('INCOME','DEPOSIT') THEN ft.amount
                ELSE -ft.amount
            END
        ), 0) AS opening
    FROM bank_accounts ba
    LEFT JOIN finance_transactions ft 
        ON ba.id = ft.account_id
        AND ft.transaction_mode='BANK'
        AND ft.tx_date < %s
    WHERE ba.id=%s
    """, (from_date, account_id))

    opening = float(cur.fetchone()["opening"] or 0)

    # Transactions
    query = """
        SELECT id, tx_date, transaction_type, amount, description,
               receipt_no, payment_mode, category, income_category,
               utr_no, attachment_url
        FROM finance_transactions
        WHERE transaction_mode='BANK'
          AND account_id=%s
          AND tx_date BETWEEN %s AND %s
    """
    params = [account_id, from_date, to_date]

    if tx_type != "ALL":
        query += " AND transaction_type=%s"
        params.append(tx_type)

    if tx_type == "INCOME" and income_cat != "ALL":
        query += " AND income_category=%s"
        params.append(income_cat)

    if tx_type == "EXPENSE" and expense_cat != "ALL":
        query += " AND category=%s"
        params.append(expense_cat)

    query += " ORDER BY tx_date ASC, id ASC"

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return build_ledger_response(rows, opening)

# ---------------------------------------
# 📱 MOBILE API - Cash & Bank Accounts CRUD
# ---------------------------------------

@finance_bp.route("/api/mobile/finance/accounts", methods=["GET"])
def mobile_get_accounts():
    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            ba.id,
            ba.account_type,
            ba.account_name,
            ba.account_holder_name,
            ba.account_number,
            ba.ifsc_code,
            ba.branch_name,
            ba.opening_balance,
            COALESCE((
                ba.opening_balance + (
                    SELECT SUM(
                        CASE 
                            WHEN ft.transaction_type IN ('INCOME','DEPOSIT') THEN ft.amount
                            ELSE -ft.amount
                        END
                    )
                    FROM finance_transactions ft
                    WHERE ft.account_id = ba.id
                )
            ), ba.opening_balance) AS closing_balance
        FROM bank_accounts ba
        ORDER BY ba.id DESC
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "data": rows
    }), 200

@finance_bp.route("/api/mobile/finance/accounts", methods=["POST"])
def mobile_add_account():
    data = request.json or {}

    required = ["account_type", "account_name", "opening_balance"]
    if any(k not in data for k in required):
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    conn = get_mysql_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO bank_accounts
        (account_type, account_name, account_holder_name, account_number,
         ifsc_code, branch_name, opening_balance)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        data.get("account_type"),
        data.get("account_name"),
        data.get("account_holder_name"),
        data.get("account_number"),
        data.get("ifsc_code"),
        data.get("branch_name"),
        data.get("opening_balance"),
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "message": "Account created"}), 201


@finance_bp.route("/api/mobile/finance/accounts/<int:account_id>", methods=["PUT"])
def mobile_update_account(account_id):
    data = request.json or {}
    conn = get_mysql_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE bank_accounts SET
            account_type=%s,
            account_name=%s,
            account_holder_name=%s,
            account_number=%s,
            ifsc_code=%s,
            branch_name=%s,
            opening_balance=%s
        WHERE id=%s
    """, (
        data.get("account_type"),
        data.get("account_name"),
        data.get("account_holder_name"),
        data.get("account_number"),
        data.get("ifsc_code"),
        data.get("branch_name"),
        data.get("opening_balance"),
        account_id
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "message": "Account updated"}), 200


@finance_bp.route("/api/mobile/finance/accounts/<int:account_id>", methods=["DELETE"])
def mobile_delete_account(account_id):
    conn = get_mysql_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM bank_accounts WHERE id=%s", (account_id,))
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"success": True, "message": "Account deleted"}), 200

# ---------------------------------------------
# 📱 MOBILE: Add Bank Deposit
# ---------------------------------------------
@finance_bp.route("/api/mobile/finance/bank-deposit", methods=["POST"])
def mobile_bank_deposit():
    data = request.form.to_dict()  # Because Flutter sends multipart
    file = request.files.get("attachment")

    required = ["account_id", "amount", "description", "tx_date"]
    if any(x not in data or not data[x] for x in required):
        return jsonify({"success": False, "message": "Missing fields"}), 400

    conn = get_mysql_connection()
    cur = conn.cursor()

    tx_id = uuid.uuid4().hex
    attachment_url = None

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{tx_id}_{file.filename}")
        upload_dir = current_app.config["UPLOAD_FOLDER_FINANCE"]
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, filename))
        attachment_url = filename

    try:
        cur.execute("""
            INSERT INTO finance_transactions
            (id, account_id, transaction_mode, transaction_type, amount, 
             description, attachment_url, tx_date)
            VALUES (%s, %s, 'BANK', 'DEPOSIT', %s, %s, %s, %s)
        """, (
            tx_id,
            data["account_id"],
            data["amount"],
            data["description"],
            attachment_url,
            data["tx_date"]
        ))

        conn.commit()
        return jsonify({"success": True, "message": "Deposit Added"}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        cur.close()
        conn.close()

# ---------------------------------------------
# 📱 MOBILE: Bank Deposit History (with filters)
# ---------------------------------------------
@finance_bp.route("/api/mobile/finance/bank-deposit/history", methods=["GET"])
def mobile_bank_deposit_history():
    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    from_date = request.args.get("from_date")  # 'YYYY-MM-DD' or None
    to_date = request.args.get("to_date")      # 'YYYY-MM-DD' or None
    account_id = request.args.get("account_id")

    query = """
        SELECT 
            ft.id,
            ft.account_id,
            ba.account_name,
            ft.amount,
            ft.description,
            ft.tx_date,
            ft.attachment_url
        FROM finance_transactions ft
        JOIN bank_accounts ba ON ft.account_id = ba.id
        WHERE ft.transaction_type = 'DEPOSIT'
          AND ft.transaction_mode = 'BANK'
    """

    values = []

    if account_id:
        query += " AND ft.account_id = %s"
        values.append(account_id)

    if from_date:
        query += " AND ft.tx_date >= %s"
        values.append(from_date)

    if to_date:
        query += " AND ft.tx_date <= %s"
        values.append(to_date)

    query += " ORDER BY ft.tx_date DESC LIMIT 200"

    cur.execute(query, tuple(values))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify({"success": True, "data": rows}), 200

# ---------------------------------------------
# 📱 MOBILE: Delete Bank Deposit
# ---------------------------------------------
@finance_bp.route("/api/mobile/finance/bank-deposit/<string:tx_id>", methods=["DELETE"])
def mobile_bank_deposit_delete(tx_id):
    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    # Check transaction exists and is a BANK DEPOSIT
    cur.execute("""
        SELECT id, attachment_url
        FROM finance_transactions
        WHERE id = %s AND transaction_type = 'DEPOSIT' AND transaction_mode = 'BANK'
    """, (tx_id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "Deposit not found"}), 404

    attachment_url = row.get("attachment_url")

    try:
        # Delete record
        cur.execute("DELETE FROM finance_transactions WHERE id = %s", (tx_id,))
        conn.commit()

        # Optionally delete file from disk
        if attachment_url:
            upload_dir = current_app.config.get("UPLOAD_FOLDER_FINANCE")
            if upload_dir:
                file_path = os.path.join(upload_dir, attachment_url)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        # Don't fail API just because file delete failed
                        pass

        return jsonify({"success": True, "message": "Deposit deleted"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        cur.close()
        conn.close()
# ---------------------------------------------
# 📱 MOBILE: Edit / Update Bank Deposit
# ---------------------------------------------
@finance_bp.route("/api/mobile/finance/bank-deposit/<string:tx_id>", methods=["PUT", "POST"])
def mobile_bank_deposit_update(tx_id):
    """
    Accepts either:
    - multipart/form-data (Flutter Dio with file)
      -> request.form + request.files
    - application/json (no file)
      -> request.json
    """
    conn = get_mysql_connection()
    cur = conn.cursor(dictionary=True)

    # Check deposit exists
    cur.execute("""
        SELECT id, attachment_url
        FROM finance_transactions
        WHERE id = %s AND transaction_type = 'DEPOSIT' AND transaction_mode = 'BANK'
    """, (tx_id,))
    existing = cur.fetchone()

    if not existing:
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "Deposit not found"}), 404

    old_attachment = existing.get("attachment_url")

    # Detect content type
    content_type = (request.content_type or "").lower()
    is_multipart = "multipart/form-data" in content_type

    if is_multipart:
        data = request.form.to_dict()
        file = request.files.get("attachment")
    else:
        data = request.json or {}
        file = None

    # Allow partial update, but at least amount or description or date or account must exist
    if not any(k in data for k in ["amount", "description", "tx_date", "account_id"]) and not file:
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "No fields to update"}), 400

    # Prepare update parts
    fields = []
    values = []

    if "account_id" in data and data["account_id"]:
        fields.append("account_id = %s")
        values.append(data["account_id"])

    if "amount" in data and data["amount"]:
        fields.append("amount = %s")
        values.append(data["amount"])

    if "description" in data:
        fields.append("description = %s")
        values.append(data.get("description") or "")

    if "tx_date" in data and data["tx_date"]:
        fields.append("tx_date = %s")
        values.append(data["tx_date"])

    # Handle attachment (replace old if new uploaded)
    new_attachment = old_attachment
    if file and allowed_file(file.filename):
        tx_prefix = tx_id or uuid.uuid4().hex  # reuse id
        filename = secure_filename(f"{tx_prefix}_{file.filename}")
        upload_dir = current_app.config["UPLOAD_FOLDER_FINANCE"]
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, filename))

        new_attachment = filename
        fields.append("attachment_url = %s")
        values.append(new_attachment)

        # Optionally delete old file
        if old_attachment:
            try:
                old_path = os.path.join(upload_dir, old_attachment)
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception:
                pass

    if not fields:  # nothing changed
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "Nothing to update"}), 400

    values.append(tx_id)
    query = f"""
        UPDATE finance_transactions
        SET {", ".join(fields)}
        WHERE id = %s AND transaction_type = 'DEPOSIT' AND transaction_mode = 'BANK'
    """

    try:
        cur.execute(query, tuple(values))
        conn.commit()
        return jsonify({"success": True, "message": "Deposit updated"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        cur.close()
        conn.close()
@finance_bp.route('/finance/attachment/<filename>')
def finance_attachment(filename):
    return send_from_directory(
        current_app.config['UPLOAD_FOLDER_FINANCE'],
        filename,
        as_attachment=False
    )
