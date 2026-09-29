from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..schemas import SolveIn, SolveOut
from ..services import ingest_solve, solve_to_out

router = APIRouter(prefix="/api/capture", tags=["capture"])


def _check_token(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_api_key:
        token = x_api_key.strip()
    if token != settings.api_token:
        raise HTTPException(401, "Invalid or missing API token")


@router.post("/solve", response_model=SolveOut)
def capture_solve(
    body: SolveIn,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    _check_token(authorization, x_api_key)
    solve, strength, rating = ingest_solve(db, body, source="extension")
    return solve_to_out(solve, strength, rating)


@router.post("/manual", response_model=SolveOut)
def manual_solve(body: SolveIn, db: Session = Depends(get_db)):
    # Manual logging from the web UI — no token required on localhost.
    solve, strength, rating = ingest_solve(db, body, source="manual")
    return solve_to_out(solve, strength, rating)
