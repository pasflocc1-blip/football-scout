from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services.search import search_players
from app.schemas.schemas import ScoutingPlayerOut

router = APIRouter(prefix="/scouting", tags=["Scouting"])


@router.get("/search", response_model=list[ScoutingPlayerOut])
def search(
    q: str = Query(..., description="Es: centravanti mancino bravo di testa under 25"),
    position: Optional[str] = Query(None, description="Es: ST, CM, CB"),
    min_age: Optional[int] = Query(None, ge=15, le=45),
    max_age: Optional[int] = Query(None, ge=15, le=45),
    nationality: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Ricerca semantica in linguaggio naturale + filtri opzionali.

    Esempi:
    - /scouting/search?q=centravanti mancino bravo di testa
    - /scouting/search?q=veloce&position=LW&max_age=25
    - /scouting/search?q=portiere esperto&nationality=italiana
    """
    return search_players(
        db=db,
        text=q,
        position=position,
        min_age=min_age,
        max_age=max_age,
        nationality=nationality,
        limit=limit,
    )
