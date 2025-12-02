from app.routers.master import get_db
from flask import session, jsonify
import uuid
from datetime import datetime
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

# -----------------------
# FINANCE ACCOUNTS API
# -----------------------
@finance_bp.route("/finance/api/accounts", methods=["GET"])
def api_finance_accounts():
    if not is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        conn = get_mysql_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT id, account_name, account_type 
            FROM bank_accounts 
            ORDER BY account_name
        """)
        rows = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify({"success": True, "accounts": rows})

    except Exception as e:
        print("❌ Error loading accounts:", e)
        return jsonify({"success": False, "message": str(e)})

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
            # Insert Transaction
            cur.execute("""
                INSERT INTO finance_transactions
                (id, account_id, transaction_mode, transaction_type, amount,
                 description, attachment_url, tx_date)
                VALUES (%s, %s, 'BANK', 'DEPOSIT', %s, %s, %s, %s)
            """, (tx_id, account_id, amount, description, attachment_url, tx_date))

            # Update Bank Balance
            cur.execute("""
                UPDATE bank_accounts SET opening_balance = opening_balance + %s
                WHERE id = %s
            """, (amount, account_id))

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
# Delete Bank Deposit (revert balance)
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
            account_id = tx["account_id"]
            amount = float(tx["amount"])

            # Revert bank balance
            cur.execute("""
                UPDATE bank_accounts
                SET opening_balance = opening_balance - %s
                WHERE id=%s
            """, (amount, account_id))

            # Delete record
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
            file.save(upload_path)
            attachment_url = filename

        try:
            cur.execute("""
                INSERT INTO finance_transactions
                (account_id, transaction_mode, transaction_type, amount,
                 description, attachment_url, tx_date)
                VALUES (%s, 'BANK', 'WITHDRAWAL', %s, %s, %s, %s)
            """, (account_id, amount, description, attachment_url, tx_date))

            cur.execute(
                "UPDATE bank_accounts SET opening_balance = opening_balance - %s WHERE id = %s",
                (amount, account_id)
            )
            cur.execute(
                "UPDATE bank_accounts SET opening_balance = opening_balance + %s WHERE id = %s",
                (amount, cash_account_id)
            )

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
# Delete Self Withdrawal (revert balance)
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
            account_id = tx["account_id"]
            amount = float(tx["amount"])

            # Revert BANK balance +
            cur.execute("""
                UPDATE bank_accounts
                SET opening_balance = opening_balance + %s
                WHERE id=%s
            """, (amount, account_id))

            # Revert CASH balance -
            cur.execute("""
                UPDATE bank_accounts
                SET opening_balance = opening_balance - %s
                WHERE account_type='CASH'
            """, (amount,))

            # Finally remove record
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
                old_account_id = old["account_id"]
                old_amount = float(old["amount"] or 0)
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
                        file.save(upload_path)
                        new_attach = filename
                    else:
                        new_attach = old_attach

                    # Adjust balances
                    if new_account_id == old_account_id:
                        # revert old, apply new
                        cur.execute(
                            """
                            UPDATE bank_accounts
                            SET opening_balance = opening_balance + %s - %s
                            WHERE id=%s
                        """,
                            (old_amount, new_amount, old_account_id),
                        )
                    else:
                        # revert old on old account
                        cur.execute(
                            """
                            UPDATE bank_accounts
                            SET opening_balance = opening_balance + %s
                            WHERE id=%s
                        """,
                            (old_amount, old_account_id),
                        )
                        # apply new on new account
                        cur.execute(
                            """
                            UPDATE bank_accounts
                            SET opening_balance = opening_balance - %s
                            WHERE id=%s
                        """,
                            (new_amount, new_account_id),
                        )

                    # Update transaction row
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
                    file.save(upload_path)
                    attachment_url = filename

                # insert transaction
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

                # reduce balance
                cur.execute(
                    """
                    UPDATE bank_accounts
                    SET opening_balance = opening_balance - %s
                    WHERE id=%s
                """,
                    (amount, account_id),
                )

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
# Delete Expense (revert balance)
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
            account_id = row["account_id"]
            amount = float(row["amount"] or 0)

            # revert balance
            cur.execute(
                """
                UPDATE bank_accounts
                SET opening_balance = opening_balance + %s
                WHERE id=%s
            """,
                (amount, account_id),
            )

            # delete transaction
            cur.execute("DELETE FROM finance_transactions WHERE id=%s", (tx_id,))
            conn.commit()
            flash("🗑 Expense deleted and balance updated.", "success")

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

                # insert transaction as INCOME
                cur.execute("""
                    INSERT INTO finance_transactions
                    (id, account_id, transaction_mode, transaction_type, amount, category,
                     description, attachment_url, tx_date)
                    VALUES (%s, %s, %s, 'INCOME', %s, %s, %s, %s, %s)
                """, (tx_id, account_id, mode, amount, category_name, description, attachment_url, tx_date))

                # increase balance
                cur.execute("""
                    UPDATE bank_accounts
                    SET opening_balance = opening_balance + %s
                    WHERE id=%s
                """, (amount, account_id))

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
# Delete Income (revert balance)
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
            account_id = row["account_id"]
            amount = float(row["amount"] or 0)

            # revert balance (account - amount)
            cur.execute("""
                UPDATE bank_accounts
                SET opening_balance = opening_balance - %s
                WHERE id=%s
            """, (amount, account_id))

            # delete transaction
            cur.execute("DELETE FROM finance_transactions WHERE id=%s", (tx_id,))
            conn.commit()
            flash("🗑 Income deleted and balance updated.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"❌ Delete income error: {e}", "danger")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("finance.income_entry"))
