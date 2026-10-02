import csv
import io

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth import client_is_loopback
from app.config import settings
from app.main import app
from app.models import Solve


@pytest.mark.parametrize("host", ["testclient", "localhost", "192.168.1.2", "", "127.evil"])
def test_peer_names_and_headers_do_not_bypass_loopback(host):
    request = Request({"type": "http", "client": (host, 123),
                       "headers": [(b"user-agent", b"testclient")]})
    assert not client_is_loopback(request)


def test_remote_peer_rejected_with_valid_token():
    with TestClient(app, client=("192.168.1.2", 123)) as client:
        assert client.get("/api/health", headers={"X-API-Key": settings.api_token}).status_code == 403


@pytest.mark.parametrize("replacement", [False, True])
def test_invalid_backup_is_atomic(client, replacement):
    client.post("/api/problems", json={"title": "Keep me", "slug": "keep"})
    before = client.get("/api/export").json()
    invalid = {**before, "problems": [{"slug": "valid"}, {"slug": "bad", "stability": -1}]}
    assert client.post("/api/import", json={"data": invalid, "merge": not replacement}).status_code == 400
    after = client.get("/api/export").json()
    assert before["problems"] == after["problems"]
    assert before["topics"] == after["topics"]


@pytest.mark.parametrize("changes", [{"problems": "wrong"}, {"version": 2},
    {"settings": {"daily_goal": "not-a-number"}}, {"reviews": [{"rating": 5}]},
    {"problems": [{"slug": "a"}, {"slug": "a"}]}])
def test_invalid_shapes_return_client_error(client, changes):
    bundle = {**client.get("/api/export").json(), **changes}
    assert client.post("/api/import", json={"data": bundle}).status_code == 400


def test_replacement_restores_dates_event_ids_and_cleared_fields(client, db):
    client.post("/api/capture/manual", json={"slug": "restore", "client_event_id": "event-123"})
    bundle = client.get("/api/export").json()
    record = bundle["problems"][0]
    record.update(notes="", tags=[], topic=None, due_at=None,
                  created_at="2025-01-01T10:00:00+05:45")
    client.post("/api/problems", json={"title": "Remove me", "slug": "remove"})
    assert client.post("/api/import", json={"data": bundle, "merge": False}).status_code == 200
    problems = client.get("/api/problems").json()
    assert [p["slug"] for p in problems] == ["restore"]
    assert problems[0]["created_at"] == "2025-01-01T04:15:00"
    assert problems[0]["due_at"] is None
    assert db.query(Solve).one().client_event_id == "event-123"
    assert client.post("/api/capture/manual", json={"slug": "restore", "client_event_id": "event-123"}).status_code == 200
    assert db.query(Solve).count() == 1
    assert client.post("/api/import", json={"data": bundle}).status_code == 200
    assert db.query(Solve).count() == 1


def test_merge_clears_notes_tags_and_null_dates(client):
    client.post("/api/problems", json={"title": "Merge", "slug": "merge", "notes": "old", "tags": ["old"]})
    bundle = client.get("/api/export").json()
    bundle["problems"][0].update(notes="", tags=[], due_at=None, topic=None)
    assert client.post("/api/import", json={"data": bundle}).status_code == 200
    p = client.get("/api/problems").json()[0]
    assert p["notes"] == "" and p["tags"] == [] and p["due_at"] is None


def test_csv_does_not_execute_formula_cells(client):
    client.post("/api/problems", json={"title": "=SUM(1,2)", "slug": "formula", "notes": "@command"})
    rows = list(csv.reader(io.StringIO(client.get("/api/export/csv").text)))
    assert rows[1][0] == "'=SUM(1,2)"
    assert rows[1][-1] == "'@command"


@pytest.mark.parametrize("route", ["/api/problems", "/api/reviews/queue", "/api/reviews/history", "/api/search"])
def test_negative_limits_are_rejected(client, route):
    assert client.get(route, params={"limit": -1}).status_code == 422


def test_negative_solve_and_review_durations_are_rejected(client):
    assert client.post("/api/capture/manual", json={"slug": "x", "hints_used": -1}).status_code == 422
    p = client.post("/api/problems", json={"title": "x"}).json()
    assert client.post(f"/api/problems/{p['id']}/reviews", json={"rating": 3, "duration_sec": -1}).status_code == 422


def test_replacement_rolls_back_on_write_failure(client, monkeypatch):
    from app.routers import export_import
    client.post("/api/problems", json={"title": "Original", "slug": "original"})
    before = client.get("/api/export").json()
    replacement = {**before, "problems": [{"slug": "replacement"}]}
    def fail(*args):
        raise RuntimeError("simulated storage failure")
    monkeypatch.setattr(export_import, "set_setting", fail)
    with pytest.raises(RuntimeError, match="simulated storage failure"):
        client.post("/api/import", json={"data": replacement, "merge": False})
    assert client.get("/api/export").json()["problems"] == before["problems"]


def test_partial_replacement_cannot_erase_history(client):
    assert client.post("/api/import", json={"data": {"problems": []}, "merge": False}).status_code == 400


def test_startup_rejects_shared_default_token(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "dev-token-change-me")
    with pytest.raises(RuntimeError, match="RECALL_API_TOKEN"):
        with TestClient(app, client=("127.0.0.1", 123)):
            pass
