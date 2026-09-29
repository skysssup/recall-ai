from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _uid() -> str:
    return uuid4().hex


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Spaced-repetition state for the topic itself
    stability: Mapped[float] = mapped_column(Float, default=1.0)
    difficulty: Mapped[float] = mapped_column(Float, default=5.0)
    retrievability: Mapped[float] = mapped_column(Float, default=1.0)
    practice_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    problems: Mapped[list["Problem"]] = relationship(back_populates="topic")
    outbound: Mapped[list["TopicEdge"]] = relationship(
        back_populates="from_topic",
        foreign_keys="TopicEdge.from_topic_id",
        cascade="all, delete-orphan",
    )
    inbound: Mapped[list["TopicEdge"]] = relationship(
        back_populates="to_topic",
        foreign_keys="TopicEdge.to_topic_id",
        cascade="all, delete-orphan",
    )


class TopicEdge(Base):
    """Directed edge: from_topic is a prerequisite of to_topic."""

    __tablename__ = "topic_edges"
    __table_args__ = (UniqueConstraint("from_topic_id", "to_topic_id", name="uq_edge"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    from_topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    to_topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))

    from_topic: Mapped[Topic] = relationship(foreign_keys=[from_topic_id], back_populates="outbound")
    to_topic: Mapped[Topic] = relationship(foreign_keys=[to_topic_id], back_populates="inbound")


class Problem(Base):
    __tablename__ = "problems"
    __table_args__ = (
        UniqueConstraint("platform", "slug", name="uq_platform_slug"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    title: Mapped[str] = mapped_column(String(240), index=True)
    platform: Mapped[str] = mapped_column(String(40), default="manual")  # leetcode|codeforces|manual
    slug: Mapped[str] = mapped_column(String(240), index=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="Medium")  # Easy|Medium|Hard
    topic_id: Mapped[Optional[str]] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    tags: Mapped[str] = mapped_column(Text, default="")  # comma-separated
    notes: Mapped[str] = mapped_column(Text, default="")
    # Card state
    stability: Mapped[float] = mapped_column(Float, default=1.0)
    difficulty_score: Mapped[float] = mapped_column(Float, default=5.0)
    retrievability: Mapped[float] = mapped_column(Float, default=1.0)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    topic: Mapped[Optional[Topic]] = relationship(back_populates="problems")
    reviews: Mapped[list["Review"]] = relationship(back_populates="problem", cascade="all, delete-orphan")
    solves: Mapped[list["Solve"]] = relationship(back_populates="problem", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1=Again 2=Hard 3=Good 4=Easy
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    problem: Mapped[Problem] = relationship(back_populates="reviews")


class Solve(Base):
    """Captured solve attempt from the extension or manual log."""

    __tablename__ = "solves"
    __table_args__ = (UniqueConstraint("client_event_id", name="uq_client_event"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    problem_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("problems.id", ondelete="SET NULL"), nullable=True, index=True
    )
    client_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    platform: Mapped[str] = mapped_column(String(40), default="manual")
    slug: Mapped[str] = mapped_column(String(240), default="")
    title: Mapped[str] = mapped_column(String(240), default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="Medium")
    verdict: Mapped[str] = mapped_column(String(40), default="Accepted")
    time_to_understand_s: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_to_write_s: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_submissions: Mapped[int] = mapped_column(Integer, default=1)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(40), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    problem: Mapped[Optional[Problem]] = relationship(back_populates="solves")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
