# app/deps.py
from dotenv import load_dotenv
import os
from requests.utils import requote_uri
from itsdangerous import URLSafeSerializer, BadSignature

load_dotenv()

FIREBASE_URL = os.getenv("FIREBASE_URL", "").rstrip("/")
FIREBASE_AUTH = os.getenv("FIREBASE_AUTH", "").strip() or None
SECRET_KEY = os.getenv("SECRET_KEY", "secret-key")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")
STUDENTS_PATH = os.getenv("STUDENTS_PATH", "/erp/BSC NRSING/students")

serializer = URLSafeSerializer(SECRET_KEY, salt="erp-auth")

def firebase_url(path: str) -> str:
    """
    Build full firebase REST URL for a path. Path may include spaces.
    If path ends with .json, leave as-is; otherwise append .json
    """
    if not FIREBASE_URL:
        raise RuntimeError("FIREBASE_URL not set in .env")
    if not path.startswith("/"):
        path = "/" + path
    if not path.endswith(".json"):
        path = path + ".json"
    url = f"{FIREBASE_URL}{path}"
    url = requote_uri(url)
    if FIREBASE_AUTH:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}auth={FIREBASE_AUTH}"
    return url

# ---- auth helpers ----
COOKIE_NAME = "erp_auth"

def make_token(username: str) -> str:
    return serializer.dumps({"u": username})

def verify_token(token: str) -> str | None:
    try:
        data = serializer.loads(token)
        return data.get("u")
    except BadSignature:
        return None

def check_credentials(username: str, password: str) -> bool:
    return username == ADMIN_USER and password == ADMIN_PASS
