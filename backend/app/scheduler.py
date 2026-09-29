"""
Recall scheduler — a compact spaced-repetition engine.

Public FSRS uses a multi-parameter model. Here we keep a small, transparent
set of knobs that are easy to reason about and unit-test:

  R(t) = (1 + t / (9 * S)) ** (-w)     # retrievability at elapsed days t
  S'   = update(S, D, rating)          # stability after a review
  D'   = clamp(D + delta(rating))      # difficulty after a review
  due  = now + interval_days(S', R_target)

Ratings: 1=Again, 2=Hard, 3=Good, 4=Easy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import exp
from typing import Optional

RATING_AGAIN = 1
RATING_HARD = 2
RATING_GOOD = 3
RATING_EASY = 4

DECAY_EXPONENT = 0.5
TARGET_RETRIEVABILITY = 0.9
STABILITY_MIN = 0.1
STABILITY_MAX = 3650.0
DIFFICULTY_MIN = 1.0
DIFFICULTY_MAX = 10.0

# Growth multipliers relative to current stability (Good is baseline).
_GROWTH = {
    RATING_HARD: 1.15,
    RATING_GOOD: 1.80,
    RATING_EASY: 2.60,
}
_DIFFICULTY_DELTA = {
    RATING_AGAIN: 1.2,
    RATING_HARD: 0.4,
    RATING_GOOD: 0.0,
    RATING_EASY: -0.8,
}


def _now(current: Optional[datetime] = None) -> datetime:
    if current is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if current.tzinfo is not None:
        return current.astimezone(timezone.utc).replace(tzinfo=None)
    return current


def elapsed_days(last_review: Optional[datetime], current: Optional[datetime] = None) -> float:
    if last_review is None:
        return 0.0
    now = _now(current)
    lr = last_review
    if lr.tzinfo is not None:
        lr = lr.astimezone(timezone.utc).replace(tzinfo=None)
    return max(0.0, (now - lr).total_seconds() / 86400.0)


def retrievability(
    stability: float,
    last_review: Optional[datetime],
    current: Optional[datetime] = None,
    decay: float = DECAY_EXPONENT,
) -> float:
    """Probability the learner still remembers, given stability and last review."""
    s = max(STABILITY_MIN, stability)
    t = elapsed_days(last_review, current)
    r = (1.0 + t / (9.0 * s)) ** (-max(0.01, decay))
    return max(0.0, min(1.0, r))


def interval_days(stability: float, target_r: float = TARGET_RETRIEVABILITY) -> float:
    """Days until retrievability falls to target_r, solved from the R formula."""
    s = max(STABILITY_MIN, stability)
    target = min(0.99, max(0.01, target_r))
    # R = (1 + t/(9S))^(-w)  =>  t = 9S * (R^(-1/w) - 1)
    return 9.0 * s * (target ** (-1.0 / DECAY_EXPONENT) - 1.0)


def _clamp_s(s: float) -> float:
    return max(STABILITY_MIN, min(STABILITY_MAX, s))


def _clamp_d(d: float) -> float:
    return max(DIFFICULTY_MIN, min(DIFFICULTY_MAX, d))


@dataclass
class CardState:
    stability: float
    difficulty: float
    retrievability: float
    due_at: datetime
    last_reviewed_at: datetime
    review_count: int
    lapses: int


def apply_review(
    stability: float,
    difficulty: float,
    rating: int,
    review_count: int = 0,
    lapses: int = 0,
    last_review: Optional[datetime] = None,
    current: Optional[datetime] = None,
) -> CardState:
    """Return the next card state after a review rating."""
    if rating not in (RATING_AGAIN, RATING_HARD, RATING_GOOD, RATING_EASY):
        raise ValueError(f"invalid rating: {rating}")

    now = _now(current)
    d = _clamp_d(difficulty + _DIFFICULTY_DELTA[rating])
    # Harder cards grow stability more slowly.
    difficulty_factor = max(1.0, d) ** -0.25

    if rating == RATING_AGAIN:
        new_s = _clamp_s(stability * 0.35)
        lapses += 1
        # Relearn: due roughly half a day later
        due = now + timedelta(hours=12)
    else:
        # First successful review gets a short fixed interval so cold-start
        # cards don't jump weeks ahead.
        if review_count == 0:
            base = {RATING_HARD: 0.5, RATING_GOOD: 1.0, RATING_EASY: 3.0}[rating]
            new_s = _clamp_s(base)
        else:
            growth = _GROWTH[rating] * difficulty_factor
            # Slight bonus if the card was still highly retrievable (easy win).
            r_before = retrievability(stability, last_review, now)
            bonus = 1.0 + 0.15 * max(0.0, r_before - TARGET_RETRIEVABILITY)
            new_s = _clamp_s(stability * growth * bonus)
        due = now + timedelta(days=max(0.05, interval_days(new_s)))

    r_now = retrievability(new_s, now, now)
    return CardState(
        stability=round(new_s, 4),
        difficulty=round(d, 4),
        retrievability=round(r_now, 4),
        due_at=due,
        last_reviewed_at=now,
        review_count=review_count + 1,
        lapses=lapses,
    )


def forgetting_risk(retrievability_value: float) -> float:
    """1 - R, clamped."""
    return max(0.0, min(1.0, 1.0 - retrievability_value))


def priority_score(
    retrievability_value: float,
    difficulty: float,
    due_at: Optional[datetime],
    current: Optional[datetime] = None,
) -> float:
    """
    Higher = review sooner. Combines overdue urgency, low R, and high difficulty.
    Used to order the revision queue.
    """
    now = _now(current)
    overdue_days = 0.0
    if due_at is not None:
        da = due_at if due_at.tzinfo is None else due_at.astimezone(timezone.utc).replace(tzinfo=None)
        overdue_days = max(0.0, (now - da).total_seconds() / 86400.0)
    return (
        2.5 * forgetting_risk(retrievability_value)
        + 0.15 * difficulty
        + 0.8 * overdue_days
        + 0.05 * (1.0 - exp(-overdue_days))
    )


def recall_from_solve(
    time_to_understand_s: Optional[int],
    time_to_write_s: Optional[int],
    num_submissions: int,
    hints_used: int,
    verdict: str,
    difficulty: str = "Medium",
) -> tuple[float, int]:
    """
    Map a captured solve into (recall_strength in [0,1], suggested rating 1-4).
    Baselines are rough global priors — good enough for first-pass automation.
    """
    priors = {
        "Easy": (90, 240),
        "Medium": (240, 480),
        "Hard": (480, 900),
    }
    u_mean, w_mean = priors.get(difficulty, priors["Medium"])
    score = 1.0

    if verdict and verdict.lower() not in ("accepted", "ac", "ok", "correct"):
        score -= 0.45

    if time_to_understand_s is not None and u_mean > 0:
        score -= 0.25 * max(0.0, (time_to_understand_s / u_mean) - 1.0)
    if time_to_write_s is not None and w_mean > 0:
        score -= 0.20 * max(0.0, (time_to_write_s / w_mean) - 1.0)

    score -= 0.12 * max(0, num_submissions - 1)
    score -= 0.15 * max(0, hints_used)
    strength = max(0.0, min(1.0, score))

    if strength < 0.30:
        rating = RATING_AGAIN
    elif strength < 0.55:
        rating = RATING_HARD
    elif strength < 0.80:
        rating = RATING_GOOD
    else:
        rating = RATING_EASY
    return strength, rating


def is_leech(lapses: int, threshold: int = 8) -> bool:
    """True when a card has lapsed enough times to need special attention."""
    return lapses >= max(1, threshold)


def preview_intervals(
    stability: float,
    difficulty: float,
    review_count: int = 0,
    lapses: int = 0,
    last_review: Optional[datetime] = None,
    current: Optional[datetime] = None,
) -> dict[int, float]:
    """
    Days until next due for each rating, without mutating card state.
    Useful for showing interval previews on the review UI.
    """
    now = _now(current)
    out: dict[int, float] = {}
    for rating in (RATING_AGAIN, RATING_HARD, RATING_GOOD, RATING_EASY):
        state = apply_review(
            stability=stability,
            difficulty=difficulty,
            rating=rating,
            review_count=review_count,
            lapses=lapses,
            last_review=last_review,
            current=now,
        )
        delta = (state.due_at - now).total_seconds() / 86400.0
        out[rating] = round(max(0.0, delta), 3)
    return out


def forecast_due_counts(
    cards: list[tuple[float, Optional[datetime], Optional[datetime]]],
    days: int = 14,
    current: Optional[datetime] = None,
) -> list[dict]:
    """
    Project how many cards would be due each day assuming no new reviews.

    Each card is (stability, last_reviewed_at, due_at).
    A card counts on the first day where due_at <= day_end or R < target.
    """
    now = _now(current)
    days = max(1, min(90, days))
    # day_offset -> set of card indices first due that day
    buckets: dict[int, set[int]] = {i: set() for i in range(days)}
    for idx, (stability, last_review, due_at) in enumerate(cards):
        for offset in range(days):
            day_end = now + timedelta(days=offset + 1)
            r = retrievability(stability, last_review, day_end)
            due = due_at is None or due_at <= day_end or r < TARGET_RETRIEVABILITY
            if due:
                buckets[offset].add(idx)
                break
    return [
        {
            "day_offset": i,
            "date": (now + timedelta(days=i)).date().isoformat(),
            "due_count": len(buckets[i]),
        }
        for i in range(days)
    ]
