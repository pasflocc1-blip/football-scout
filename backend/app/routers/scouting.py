"""
routers/scouting.py — FIX: q diventa opzionale per supportare ricerche con soli filtri avanzati
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services.search import search_players
from app.schemas.schemas import ScoutingPlayerOut

router = APIRouter(prefix="/scouting", tags=["Scouting"])


@router.get("/search", response_model=list[ScoutingPlayerOut])
def search(
        q: Optional[str] = Query(None, description="Es: centravanti mancino bravo di testa under 25"),
        position: Optional[str] = Query(None, description="Es: ST, CM, CB"),
        min_age: Optional[int] = Query(None, ge=15, le=45),
        max_age: Optional[int] = Query(None, ge=15, le=45),
        nationality: Optional[str] = Query(None),
        limit: int = Query(20, ge=1, le=100),
        db: Session = Depends(get_db),
):
    """
    Ricerca semantica in linguaggio naturale + filtri opzionali.

    FIX: q è ora OPZIONALE. Si può cercare con solo i filtri avanzati.

    Esempi:
    - /scouting/search?q=centravanti mancino bravo di testa
    - /scouting/search?q=veloce&position=LW&max_age=25
    - /scouting/search?position=CB&min_age=25&max_age=30
    - /scouting/search?q=scarsa in difesa
    """
    # Richiede almeno un parametro
    if not q and not position and min_age is None and max_age is None and not nationality:
        return []

    return search_players(
        db=db,
        text=q,
        position=position,
        min_age=min_age,
        max_age=max_age,
        nationality=nationality,
        limit=limit,
    )