from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TopicOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    stability: float
    difficulty: float
    retrievability: float
    practice_count: int
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    problem_count: int = 0
    prerequisites: list[str] = []
    dependents: list[str] = []

    model_config = {"from_attributes": True}


class ProblemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    platform: str = Field(default="manual", min_length=1, max_length=40)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=240)
    url: Optional[str] = None
    difficulty: str = "Medium"
    topic_name: Optional[str] = None
    tags: list[str] = []
    notes: str = ""


class ProblemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    url: Optional[str] = None
    difficulty: Optional[str] = None
    topic_name: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None


class ProblemOut(BaseModel):
    id: str
    title: str
    platform: str
    slug: str
    url: Optional[str] = None
    difficulty: str
    topic_id: Optional[str] = None
    topic_name: Optional[str] = None
    tags: list[str] = []
    notes: str = ""
    stability: float
    difficulty_score: float
    retrievability: float
    due_at: Optional[datetime] = None
    last_reviewed_at: Optional[datetime] = None
    review_count: int
    lapses: int
    created_at: datetime
    priority: float = 0.0

    model_config = {"from_attributes": True}


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=4)
    duration_sec: int = Field(default=0, ge=0)
    note: str = ""


class ReviewOut(BaseModel):
    id: str
    problem_id: str
    rating: int
    duration_sec: int
    note: str
    created_at: datetime
    next_due_at: Optional[datetime] = None
    stability: float
    retrievability: float

    model_config = {"from_attributes": True}


class SolveIn(BaseModel):
    client_event_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    platform: str = Field(default="manual", min_length=1, max_length=40)
    slug: str = Field(min_length=1, max_length=240)
    title: str = Field(default="", max_length=240)
    url: Optional[str] = None
    difficulty: str = "Medium"
    verdict: str = "Accepted"
    time_to_understand_s: Optional[int] = Field(default=None, ge=0)
    time_to_write_s: Optional[int] = Field(default=None, ge=0)
    num_submissions: int = Field(default=1, ge=1)
    hints_used: int = Field(default=0, ge=0)
    tags: list[str] = []
    topic_name: Optional[str] = None
    auto_review: bool = True


class SolveOut(BaseModel):
    id: str
    problem_id: Optional[str]
    platform: str
    slug: str
    title: str
    difficulty: str
    verdict: str
    time_to_understand_s: Optional[int]
    time_to_write_s: Optional[int]
    num_submissions: int
    hints_used: int
    tags: list[str]
    source: str
    created_at: datetime
    recall_strength: Optional[float] = None
    applied_rating: Optional[int] = None

    model_config = {"from_attributes": True}


class DashboardOut(BaseModel):
    due_count: int
    learned_count: int
    problem_count: int
    topic_count: int
    health_score: float
    streak_days: int
    reviews_today: int
    weak_topics: list[dict[str, Any]]
    upcoming: list[ProblemOut]
    recent_solves: list[SolveOut]
