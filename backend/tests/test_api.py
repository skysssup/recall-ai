def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_topics_seeded(client):
    r = client.get("/api/topics")
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert "Arrays" in names
    assert "Dynamic Programming" in names


def test_graph(client):
    r = client.get("/api/topics/graph")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body and "edges" in body


def test_create_and_review_problem(client):
    r = client.post(
        "/api/problems",
        json={
            "title": "Two Sum",
            "platform": "leetcode",
            "slug": "two-sum",
            "difficulty": "Easy",
            "topic_name": "Arrays",
            "tags": ["array", "hash-table"],
            "notes": "Use a hashmap",
        },
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    r = client.post(f"/api/problems/{pid}/reviews", json={"rating": 3, "duration_sec": 120})
    assert r.status_code == 200
    body = r.json()
    assert body["rating"] == 3
    assert body["stability"] > 0
    assert body["next_due_at"] is not None


def test_review_queue_and_dashboard(client):
    client.post(
        "/api/problems",
        json={"title": "Valid Anagram", "slug": "valid-anagram", "topic_name": "Hash Table"},
    )
    q = client.get("/api/reviews/queue")
    assert q.status_code == 200
    assert len(q.json()) >= 1

    d = client.get("/api/dashboard")
    assert d.status_code == 200
    body = d.json()
    assert body["problem_count"] >= 1
    assert "health_score" in body


def test_search(client):
    client.post("/api/problems", json={"title": "Binary Tree Inorder", "slug": "inorder", "topic_name": "Trees"})
    r = client.get("/api/search", params={"q": "tree"})
    assert r.status_code == 200
    kinds = {h["kind"] for h in r.json()}
    assert "topic" in kinds or "problem" in kinds


def test_capture_requires_token(client, raw_client):
    r = raw_client.post(
        "/api/capture/solve",
        json={"platform": "leetcode", "slug": "two-sum", "title": "Two Sum", "verdict": "Accepted"},
    )
    assert r.status_code == 401

    r = client.post(
        "/api/capture/solve",
        json={
            "platform": "leetcode",
            "slug": "two-sum",
            "title": "Two Sum",
            "verdict": "Accepted",
            "time_to_understand_s": 40,
            "time_to_write_s": 90,
            "client_event_id": "evt-1",
            "tags": ["Array"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["applied_rating"] is not None

    # Idempotent replay
    r2 = client.post(
        "/api/capture/solve",
        json={
            "platform": "leetcode",
            "slug": "two-sum",
            "title": "Two Sum",
            "verdict": "Accepted",
            "client_event_id": "evt-1",
        },
        headers={"X-API-Key": "test-token"},
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == r.json()["id"]


def test_export_import(client):
    client.post("/api/problems", json={"title": "Climbing Stairs", "slug": "climbing-stairs", "topic_name": "Dynamic Programming"})
    exp = client.get("/api/export")
    assert exp.status_code == 200
    bundle = exp.json()
    assert bundle["version"] == 1
    assert len(bundle["problems"]) >= 1

    imp = client.post("/api/import", json={"data": bundle, "merge": True})
    assert imp.status_code == 200


def test_manual_solve(client):
    r = client.post(
        "/api/capture/manual",
        json={
            "platform": "manual",
            "slug": "house-robber",
            "title": "House Robber",
            "difficulty": "Medium",
            "verdict": "Accepted",
            "topic_name": "Dynamic Programming",
            "tags": ["Dynamic Programming"],
        },
    )
    assert r.status_code == 200


def test_forecast_and_csv_and_undo(client):
    created = client.post(
        "/api/problems",
        json={"title": "Merge Intervals", "slug": "merge-intervals", "topic_name": "Intervals"},
    )
    assert created.status_code == 201
    pid = created.json()["id"]

    r = client.post(f"/api/problems/{pid}/reviews", json={"rating": 3})
    assert r.status_code == 200

    forecast = client.get("/api/reviews/forecast", params={"days": 7})
    assert forecast.status_code == 200
    body = forecast.json()
    assert body["days"] == 7
    assert len(body["series"]) == 7

    preview = client.get(f"/api/reviews/preview/{pid}")
    assert preview.status_code == 200
    assert "3" in preview.json()["intervals_days"]

    csv_resp = client.get("/api/export/csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers.get("content-type", "")
    assert "Merge Intervals" in csv_resp.text

    undo = client.post("/api/reviews/undo", params={"problem_id": pid})
    assert undo.status_code == 200
    assert undo.json()["ok"] is True

    leeches = client.get("/api/reviews/leeches")
    assert leeches.status_code == 200
    assert isinstance(leeches.json(), list)


def test_daily_goal_validation(client):
    bad = client.post("/api/settings", json={"daily_goal": 0})
    assert bad.status_code == 400
    ok = client.post("/api/settings", json={"daily_goal": 7})
    assert ok.status_code == 200
    assert ok.json()["daily_goal"] == 7


def test_backup_round_trip_keeps_review_history(client):
    created = client.post(
        "/api/problems",
        json={"title": "Two Sum", "platform": "leetcode", "slug": "two-sum-backup", "difficulty": "Easy"},
    )
    assert created.status_code in (200, 201)
    pid = created.json()["id"]
    rev = client.post(f"/api/problems/{pid}/reviews", json={"rating": 3, "duration_sec": 12})
    assert rev.status_code in (200, 201)
    bundle = client.get("/api/export").json()
    assert any(r.get("problem_slug") == "two-sum-backup" for r in bundle.get("reviews", []))
    again = client.post("/api/import", json={"data": bundle, "merge": True})
    assert again.status_code == 200
    bundle2 = client.get("/api/export").json()
    reviews = [r for r in bundle2["reviews"] if r.get("problem_slug") == "two-sum-backup"]
    assert len(reviews) >= 1
