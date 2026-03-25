from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.scoring import recalculate_all

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/recalculate-scores")
def recalculate_scores(db: Session = Depends(get_db)):
    """
    Ricalcola heading_score, build_up_score, defensive_score
    per tutti i giocatori nel database.
    Da eseguire dopo ogni importazione dati.
    """
    updated = recalculate_all(db)
    return {"message": f"Score ricalcolati per {updated} giocatori"}


@router.get("/stats")
def db_stats(db: Session = Depends(get_db)):
    """Statistiche rapide sul contenuto del database."""
    from app.models.models import ScoutingPlayer, MyTeam, MyPlayer
    return {
        "scouting_players": db.query(ScoutingPlayer).count(),
        "teams":            db.query(MyTeam).count(),
        "roster_players":   db.query(MyPlayer).count(),
    }
