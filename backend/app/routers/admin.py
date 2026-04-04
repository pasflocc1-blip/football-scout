"""
routers/admin.py
----------------
Endpoint amministrativi per il ricalcolo degli score.

POST /admin/recalculate-scores      → Fase 2+3+4 in background (risposta immediata)
POST /admin/recalculate-scores/sync → Fase 2+3+4 sincrono (blocca fino al termine)
POST /admin/recalculate-percentiles → Solo Fase 4 sincrono
GET  /admin/stats                   → Statistiche DB
"""

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])


def _run_full_recalculate(db) -> dict:
    """
    Esegue Fase 2 + Fase 3 (scoring) poi Fase 4 (percentili) in sequenza.
    Unica funzione chiamata da tutti gli endpoint di ricalcolo.
    """
    from app.services.scoring    import recalculate_all
    from app.services.percentiles import recalculate_percentiles

    # Fase 2 + 3: normalizzazione per 90 e score dimensionali
    n_scored = recalculate_all(db)

    # Fase 4: percentile per ruolo (richiede pandas)
    try:
        pct_result = recalculate_percentiles(db)
    except ImportError as e:
        pct_result = {"error": str(e), "players_updated": 0}

    return {
        "scored":  n_scored,
        "percentiles": pct_result,
    }


# ── Ricalcolo completo (background) ──────────────────────────────

@router.post("/recalculate-scores")
def recalculate_scores(background_tasks: BackgroundTasks):
    """
    Avvia Fase 2+3+4 in background.
    Risposta immediata — il ricalcolo gira senza bloccare.
    Chiamato automaticamente al termine di ogni importazione.
    """
    def _task():
        from app.database import SessionLocal
        _db = SessionLocal()
        try:
            result = _run_full_recalculate(_db)
            print(f"  → recalculate complete: {result}")
        finally:
            _db.close()

    background_tasks.add_task(_task)
    return {"message": "Ricalcolo avviato in background (Fase 2+3+4)"}


# ── Ricalcolo completo (sincrono — utile da terminale/test) ──────

@router.post("/recalculate-scores/sync")
def recalculate_scores_sync(db: Session = Depends(get_db)):
    """
    Esegue Fase 2+3+4 in modo sincrono.
    La risposta contiene il dettaglio del ricalcolo.
    """
    result = _run_full_recalculate(db)
    return {
        "message":   f"Score ricalcolati per {result['scored']} giocatori",
        "scored":    result["scored"],
        "percentiles": result["percentiles"],
    }


# ── Solo percentili (Fase 4) ─────────────────────────────────────

@router.post("/recalculate-percentiles")
def recalculate_percentiles_endpoint(db: Session = Depends(get_db)):
    """
    Ricalcola solo i percentili per ruolo (Fase 4), senza rieseguire
    il calcolo degli score. Utile se si vuole solo aggiornare i percentili
    dopo aver aggiunto nuovi giocatori.
    """
    from app.services.percentiles import recalculate_percentiles
    result = recalculate_percentiles(db)
    return {
        "message": f"Percentili ricalcolati per {result['players_updated']} giocatori",
        **result,
    }


# ── Statistiche DB ───────────────────────────────────────────────

@router.get("/stats")
def db_stats(db: Session = Depends(get_db)):
    """Statistiche rapide sul contenuto del database."""
    from app.models.models import ScoutingPlayer, MyTeam, MyPlayer

    with_minutes = (
        db.query(ScoutingPlayer)
        .filter(
            ScoutingPlayer.minutes_season.isnot(None),
            ScoutingPlayer.minutes_season > 0,
        )
        .count()
    )
    with_scores = (
        db.query(ScoutingPlayer)
        .filter(ScoutingPlayer.finishing_score.isnot(None))
        .count()
    )
    with_percentiles = (
        db.query(ScoutingPlayer)
        .filter(ScoutingPlayer.finishing_pct.isnot(None))
        .count()
    )

    return {
        "scouting_players":  db.query(ScoutingPlayer).count(),
        "with_minutes":      with_minutes,
        "with_scores":       with_scores,
        "with_percentiles":  with_percentiles,
        "teams":             db.query(MyTeam).count(),
        "roster_players":    db.query(MyPlayer).count(),
    }


@router.get("/data-sources/last-update")
def get_last_updates(db: Session = Depends(get_db)):
    from sqlalchemy import text, func
    from app.models.models import PlayerSeasonStats, ScoutingPlayer, PlayerHeatmap

    rows = db.query(
        PlayerSeasonStats.source,
        func.max(PlayerSeasonStats.fetched_at).label('last_download'),
        func.count(PlayerSeasonStats.player_id.distinct()).label('players_updated'),
    ).group_by(PlayerSeasonStats.source).all()

    result = [
        {
            "source": r.source,
            "last_download": r.last_download.isoformat() if r.last_download else None,
            "players_updated": r.players_updated,
        }
        for r in rows
    ]

    # Aggiunge SofaScore da scouting_players.last_updated_sofascore
    sofa_last = db.query(func.max(ScoutingPlayer.last_updated_sofascore)).scalar()
    result.append({
        "source": "sofascore_rpa",
        "last_download": sofa_last.isoformat() if sofa_last else None,
        "players_updated": db.query(ScoutingPlayer).filter(
            ScoutingPlayer.last_updated_sofascore.isnot(None)
        ).count(),
    })

    return result
