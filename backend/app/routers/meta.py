from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..services import get_setting, search_all, set_setting
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "recall-ai"}


@router.get("/search")
def search(q: str = Query(""), limit: int = 30, db: Session = Depends(get_db)):
    return search_all(db, q, limit)


class SettingsUpdate(BaseModel):
    daily_goal: int | None = None
    api_token_hint: str | None = None


@router.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    return {
        "daily_goal": int(get_setting(db, "daily_goal", "10")),
        "api_token": settings.api_token,
        "onboarded": get_setting(db, "onboarded", "false") == "true",
    }


@router.post("/settings")
def write_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    if body.daily_goal is not None:
        if not isinstance(body.daily_goal, int) or body.daily_goal < 1 or body.daily_goal > 100:
            from fastapi import HTTPException
            raise HTTPException(400, "daily_goal must be an integer from 1 to 100")
        set_setting(db, "daily_goal", str(body.daily_goal))
    set_setting(db, "onboarded", "true")
    db.commit()
    return read_settings(db)
