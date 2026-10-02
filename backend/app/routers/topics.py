from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_api_token
from sqlalchemy.orm import Session

from ..db import get_db
from .. import graph as graph_mod
from ..models import Topic
from ..schemas import TopicOut
from ..services import topic_to_out

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("", response_model=list[TopicOut])
def list_topics(db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    topics = db.query(Topic).order_by(Topic.name).all()
    return [topic_to_out(db, t) for t in topics]


@router.get("/graph")
def topic_graph(db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    return graph_mod.serialize_graph(db)


@router.get("/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: str, db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    t = db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404, "Topic not found")
    return topic_to_out(db, t)
