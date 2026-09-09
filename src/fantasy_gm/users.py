"""User accounts: bcrypt password hashing + JWT session tokens.

Optional/additive auth — the app stays browsable in demo mode without an account;
signing in adds a per-user row (currently just a saved league format).
"""
import datetime as dt

import bcrypt
import jwt

from fantasy_gm.config import get_settings
from fantasy_gm.db import execute, fetch_one

_ALG = "HS256"
_MAX_PW_BYTES = 72  # bcrypt only hashes the first 72 bytes


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:_MAX_PW_BYTES], bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:_MAX_PW_BYTES], hashed.encode())
    except ValueError:
        return False


def make_token(user_id: int) -> str:
    payload = {"sub": str(user_id),
               "exp": dt.datetime.now(dt.UTC) + dt.timedelta(days=30)}
    return jwt.encode(payload, get_settings().secret_key, algorithm=_ALG)


def decode_token(token: str) -> int | None:
    try:
        p = jwt.decode(token, get_settings().secret_key, algorithms=[_ALG])
        return int(p["sub"])
    except Exception:
        return None


def create_user(email: str, password: str) -> dict:
    execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)",
            (email.lower(), hash_password(password)))
    return get_user_by_email(email)


def get_user_by_email(email: str) -> dict | None:
    return fetch_one("SELECT id, email, password_hash, league_format "
                     "FROM users WHERE email=%s", (email.lower(),))


def get_user_by_id(uid: int) -> dict | None:
    return fetch_one("SELECT id, email, password_hash, league_format "
                     "FROM users WHERE id=%s", (uid,))
