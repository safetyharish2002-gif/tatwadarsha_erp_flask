# ======================================
# FILE: app/mysql_config.py
# MYSQL VERSION – REPLACES firebase_config.py
# ======================================

import os
import mysql.connector
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ======================================
# 🔹 Create MySQL Connection
# ======================================
def get_db():
    """Return a new MySQL connection."""
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "srv366.hstgr.io"),
        user=os.getenv("MYSQL_USER", "u514260654_testerp"),
        password=os.getenv("MYSQL_PASSWORD", "Tions@98"),
        database=os.getenv("MYSQL_DATABASE", "u514260654_test_erp"),
        auth_plugin="mysql_native_password"
    )


# ======================================
# 🔹 Helper: Normalize master name
# ======================================
def normalize_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


# ======================================
# 🔹 Equivalent of master_ref() → Not needed in MySQL
#     (Because Firebase used nested nodes; MySQL uses tables)
# ======================================
# We do NOT return references. Instead, we use SQL directly.
# So this function is intentionally removed.


# ======================================
# 🔹 get_masters_list()  (REPLACEMENT)
#     Fetch dynamic master list from config_master_list TABLE
# ======================================
def get_masters_list():
    """
    Returns dict:
    {
        "religion": "Religion",
        "course": "Course",
        "department": "Department"
    }

    In MySQL:
      - Table: config_master_list
      - Columns: key_name, label
    """
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute("SELECT key_name, label FROM config_master_list ORDER BY label ASC")
        rows = cur.fetchall()

        cur.close()
        db.close()

        return {row["key_name"]: row["label"] for row in rows}

    except Exception as e:
        print("⚠️ MySQL error (get_masters_list):", e)
        return {}


# ======================================
# 🔹 add_master_item()  (REPLACEMENT)
#     Adds a row to config_master_list
#     AND ensures entry exists in 'masters' table
# ======================================
def add_master_item(key: str, label: str):
    """
    Add a new master entry into config_master_list.
    Also auto-creates entry in masters table (same as Firebase auto node creation).
    """
    key = normalize_key(key)

    try:
        db = get_db()
        cur = db.cursor(dictionary=True)

        # Insert into config_master_list
        cur.execute("""
            INSERT INTO config_master_list (key_name, label)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE label=%s
        """, (key, label, label))

        db.commit()

        # Ensure master exists in masters table
        cur.execute("SELECT id FROM masters WHERE master_name=%s", (key,))
        row = cur.fetchone()

        if not row:
            cur.execute("INSERT INTO masters (master_name) VALUES (%s)", (key,))
            db.commit()

        cur.close()
        db.close()

        print(f"✅ Added master '{key}' → '{label}'")

    except Exception as e:
        print("⚠️ MySQL error (add_master_item):", e)


# ======================================
# 🔹 delete_master_item()  (REPLACEMENT)
#     Removes row from config_master_list
#     Removes associated data from masters + master_items tables
# ======================================
def delete_master_item(key: str):
    """
    Delete from config_master_list AND
    remove all items for that master from master_items + masters table.
    """
    key = normalize_key(key)

    try:
        db = get_db()
        cur = db.cursor(dictionary=True)

        # 1. Delete from config master list
        cur.execute("DELETE FROM config_master_list WHERE key_name=%s", (key,))
        db.commit()

        # 2. Find master_id from masters table
        cur.execute("SELECT id FROM masters WHERE master_name=%s", (key,))
        row = cur.fetchone()

        if row:
            master_id = row["id"]

            # Delete associated items
            cur.execute("DELETE FROM master_items WHERE master_id=%s", (master_id,))
            db.commit()

            # Delete master
            cur.execute("DELETE FROM masters WHERE id=%s", (master_id,))
            db.commit()

        cur.close()
        db.close()

        print(f"🧹 Removed master '{key}' and all related items")

    except Exception as e:
        print("⚠️ MySQL error (delete_master_item):", e)
