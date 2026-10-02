"""Request authentication for the local-only Recall API."""

from __future__ import annotations

from ipaddress import ip_address
from secrets import compare_digest

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
    if not token or not compare_digest(token.encode(), settings.api_token.encode()):
        raise HTTPException(401, "Invalid or missing API token")
    return token


def client_is_loopback(request: Request) -> bool:
    """Accept only the actual loopback IP peer; headers cannot prove locality."""
    host = request.client.host if request.client else ""
    try:
        peer = ip_address(host)
        return peer.is_loopback or bool(getattr(peer, "ipv4_mapped", None) and peer.ipv4_mapped.is_loopback)
    except ValueError:
        return False



def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "…"
    return "…" + token[-4:]
