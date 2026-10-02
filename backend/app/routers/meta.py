from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import mask_token, require_api_token
from ..config import settings
from ..db import get_db
from ..services import get_setting, search_all, set_setting

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "recall-ai"}


@router.get("/search")
def search(
    q: str = Query(""),
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    return search_all(db, q, limit)


class SettingsUpdate(BaseModel):
    daily_goal: int | None = None


def _settings_payload(db: Session) -> dict:
    return {
        "daily_goal": int(get_setting(db, "daily_goal", "10")),
        "api_token_hint": mask_token(settings.api_token),
        "api_token_configured": bool(settings.api_token),
        "onboarded": get_setting(db, "onboarded", "false") == "true",
    }


@router.get("/settings")
def read_settings(
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    # Never return the raw API token — configure via RECALL_API_TOKEN / extension popup.
    return _settings_payload(db)


@router.post("/settings")
def write_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    if body.daily_goal is not None:
        if not isinstance(body.daily_goal, int) or body.daily_goal < 1 or body.daily_goal > 100:
            raise HTTPException(400, "daily_goal must be an integer from 1 to 100")
        set_setting(db, "daily_goal", str(body.daily_goal))
    set_setting(db, "onboarded", "true")
    db.commit()
    return _settings_payload(db)
