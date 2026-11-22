"""Accounts: scrypt password hashes and signed, expiring bearer tokens (standard library only)."""
import base64
import hashlib
import hmac
import json
import os
import re
import time

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

TOKEN_TTL_SECONDS = 7 * 24 * 3600
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL.match(email)) and len(email) <= 254


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
        return hmac.compare_digest(candidate, bytes.fromhex(digest))
    except ValueError:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    return _b64(hmac.new(get_settings().auth_secret.encode(), body.encode(), hashlib.sha256).digest())


def create_token(user_id: int, now: float | None = None) -> str:
    payload = {"sub": user_id, "exp": int((now if now is not None else time.time()) + TOKEN_TTL_SECONDS)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"


def read_token(token: str, now: float | None = None) -> int | None:
    """The user id a token was issued for, or None if it is forged, malformed or expired."""
    try:
        body, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(body)):
            return None
        payload = json.loads(_unb64(body))
        if payload["exp"] < (now if now is not None else time.time()):
            return None
        return int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        return None


def current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db),
) -> User:
    scheme, _, token = (authorization or "").partition(" ")
    user_id = read_token(token) if scheme.lower() == "bearer" else None
    user = session.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


def find_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == normalize_email(email)))
