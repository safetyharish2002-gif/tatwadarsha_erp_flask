# FILE: app/db.py

import mysql.connector
from mysql.connector import pooling, Error
from dotenv import load_dotenv
import os

# Load env
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

DB_HOST = os.getenv("MYSQL_HOST", "srv366.hstgr.io")
DB_USER = os.getenv("MYSQL_USER", "u514260654_testerp")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "Tions@98")
DB_NAME = os.getenv("MYSQL_DB", "u514260654_test_erp")
DB_PORT = int(os.getenv("MYSQL_PORT", 3306))


# ============================
# Try SINGLE TEST CONNECTION
# ============================
def test_single_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            connection_timeout=5,
        )
        conn.close()
        return True
    except Exception as e:
        print("❌ Single MySQL connection failed:", e)
        return False


# ============================
# SAFE POOL CREATION
# ============================
connection_pool = None

if test_single_connection():   # only build pool if DB is reachable
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="erp_pool",
            pool_size=3,     # 🔥 Hostinger shared DB cannot handle 10!
            pool_reset_session=True,
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            connection_timeout=5,
        )
        print("✅ MySQL Pool Created Successfully")

    except Error as e:
        print("❌ Failed to create pool:", e)
else:
    print("❌ Pool disabled — DB unreachable.")


# ============================
# GET CONNECTION (Failsafe)
# ============================
def get_mysql_connection():
    try:
        if connection_pool:
            return connection_pool.get_connection()

        # fallback
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            connection_timeout=5,
        )
    except Error as e:
        print("❌ MySQL Get Connection Error:", e)
        return None
