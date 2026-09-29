from datetime import datetime, timedelta

from app.scheduler import (
    RATING_AGAIN,
    RATING_EASY,
    RATING_GOOD,
    RATING_HARD,
    apply_review,
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
