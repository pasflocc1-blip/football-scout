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

    # 1. Troviamo i giocatori con l'intelligenza artificiale
    players = search_players(
        db=db,
        text=q,
        position=position,
        min_age=min_age,
        max_age=max_age,
        nationality=nationality,
        limit=limit,
    )

    # 2. Importa il modello delle statistiche (se non c'è già in cima al file)
    from app.models.models import PlayerSeasonStats

    # 3. Costruiamo la risposta unendo l'anagrafica e le statistiche
    response = []
    for p in players:
        # Cerchiamo l'ultima stagione di questo giocatore
        stats = db.query(PlayerSeasonStats).filter(
            PlayerSeasonStats.player_id == p.id
        ).order_by(PlayerSeasonStats.fetched_at.desc()).first()

        # Copiamo l'anagrafica in un dizionario
        p_dict = p.__dict__.copy()

        # Aggiungiamo tutte le statistiche che FastAPI pretende
        # Usiamo getattr() così se il giocatore non ha statistiche, mettiamo 0 senza far crashare nulla
        p_dict["xg_per90"] = getattr(stats, "xg_per90", 0.0)
        p_dict["xa_per90"] = getattr(stats, "xa_per90", 0.0)
        p_dict["npxg_per90"] = getattr(stats, "npxg_per90", 0.0)
        p_dict["xgchain_per90"] = getattr(stats, "xgchain_per90", 0.0)
        p_dict["xgbuildup_per90"] = getattr(stats, "xgbuildup_per90", 0.0)

        # Mappiamo i nomi dal DB a quelli richiesti dal frontend
        p_dict["minutes_season"] = getattr(stats, "minutes_played", 0)
        p_dict["goals_season"] = getattr(stats, "goals", 0)
        p_dict["assists_season"] = getattr(stats, "assists", 0)
        p_dict["aerial_duels_won_pct"] = getattr(stats, "aerial_duels_won_pct", 0.0)
        p_dict["duels_won_pct"] = getattr(stats, "total_duels_won_pct", 0.0)

        response.append(p_dict)

    return response


@router.get("/autocomplete")
def autocomplete_players(
        q: str = Query(..., description="Nome del giocatore da cercare"),
        db: Session = Depends(get_db)
):
    """
    Endpoint leggerissimo dedicato ESCLUSIVAMENTE alla barra di ricerca del frontend.
    """
    # 👇 ECCO LA RIGA MAGICA CHE MANCAVA 👇
    from app.models.models import ScoutingPlayer

    if len(q) < 3:
        return []

    # Cerca i giocatori il cui nome contiene il testo digitato
    players = db.query(ScoutingPlayer).filter(
        ScoutingPlayer.name.ilike(f"%{q}%")
    ).limit(10).all()

    # Restituisce solo un dizionario pulito e leggero
    return [{"id": p.id, "name": p.name, "position": p.position} for p in players]
