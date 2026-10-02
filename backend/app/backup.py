"""Validate backups completely before the importer mutates a database."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class TopicRecord(Record):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    stability: float = Field(default=1, gt=0, le=3650)
    difficulty: float = Field(default=5, ge=1, le=10)
    practice_count: int = Field(default=0, ge=0)
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None


class ProblemRecord(Record):
    platform: str = Field(default="manual", min_length=1, max_length=40)
    slug: str = Field(min_length=1, max_length=240)
    title: str = Field(default="", max_length=240)
    url: str | None = None
    difficulty: str = "Medium"
    topic: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    stability: float = Field(default=1, gt=0, le=3650)
    difficulty_score: float = Field(default=5, ge=1, le=10)
    review_count: int = Field(default=0, ge=0)
    lapses: int = Field(default=0, ge=0)
    due_at: datetime | None = None
    last_reviewed_at: datetime | None = None
    created_at: datetime | None = None


class ReviewRecord(Record):
    problem_platform: str
    problem_slug: str = Field(min_length=1)
    rating: int = Field(ge=1, le=4)
    duration_sec: int = Field(default=0, ge=0)
    note: str = ""
    created_at: datetime


class SolveRecord(Record):
    platform: str = Field(default="manual", min_length=1, max_length=40)
    slug: str = Field(min_length=1, max_length=240)
    title: str = ""
    difficulty: str = "Medium"
    verdict: str = "Accepted"
    time_to_understand_s: int | None = Field(default=None, ge=0)
    time_to_write_s: int | None = Field(default=None, ge=0)
    num_submissions: int = Field(default=1, ge=1)
    hints_used: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list)
    source: str = "import"
    client_event_id: str | None = Field(default=None, max_length=64)
    created_at: datetime


class Backup(Record):
    version: Literal[1] = 1
    topics: list[TopicRecord] = Field(default_factory=list, max_length=10000)
    edges: list[dict[str, str]] = Field(default_factory=list, max_length=50000)
    problems: list[ProblemRecord] = Field(max_length=50000)
    reviews: list[ReviewRecord] = Field(default_factory=list, max_length=200000)
    solves: list[SolveRecord] = Field(default_factory=list, max_length=200000)
    settings: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_records(self):
        for keys in ([t.name.lower() for t in self.topics],
                     [(p.platform, p.slug) for p in self.problems]):
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate topics or problems in backup")
        for edge in self.edges:
            if set(edge) != {"from", "to"} or edge["from"] == edge["to"]:
                raise ValueError("Invalid topic edge")
        if "daily_goal" in self.settings:
            goal = int(self.settings["daily_goal"])
            if not 1 <= goal <= 100:
                raise ValueError("daily_goal must be between 1 and 100")
        return self
