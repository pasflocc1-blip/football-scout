"""
routers/global_scouting.py — aggiornato per pipeline oggettivo (Fase 1-5)
--------------------------------------------------------------------------
FIX: rimossi tutti i riferimenti a pace/shooting/passing/dribbling/defending/physical
     che non esistono più nel modello ScoutingPlayer aggiornato.

GET  /global-scouting/search
GET  /global-scouting/top-xg
GET  /global-scouting/overperforming
GET  /global-scouting/underperforming
GET  /global-scouting/compare
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import Optional

from app.database import get_db
from app.models.models import ScoutingPlayer

router = APIRouter(prefix="/global-scouting", tags=["Global Scouting"])


def _g(p, attr, default=None):
    return getattr(p, attr, default)


def _player_dict(p: ScoutingPlayer) -> dict:
    return {
        "id":                   p.id,
        "name":                 p.name,
        "position":             p.position,
        "club":                 p.club,
        "nationality":          p.nationality,
        "age":                  p.age,
        "preferred_foot":       p.preferred_foot,
        # xG / xA per 90
        "xg_per90":             _g(p, "xg_per90"),
        "xa_per90":             _g(p, "xa_per90"),
        "npxg_per90":           _g(p, "npxg_per90"),
        "xgchain_per90":        _g(p, "xgchain_per90"),
        "xgbuildup_per90":      _g(p, "xgbuildup_per90"),
        # Stagione
        "goals_season":         _g(p, "goals_season"),
        "assists_season":       _g(p, "assists_season"),
        "minutes_season":       _g(p, "minutes_season"),
        "games_season":         _g(p, "games_season"),
        "shots_season":         _g(p, "shots_season"),
        "key_passes_season":    _g(p, "key_passes_season"),
        # Progressione
        "progressive_passes":   _g(p, "progressive_passes"),
        "progressive_carries":  _g(p, "progressive_carries"),
        # Difesa
        "aerial_duels_won_pct": _g(p, "aerial_duels_won_pct"),
        "duels_won_pct":        _g(p, "duels_won_pct"),
        "pressures_season":     _g(p, "pressures_season"),
        # Score oggettivi (Fase 3)
        "finishing_score":      _g(p, "finishing_score"),
        "creativity_score":     _g(p, "creativity_score"),
        "pressing_score":       _g(p, "pressing_score"),
        "carrying_score":       _g(p, "carrying_score"),
        "defending_obj_score":  _g(p, "defending_obj_score"),
        "buildup_obj_score":    _g(p, "buildup_obj_score"),
        # Percentili (Fase 4)
        "finishing_pct":        _g(p, "finishing_pct"),
        "creativity_pct":       _g(p, "creativity_pct"),
        "pressing_pct":         _g(p, "pressing_pct"),
        "carrying_pct":         _g(p, "carrying_pct"),
        "defending_pct":        _g(p, "defending_pct"),
        "buildup_pct":          _g(p, "buildup_pct"),
        # Legacy (compatibilità PlayerCard)
        "heading_score":        _g(p, "heading_score"),
        "build_up_score":       _g(p, "build_up_score"),
        "defensive_score":      _g(p, "defensive_score"),
    }


@router.get("/search")
def global_search(
    q:              Optional[str]   = Query(None),
    position:       Optional[str]   = Query(None),
    min_age:        Optional[int]   = Query(None, ge=15, le=45),
    max_age:        Optional[int]   = Query(None, ge=15, le=45),
    nationality:    Optional[str]   = Query(None),
    club:           Optional[str]   = Query(None),
    min_xg:         Optional[float] = Query(None, ge=0),
    min_xa:         Optional[float] = Query(None, ge=0),
    preferred_foot: Optional[str]   = Query(None),
    sort_by:        str             = Query("name"),
    sort_dir:       str             = Query("asc"),
    limit:          int             = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(ScoutingPlayer)

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

    # Mappa ordinamento — SOLO colonne presenti nel modello aggiornato
    _SORT = {
        "name":             ScoutingPlayer.name,
        "xg_per90":         ScoutingPlayer.xg_per90,
        "xa_per90":         ScoutingPlayer.xa_per90,
        "npxg_per90":       ScoutingPlayer.npxg_per90,
        "age":              ScoutingPlayer.age,
        "finishing_score":  ScoutingPlayer.finishing_score,
        "creativity_score": ScoutingPlayer.creativity_score,
        "pressing_score":   ScoutingPlayer.pressing_score,
        "carrying_score":   ScoutingPlayer.carrying_score,
        "finishing_pct":    ScoutingPlayer.finishing_pct,
        "creativity_pct":   ScoutingPlayer.creativity_pct,
        "minutes_season":   ScoutingPlayer.minutes_season,
        "goals_season":     ScoutingPlayer.goals_season,
    }
    sort_col = _SORT.get(sort_by, ScoutingPlayer.name)
    order_fn = desc if sort_dir == "desc" else asc
    query = query.order_by(order_fn(sort_col))

    return [_player_dict(p) for p in query.limit(limit).all()]


@router.get("/top-xg")
def top_xg(
    limit:       int           = Query(20, ge=1, le=100),
    min_minutes: int           = Query(300, ge=0),
    position:    Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ScoutingPlayer).filter(ScoutingPlayer.xg_per90.isnot(None))
    try:
        if min_minutes > 0:
            query = query.filter(ScoutingPlayer.minutes_season >= min_minutes)
    except Exception:
        pass
    if position:
        query = query.filter(ScoutingPlayer.position.ilike(f"%{position}%"))

    return [
        {
            "id":              p.id,
            "name":            p.name,
            "club":            p.club,
            "position":        p.position,
            "nationality":     p.nationality,
            "age":             p.age,
            "xg_per90":        p.xg_per90,
            "xa_per90":        _g(p, "xa_per90"),
            "npxg_per90":      _g(p, "npxg_per90"),
            "finishing_score": _g(p, "finishing_score"),
            "finishing_pct":   _g(p, "finishing_pct"),
            "minutes":         _g(p, "minutes_season"),
        }
        for p in query.order_by(desc(ScoutingPlayer.xg_per90)).limit(limit).all()
    ]


@router.get("/overperforming")
def overperforming(
    limit:       int           = Query(20, ge=1, le=100),
    min_minutes: int           = Query(300, ge=0),
    position:    Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ScoutingPlayer).filter(ScoutingPlayer.xg_per90.isnot(None))
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
        minutes = _g(p, "minutes_season")
        goals   = _g(p, "goals_season")
        if not minutes or goals is None:
            continue
        xg_total = p.xg_per90 * (minutes / 90)
        delta    = goals - xg_total
        result.append({
            "id": p.id, "name": p.name, "club": p.club,
            "position": p.position, "nationality": p.nationality, "age": p.age,
            "goals": goals, "xg_per90": p.xg_per90, "xa_per90": _g(p, "xa_per90"),
            "xg_estimated": round(xg_total, 2), "delta": round(delta, 2),
            "minutes": minutes, "finishing_pct": _g(p, "finishing_pct"),
        })

    result.sort(key=lambda x: x["delta"], reverse=True)
    return result[:limit]


@router.get("/underperforming")
def underperforming(
    limit:       int           = Query(20, ge=1, le=100),
    min_minutes: int           = Query(300, ge=0),
    position:    Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ScoutingPlayer).filter(ScoutingPlayer.xg_per90.isnot(None))
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
        minutes = _g(p, "minutes_season")
        goals   = _g(p, "goals_season")
        if not minutes or goals is None:
            continue
        xg_total = p.xg_per90 * (minutes / 90)
        delta    = goals - xg_total
        result.append({
            "id": p.id, "name": p.name, "club": p.club,
            "position": p.position, "nationality": p.nationality, "age": p.age,
            "goals": goals, "xg_per90": p.xg_per90, "xa_per90": _g(p, "xa_per90"),
            "xg_estimated": round(xg_total, 2), "delta": round(delta, 2),
            "minutes": minutes, "finishing_pct": _g(p, "finishing_pct"),
        })

    result.sort(key=lambda x: x["delta"])
    return result[:limit]


@router.get("/compare")
def compare_players(
    name1: str = Query(...),
    name2: str = Query(...),
    db: Session = Depends(get_db),
):
    def _find(name):
        p = db.query(ScoutingPlayer).filter(
            ScoutingPlayer.name.ilike(f"%{name.strip()}%")
        ).first()
        if not p:
            raise HTTPException(404, f"Giocatore '{name}' non trovato")
        return p

    p1, p2 = _find(name1), _find(name2)

    def _diff(a, b):
        if a is None or b is None:
            return None
        try:
            return round(float(a) - float(b), 3)
        except (TypeError, ValueError):
            return None

    METRICS = [
        "xg_per90", "xa_per90", "npxg_per90", "xgchain_per90", "xgbuildup_per90",
        "finishing_score", "creativity_score", "pressing_score",
        "carrying_score", "defending_obj_score", "buildup_obj_score",
        "finishing_pct", "creativity_pct", "pressing_pct",
        "carrying_pct", "defending_pct", "buildup_pct",
        "heading_score", "build_up_score", "defensive_score",
        "aerial_duels_won_pct", "duels_won_pct",
        "progressive_passes", "progressive_carries",
    ]

    return {
        "player1": _player_dict(p1),
        "player2": _player_dict(p2),
        "diff":    {m: _diff(_g(p1, m), _g(p2, m)) for m in METRICS},
    }