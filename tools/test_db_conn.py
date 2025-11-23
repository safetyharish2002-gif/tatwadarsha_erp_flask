import os
import sys
from dotenv import load_dotenv

# Add project root to PATH
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from app.db import get_db

def main():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        print("Connected to database:", cursor.fetchone())
        cursor.close()
        conn.close()
        print("Connection test: SUCCESS")
    except Exception as e:
        print("Connection test: FAILED")
        print(e)

if __name__ == "__main__":
    main()
