# tools/test_mysql.py
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("MYSQL_HOST")
user = os.getenv("MYSQL_USER")
pwd  = os.getenv("MYSQL_PASSWORD")
db   = os.getenv("MYSQL_DB") or os.getenv("MYSQL_DATABASE")

print("Testing connection to:", host, user, db)
conn = mysql.connector.connect(host=host, user=user, password=pwd, database=db, auth_plugin="mysql_native_password", connection_timeout=10)
print("Connected OK:", conn.server_version)
conn.close()
