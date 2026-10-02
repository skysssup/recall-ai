"""Local boundary: auth, CORS origins, settings token non-disclosure."""

from app.config import settings
from app.main import app


def test_export_requires_auth(raw_client):
    r = raw_client.get("/api/export")
    assert r.status_code == 401


def test_delete_requires_auth(client, raw_client):
    created = client.post(
        "/api/problems",
        json={"title": "Auth Delete", "slug": "auth-delete", "platform": "manual"},
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    denied = raw_client.delete(f"/api/problems/{pid}")
    assert denied.status_code == 401
    ok = client.delete(f"/api/problems/{pid}")
    assert ok.status_code == 200


def test_settings_requires_auth_and_hides_token(client, raw_client):
    denied = raw_client.get("/api/settings")
    assert denied.status_code == 401
    ok = client.get("/api/settings")
    assert ok.status_code == 200
    body = ok.json()
    assert "api_token" not in body
    assert body["api_token_configured"] is True
    assert body["api_token_hint"].startswith("…")
    assert settings.api_token not in body.values()


def test_cors_allows_configured_origin_only(client):
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    rejected = client.get(
        "/api/health",
        headers={"Origin": "http://evil.example"},
    )
    assert rejected.headers.get("access-control-allow-origin") is None

    # Wildcard extension / random localhost ports must not match.
    ext = client.get(
        "/api/health",
        headers={"Origin": "chrome-extension://abcdefghijklmnop"},
    )
    assert ext.headers.get("access-control-allow-origin") is None

    random_port = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:9999"},
    )
    assert random_port.headers.get("access-control-allow-origin") is None


def test_cors_origins_config_has_no_wildcards():
    assert all("*" not in o for o in settings.cors_origins)
    # Middleware was configured without allow_origin_regex.
    middlewares = [m.cls.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in middlewares
