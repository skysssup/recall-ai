from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_api_token
from ..db import get_db
from ..schemas import SolveIn, SolveOut
from ..services import ingest_solve, solve_to_out

router = APIRouter(prefix="/api/capture", tags=["capture"])


@router.post("/solve", response_model=SolveOut)
def capture_solve(
    body: SolveIn,
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    solve, strength, rating = ingest_solve(db, body, source="extension")
    return solve_to_out(solve, strength, rating)


@router.post("/manual", response_model=SolveOut)
def manual_solve(
    body: SolveIn,
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    solve, strength, rating = ingest_solve(db, body, source="manual")
    return solve_to_out(solve, strength, rating)
