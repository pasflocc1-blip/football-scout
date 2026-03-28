"""
routers/global_scouting.py
--------------------------
Endpoints per il Global Scouting: esplorazione libera del database,
ranking, confronto e discovery dei giocatori.

Differenza rispetto a /scouting (team scouting):
  /scouting          → filtri legati al team, decision support
  /global-scouting   → esplorazione libera, ranking, confronto, discovery

Endpoints esposti sotto il prefix /scouting (compatibilità client):
  GET  /scouting/search          → ricerca per filtri avanzati
  GET  /scouting/top-xg          → classifica per xG/90
  GET  /scouting/overperforming  → goals > xG stimati
  GET  /scouting/underperforming → goals < xG stimati
  GET  /scouting/compare         → confronto tra due giocatori per nome
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import Optional

from app.database import get_db
from app.models.models import ScoutingPlayer

router = APIRouter(prefix="/scouting", tags=["Global Scouting"])


# ── Helper: serializza un giocatore in dizionario completo ────────

def _player_dict(p: ScoutingPlayer) -> dict:
    return {
        "id":               p.id,
        "name":             p.name,
        "position":         p.position,
        "club":             p.club,
        "nationality":      p.nationality,
        "age":              p.age,
        "preferred_foot":   p.preferred_foot,
        # Stats base
        "pace":             p.pace,
        "shooting":         p.shooting,
        "passing":          p.passing,
        "dribbling":        p.dribbling,
        "defending":        p.defending,
        "physical":         p.physical,
        # Stats avanzate
        "xg_per90":         p.xg_per90,
        "xa_per90":         p.xa_per90,
        "progressive_passes": p.progressive_passes,
        "aerial_duels_won_pct": p.aerial_duels_won_pct,
        # Scores calcolati
        "heading_score":    p.heading_score,
        "build_up_score":   p.build_up_score,
        "defensive_score":  p.defensive_score,
        # Stagione (colonne opzionali — presenti solo se migration applicata)
        "goals_season":     getattr(p, "goals_season", None),
        "assists_season":   getattr(p, "assists_season", None),
        "minutes_season":   getattr(p, "minutes_season", None),
    }


# ── 1. SEARCH — ricerca avanzata per filtri ───────────────────────

@router.get("/search")
def global_search(
    q:            Optional[str]   = Query(None,  description="Testo libero (nome, club, nazionalità)"),
    position:     Optional[str]   = Query(None,  description="Es: ST, CM, CB, GK"),
    min_age:      Optional[int]   = Query(None,  ge=15, le=45),
    max_age:      Optional[int]   = Query(None,  ge=15, le=45),
    nationality:  Optional[str]   = Query(None),
    club:         Optional[str]   = Query(None),
    min_xg:       Optional[float] = Query(None,  ge=0, description="xG/90 minimo"),
    min_xa:       Optional[float] = Query(None,  ge=0, description="xA/90 minimo"),
    preferred_foot: Optional[str] = Query(None,  description="left | right | both"),
    sort_by:      str             = Query("name", description="Campo di ordinamento: name|xg_per90|xa_per90|age"),
    sort_dir:     str             = Query("asc",  description="asc | desc"),
    limit:        int             = Query(50,     ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Ricerca libera nel database giocatori con filtri combinabili.
    Punto di ingresso principale per il Global Scouting.
    """
    query = db.query(ScoutingPlayer)

    # Filtro testo libero (nome / club / nazionalità)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.filter(
            ScoutingPlayer.name.ilike(like) |
            ScoutingPlayer.club.ilike(like) |
            ScoutingPlayer.nationality.ilike(like)
        )

    if position:
        query = query.filter(ScoutingPlayer.position.ilike(f"%{position}%"))

    if min_age is not None:
        query = query.filter(ScoutingPlayer.age >= min_age)

    if max_age is not None:
        query = query.filter(ScoutingPlayer.age <= max_age)

    if nationality:
        query = query.filter(ScoutingPlayer.nationality.ilike(f"%{nationality}%"))

    if club:
        query = query.filter(ScoutingPlayer.club.ilike(f"%{club}%"))

    if min_xg is not None:
        query = query.filter(ScoutingPlayer.xg_per90 >= min_xg)

    if min_xa is not None:
        query = query.filter(ScoutingPlayer.xa_per90 >= min_xa)

    if preferred_foot:
        query = query.filter(ScoutingPlayer.preferred_foot.ilike(preferred_foot))

    # Ordinamento
    _SORT_FIELDS = {
        "name":      ScoutingPlayer.name,
        "xg_per90":  ScoutingPlayer.xg_per90,
        "xa_per90":  ScoutingPlayer.xa_per90,
        "age":       ScoutingPlayer.age,
        "pace":      ScoutingPlayer.pace,
        "shooting":  ScoutingPlayer.shooting,
        "passing":   ScoutingPlayer.passing,
        "dribbling": ScoutingPlayer.dribbling,
    }
    sort_col = _SORT_FIELDS.get(sort_by, ScoutingPlayer.name)
    order_fn = desc if sort_dir == "desc" else asc
    query = query.order_by(order_fn(sort_col))

    players = query.limit(limit).all()
    return [_player_dict(p) for p in players]


# ── 2. TOP XG — classifica per xG/90 ─────────────────────────────

