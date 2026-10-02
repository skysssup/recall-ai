"""Request authentication for the local-only Recall API."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from .config import settings


def extract_token(
    authorization: str | None = None,
    x_api_key: str | None = None,
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip() or None
    if x_api_key:
        return x_api_key.strip() or None
    return None


def require_api_token(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> str:
    token = extract_token(authorization, x_api_key)
    if not token or token != settings.api_token:
        raise HTTPException(401, "Invalid or missing API token")
    return token


def client_is_loopback(request: Request) -> bool:
    """True when the TCP peer is loopback (or the FastAPI TestClient)."""
    host = ""
    if request.client is not None:
        host = (request.client.host or "").strip().lower()
    if host in {"testclient", "localhost", "::1"} or host.startswith("127."):
        return True
    # Starlette TestClient sometimes reports as None/empty in middleware.
    if not host and request.headers.get("user-agent", "").startswith("testclient"):
        return True
    return False


def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "…"
    return "…" + token[-4:]
