from datetime import datetime, timedelta, timezone

import pytest

from app.scheduler import (
    RATING_AGAIN,
    RATING_EASY,
    RATING_GOOD,
    RATING_HARD,
    apply_review,
    forecast_due_counts,
    interval_days,
    priority_score,
    recall_from_solve,
    retrievability,
)


def test_retrievability_fresh_is_high():
    now = datetime(2026, 1, 1)
    r = retrievability(10.0, now, now)
    assert r == 1.0


def test_retrievability_decays_with_time():
    last = datetime(2026, 1, 1)
    later = last + timedelta(days=30)
    r = retrievability(5.0, last, later)
    assert 0.0 < r < 1.0


def test_interval_positive():
    assert interval_days(2.0) > 0


def test_again_reduces_stability():
    state = apply_review(stability=10.0, difficulty=5.0, rating=RATING_AGAIN, review_count=3)
    assert state.stability < 10.0
    assert state.lapses == 1


def test_good_grows_stability_after_first():
    first = apply_review(stability=1.0, difficulty=5.0, rating=RATING_GOOD, review_count=0)
    second = apply_review(
        stability=first.stability,
        difficulty=first.difficulty,
        rating=RATING_GOOD,
        review_count=first.review_count,
        last_review=first.last_reviewed_at,
        current=first.last_reviewed_at + timedelta(days=2),
    )
    assert second.stability >= first.stability


def test_easy_grows_faster_than_hard():
    easy = apply_review(stability=5.0, difficulty=5.0, rating=RATING_EASY, review_count=2)
    hard = apply_review(stability=5.0, difficulty=5.0, rating=RATING_HARD, review_count=2)
    assert easy.stability > hard.stability


def test_invalid_rating():
    try:
        apply_review(1.0, 5.0, rating=9)
        assert False
    except ValueError:
        pass


def test_recall_from_solve_accepted_fast():
    strength, rating = recall_from_solve(30, 60, 1, 0, "Accepted", "Easy")
    assert strength > 0.7
    assert rating >= RATING_GOOD


def test_recall_from_solve_failed():
    strength, rating = recall_from_solve(600, 900, 5, 2, "Wrong Answer", "Hard")
    assert strength < 0.5
    assert rating <= RATING_HARD


def test_priority_overdue_higher():
    now = datetime(2026, 6, 1)
    low = priority_score(0.95, 3.0, now + timedelta(days=5), now)
    high = priority_score(0.2, 8.0, now - timedelta(days=3), now)
    assert high > low


def test_preview_intervals_keys():
    from app.scheduler import preview_intervals

    now = datetime(2026, 3, 1)
    previews = preview_intervals(5.0, 5.0, review_count=2, current=now)
    assert set(previews.keys()) == {1, 2, 3, 4}
    assert previews[4] >= previews[3] >= previews[2]
    assert previews[1] < previews[2]


def test_is_leech():
    from app.scheduler import is_leech

    assert is_leech(8) is True
    assert is_leech(3, threshold=8) is False
    assert is_leech(3, threshold=3) is True


def test_forecast_due_counts_shape():
    from app.scheduler import forecast_due_counts

    now = datetime(2026, 4, 1)
    cards = [
        (1.0, now - timedelta(days=10), now - timedelta(days=1)),
        (30.0, now, now + timedelta(days=20)),
    ]
    series = forecast_due_counts(cards, days=7, current=now)
    assert len(series) == 7
    assert series[0]["due_count"] >= 1
    assert sum(d["due_count"] for d in series) >= 1


@pytest.mark.parametrize("current", [
    datetime(2026, 10, 3), datetime(2026, 10, 3, 14),
    datetime(2026, 10, 4, 1, tzinfo=timezone(timedelta(hours=11))),
])
def test_forecast_uses_utc_calendar_boundaries(current):
    tomorrow = datetime(2026, 10, 4)
    cards = [(1000, None, due) for due in (
        datetime(2026, 10, 1),
        tomorrow - timedelta(microseconds=1),
        tomorrow,
        tomorrow + timedelta(microseconds=1),
        tomorrow + timedelta(hours=8),
        datetime(2026, 10, 4, 5, 45, tzinfo=timezone(timedelta(hours=5, minutes=45))),
        datetime(2026, 10, 5),
        datetime(2026, 10, 6),
        None,
    )]
    series = forecast_due_counts(cards, days=3, current=current)
    assert series == [
        {"day_offset": 0, "date": "2026-10-03", "due_count": 3},
        {"day_offset": 1, "date": "2026-10-04", "due_count": 4},
        {"day_offset": 2, "date": "2026-10-05", "due_count": 1},
    ]


def test_forecast_buckets_decay_by_calendar_day():
    now = datetime(2026, 10, 3, 14)
    threshold_at = datetime(2026, 10, 4)
    last_review = threshold_at - timedelta(days=interval_days(1))
    cards = [(1, last_review, datetime(2026, 12, 1))]
    series = forecast_due_counts(cards, days=3, current=now)
    assert [day["due_count"] for day in series] == [0, 1, 0]
