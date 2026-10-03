"""Topic prerequisite graph helpers (no NetworkX — plain adjacency)."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .models import Topic, TopicEdge
from .scheduler import retrievability


def adjacency(db: Session) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Return (prereq_name -> [dependent names], id -> name)."""
    topics = db.query(Topic).all()
    id_to_name = {t.id: t.name for t in topics}
    fwd: dict[str, list[str]] = defaultdict(list)
    for edge in db.query(TopicEdge).all():
        a = id_to_name.get(edge.from_topic_id)
        b = id_to_name.get(edge.to_topic_id)
        if a and b:
            fwd[a].append(b)
    return dict(fwd), id_to_name


def reverse_adjacency(fwd: dict[str, list[str]]) -> dict[str, list[str]]:
    rev: dict[str, list[str]] = defaultdict(list)
    for src, dsts in fwd.items():
        for d in dsts:
            rev[d].append(src)
    return dict(rev)


def neighbors(db: Session, topic_name: str) -> dict[str, list[str]]:
    fwd, id_to_name = adjacency(db)
    if topic_name not in id_to_name.values():
        return {"prerequisites": [], "dependents": []}
    rev = reverse_adjacency(fwd)
    return {
        "prerequisites": sorted(rev.get(topic_name, [])),
        "dependents": sorted(fwd.get(topic_name, [])),
    }


def ancestors(db: Session, topic_name: str) -> list[str]:
    fwd, _ = adjacency(db)
    rev = reverse_adjacency(fwd)
    seen: set[str] = set()
    q: deque[str] = deque(rev.get(topic_name, []))
    while q:
        n = q.popleft()
        if n in seen:
            continue
        seen.add(n)
        q.extend(rev.get(n, []))
    return sorted(seen)


def descendants(db: Session, topic_name: str) -> list[str]:
    fwd, _ = adjacency(db)
    seen: set[str] = set()
    q: deque[str] = deque(fwd.get(topic_name, []))
    while q:
        n = q.popleft()
        if n in seen:
            continue
        seen.add(n)
        q.extend(fwd.get(n, []))
    return sorted(seen)


def topological_layers(db: Session) -> list[list[str]]:
    """Group topics into prerequisite layers (roots first)."""
    fwd, id_to_name = adjacency(db)
    names = list(id_to_name.values())
    rev = reverse_adjacency(fwd)
    indeg = {n: len(rev.get(n, [])) for n in names}
    layer = [n for n, d in indeg.items() if d == 0]
    layers: list[list[str]] = []
    placed: set[str] = set()
    while layer:
        layer = sorted(layer)
        layers.append(layer)
        placed.update(layer)
        nxt: list[str] = []
        for n in layer:
            for d in fwd.get(n, []):
                indeg[d] -= 1
                if indeg[d] == 0 and d not in placed:
                    nxt.append(d)
        layer = nxt
    leftover = sorted(n for n in names if n not in placed)
    if leftover:
        layers.append(leftover)
    return layers


def serialize_graph(db: Session) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    topics = db.query(Topic).order_by(Topic.name).all()
    edges = db.query(TopicEdge).all()
    id_to_name = {t.id: t.name for t in topics}
    return {
        "nodes": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "stability": t.stability,
                "difficulty": t.difficulty,
                "retrievability": round(retrievability(t.stability, t.last_reviewed_at, now), 4),
                "practice_count": t.practice_count,
                "last_reviewed_at": t.last_reviewed_at.isoformat() + "Z" if t.last_reviewed_at else None,
            }
            for t in topics
        ],
        "edges": [
            {
                "from": id_to_name.get(e.from_topic_id),
                "to": id_to_name.get(e.to_topic_id),
                "from_id": e.from_topic_id,
                "to_id": e.to_topic_id,
            }
            for e in edges
            if e.from_topic_id in id_to_name and e.to_topic_id in id_to_name
        ],
        "layers": topological_layers(db),
    }


def ensure_edge(db: Session, prereq: Topic, dependent: Topic) -> None:
    exists = (
        db.query(TopicEdge)
        .filter(TopicEdge.from_topic_id == prereq.id, TopicEdge.to_topic_id == dependent.id)
        .first()
    )
    if not exists:
        db.add(TopicEdge(from_topic_id=prereq.id, to_topic_id=dependent.id))