@router.get("/top-xg")
def top_xg(
    limit:        int           = Query(20,  ge=1, le=100),
    min_minutes:  int           = Query(300, ge=0, description="Minuti minimi stagione"),
    position:     Optional[str] = Query(None, description="Filtra per ruolo"),
    db: Session = Depends(get_db),
):
    """
    Classifica i migliori giocatori per xG per 90 minuti.
    Filtrabile per ruolo e minuti minimi (per escludere sample size bassi).
    """
    query = (
        db.query(ScoutingPlayer)
        .filter(ScoutingPlayer.xg_per90.isnot(None))
    )

    # Filtro minuti (colonna opzionale)
    try:
        if min_minutes > 0:
            query = query.filter(ScoutingPlayer.minutes_season >= min_minutes)
    except Exception:
        pass  # colonna non ancora presente nel DB

    if position:
        query = query.filter(ScoutingPlayer.position.ilike(f"%{position}%"))

    players = query.order_by(desc(ScoutingPlayer.xg_per90)).limit(limit).all()

    return [
        {
            "id":          p.id,
            "name":        p.name,
            "club":        p.club,
            "position":    p.position,
            "nationality": p.nationality,
            "age":         p.age,
            "xg_per90":    p.xg_per90,
            "xa_per90":    p.xa_per90,
            "minutes":     getattr(p, "minutes_season", None),
        }
        for p in players
    ]


# ── 3. OVERPERFORMING — goals > xG stimati ───────────────────────

@router.get("/overperforming")
def overperforming(
    limit:       int           = Query(20,  ge=1, le=100),
    min_minutes: int           = Query(300, ge=0),
    position:    Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Giocatori che segnano più di quanto suggerisce il loro xG:
    delta = goals_season - xG_stimato_totale  (positivo → overperforming)
    """
    query = (
        db.query(ScoutingPlayer)
        .filter(ScoutingPlayer.xg_per90.isnot(None))
    )

    try:
        if min_minutes > 0:
            query = query.filter(ScoutingPlayer.minutes_season >= min_minutes)
        query = query.filter(ScoutingPlayer.goals_season.isnot(None))
    except Exception:
        pass

    if position:
        query = query.filter(ScoutingPlayer.position.ilike(f"%{position}%"))

    result = []
    for p in query.all():
        minutes = getattr(p, "minutes_season", None)
        goals   = getattr(p, "goals_season", None)
        if not minutes or goals is None:
            continue
        xg_total = p.xg_per90 * (minutes / 90)
        delta    = goals - xg_total
        result.append({
            "id":            p.id,
            "name":          p.name,
            "club":          p.club,
            "position":      p.position,
            "nationality":   p.nationality,
            "age":           p.age,
            "goals":         goals,
            "xg_estimated":  round(xg_total, 2),
            "delta":         round(delta, 2),
            "minutes":       minutes,
        })

    result.sort(key=lambda x: x["delta"], reverse=True)
    return result[:limit]


# ── 4. UNDERPERFORMING — goals < xG stimati ──────────────────────

@router.get("/underperforming")
def underperforming(
    limit:       int           = Query(20,  ge=1, le=100),
    min_minutes: int           = Query(300, ge=0),
    position:    Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Giocatori che segnano meno di quanto suggerisce il loro xG:
    delta = goals_season - xG_stimato_totale  (negativo → underperforming)

    Utile per trovare giocatori "sfigati" che potrebbero tornare alla media.
    """
    query = (
        db.query(ScoutingPlayer)
        .filter(ScoutingPlayer.xg_per90.isnot(None))
    )

    try:
        if min_minutes > 0:
            query = query.filter(ScoutingPlayer.minutes_season >= min_minutes)
        query = query.filter(ScoutingPlayer.goals_season.isnot(None))
    except Exception:
        pass

    if position:
        query = query.filter(ScoutingPlayer.position.ilike(f"%{position}%"))

    result = []
    for p in query.all():
        minutes = getattr(p, "minutes_season", None)
        goals   = getattr(p, "goals_season", None)
        if not minutes or goals is None:
            continue
        xg_total = p.xg_per90 * (minutes / 90)
        delta    = goals - xg_total
        result.append({
            "id":            p.id,
            "name":          p.name,
            "club":          p.club,
            "position":      p.position,
            "nationality":   p.nationality,
            "age":           p.age,
            "goals":         goals,
            "xg_estimated":  round(xg_total, 2),
            "delta":         round(delta, 2),
            "minutes":       minutes,
        })

    result.sort(key=lambda x: x["delta"])
    return result[:limit]


# ── 5. COMPARE — confronto diretto tra due giocatori ─────────────

@router.get("/compare")
def compare_players(
    name1: str = Query(..., description="Nome (parziale) del primo giocatore"),
    name2: str = Query(..., description="Nome (parziale) del secondo giocatore"),
    db: Session = Depends(get_db),
):
    """
    Confronto testa-a-testa tra due giocatori cercati per nome.
    Ritorna le stat complete di entrambi più un diff per ogni metrica.
    """
    def _find(name: str) -> ScoutingPlayer:
        player = (
            db.query(ScoutingPlayer)
            .filter(ScoutingPlayer.name.ilike(f"%{name.strip()}%"))
            .first()
        )
        if not player:
            raise HTTPException(404, f"Giocatore '{name}' non trovato nel database")
        return player

    p1 = _find(name1)
    p2 = _find(name2)

    def _safe_diff(a, b):
        if a is None or b is None:
            return None
        try:
            return round(a - b, 3)
        except TypeError:
            return None

    METRICS = [
        "pace", "shooting", "passing", "dribbling", "defending", "physical",
        "xg_per90", "xa_per90",
        "heading_score", "build_up_score", "defensive_score",
        "aerial_duels_won_pct", "progressive_passes",
    ]

    diff = {}
    for m in METRICS:
        v1 = getattr(p1, m, None)
        v2 = getattr(p2, m, None)
        diff[m] = _safe_diff(v1, v2)

    return {
        "player1": _player_dict(p1),
        "player2": _player_dict(p2),
        "diff":    diff,          # diff[m] = p1[m] - p2[m]  (positivo → p1 migliore)
    }