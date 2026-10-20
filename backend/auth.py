"""Password hashing and revocable opaque cookie sessions."""
import hashlib
import hmac
import os
import secrets
import time
from fastapi import Depends, HTTPException, Request
from .database import connect

ITERATIONS = 310_000
SESSION_COOKIE = "cinematch_session"
SESSION_SECONDS = 12 * 60 * 60


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt, expected = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",
                   (token_hash, user_id, int(time.time()) + SESSION_SECONDS))
    return token


def current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with connect() as db:
        row = db.execute("""SELECT u.id,u.name,u.email,u.role FROM sessions s
            JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?""",
            (token_hash, int(time.time()))).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    return dict(row)


def admin_user(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user


def set_session_cookie(response, token):
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=os.getenv("CINEMATCH_SECURE_COOKIE", "0") == "1",
                        samesite="lax", path="/")


def clear_session_cookie(response):
    response.delete_cookie(SESSION_COOKIE, httponly=True,
                           secure=os.getenv("CINEMATCH_SECURE_COOKIE", "0") == "1",
                           samesite="lax", path="/")
