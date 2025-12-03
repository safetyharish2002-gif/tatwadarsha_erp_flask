# path: app/jwt_utils.py
import jwt
import datetime

# ❗ Change this to a long random string later
SECRET_KEY = "TATWADARSHA_SUPER_SECRET_KEY_CHANGE_ME"

def generate_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=12),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def verify_token(token):
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return data   # e.g. {"user_id": 1, "exp": ...}
    except Exception:
        return None
