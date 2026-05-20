"""Signed session cookie auth for admin UI; X-Admin-Token kept for CLI."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Annotated

from fastapi import Header, HTTPException, Request

from config import ADMIN_PASSWORD, ADMIN_TOKEN, SESSION_MAX_AGE, SESSION_SECRET

SESSION_COOKIE_NAME = "singalong_session"


def create_session_token() -> str:
    payload = {"admin": True, "iat": int(time.time())}
    data = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()
    sig = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode()
    return f"{data}.{sig_b64}"


def verify_session_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    data, sig_b64 = token.rsplit(".", 1)
    try:
        expected = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).digest()
        padded = sig_b64 + "=" * (-len(sig_b64) % 4)
        actual = base64.urlsafe_b64decode(padded.encode())
    except (ValueError, json.JSONDecodeError):
        return False
    if not hmac.compare_digest(expected, actual):
        return False
    try:
        padded_data = data + "=" * (-len(data) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_data.encode()))
    except (ValueError, json.JSONDecodeError):
        return False
    iat = payload.get("iat", 0)
    if not isinstance(iat, int) or time.time() - iat > SESSION_MAX_AGE:
        return False
    return payload.get("admin") is True


def is_admin_request(
    request: Request,
    x_admin_token: str | None = None,
) -> bool:
    if x_admin_token and secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        return True
    return verify_session_token(request.cookies.get(SESSION_COOKIE_NAME))


def require_admin(
    request: Request,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> None:
    if not is_admin_request(request, x_admin_token):
        raise HTTPException(status_code=401, detail="Admin access required")


def verify_admin_password(password: str) -> bool:
    return secrets.compare_digest(password, ADMIN_PASSWORD)
