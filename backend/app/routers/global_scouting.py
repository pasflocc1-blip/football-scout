"""
routers/global_scouting.py — v2.0 (fix post-ristrutturazione DB)
-----------------------------------------------------------------
FIX: xg_per90, xa_per90, ecc. sono ora in player_season_stats.
     Le query fanno JOIN con PlayerSeasonStats e aggregano per player.

GET  /global-scouting/search
GET  /global-scouting/top-xg
GET  /global-scouting/overperforming
GET  /global-scouting/underperforming
GET  /global-scouting/compare
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from typing import Optional

from app.database import get_db
from app.models.models import ScoutingPlayer, PlayerSeasonStats

router = APIRouter(prefix="/global-scouting", tags=["Global Scouting"])


def _g(obj, attr, default=None):
    return getattr(obj, attr, default)


def _get_season_stats_subquery(db: Session):
    """
    Subquery che aggrega player_season_stats per player_id:
    prende i valori dalla stagione più recente (max fetched_at per player).
    """
    # Subquery: per ogni player, prende la riga con il rating più alto
    # (proxy per "stagione più importante / campionato principale")
    latest = (
        db.query(
            PlayerSeasonStats.player_id,
            func.max(PlayerSeasonStats.xg_per90).label("xg_per90"),
            func.max(PlayerSeasonStats.xa_per90).label("xa_per90"),
            func.max(PlayerSeasonStats.npxg_per90).label("npxg_per90"),
            func.max(PlayerSeasonStats.xgchain_per90).label("xgchain_per90"),
            func.max(PlayerSeasonStats.xgbuildup_per90).label("xgbuildup_per90"),
            func.sum(PlayerSeasonStats.goals).label("goals_season"),
            func.sum(PlayerSeasonStats.assists).label("assists_season"),
            func.sum(PlayerSeasonStats.minutes_played).label("minutes_season"),
            func.sum(PlayerSeasonStats.appearances).label("games_season"),
            func.sum(PlayerSeasonStats.shots_total).label("shots_season"),
            func.sum(PlayerSeasonStats.key_passes).label("key_passes_season"),
            func.max(PlayerSeasonStats.sofascore_rating).label("sofascore_rating"),
        )
        .group_by(PlayerSeasonStats.player_id)
        .subquery()
    )
    return latest


def _player_dict_with_stats(p: ScoutingPlayer, stats) -> dict:
    """Costruisce dict giocatore unendo ScoutingPlayer e stats aggregate."""
    return {
        "id":                   p.id,
        "name":                 p.name,
        "position":             p.position,
        "club":                 p.club,
        "nationality":          p.nationality,
        "age":                  p.age,
        "preferred_foot":       p.preferred_foot,
        "sofascore_id":         p.sofascore_id,
        "market_value":         p.market_value,
        # xG / xA (da PlayerSeasonStats)
        "xg_per90":             getattr(stats, "xg_per90", None) if stats else None,
        "xa_per90":             getattr(stats, "xa_per90", None) if stats else None,
        "npxg_per90":           getattr(stats, "npxg_per90", None) if stats else None,
        "xgchain_per90":        getattr(stats, "xgchain_per90", None) if stats else None,
        "xgbuildup_per90":      getattr(stats, "xgbuildup_per90", None) if stats else None,
        # Stagione aggregata
        "goals_season":         getattr(stats, "goals_season", None) if stats else None,
        "assists_season":       getattr(stats, "assists_season", None) if stats else None,
        "minutes_season":       getattr(stats, "minutes_season", None) if stats else None,
        "games_season":         getattr(stats, "games_season", None) if stats else None,
        "shots_season":         getattr(stats, "shots_season", None) if stats else None,
        "key_passes_season":    getattr(stats, "key_passes_season", None) if stats else None,
        "sofascore_rating":     getattr(stats, "sofascore_rating", None) if stats else p.sofascore_rating,
        # Score oggettivi (Fase 3) - ancora su ScoutingPlayer
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
        # Score legacy
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
    sq = _get_season_stats_subquery(db)

    query = (
        db.query(ScoutingPlayer, sq)
        .outerjoin(sq, ScoutingPlayer.id == sq.c.player_id)
    )

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
        query = query.filter(sq.c.xg_per90 >= min_xg)
    if min_xa is not None:
        query = query.filter(sq.c.xa_per90 >= min_xa)
    if preferred_foot:
        query = query.filter(ScoutingPlayer.preferred_foot.ilike(preferred_foot))

    # Mappa ordinamento
    _SORT = {
        "name":             ScoutingPlayer.name,
        "xg_per90":         sq.c.xg_per90,
        "xa_per90":         sq.c.xa_per90,
        "npxg_per90":       sq.c.npxg_per90,
        "age":              ScoutingPlayer.age,
        "finishing_score":  ScoutingPlayer.finishing_score,
        "creativity_score": ScoutingPlayer.creativity_score,
        "pressing_score":   ScoutingPlayer.pressing_score,
        "carrying_score":   ScoutingPlayer.carrying_score,
        "finishing_pct":    ScoutingPlayer.finishing_pct,
        "creativity_pct":   ScoutingPlayer.creativity_pct,
        "minutes_season":   sq.c.minutes_season,
        "goals_season":     sq.c.goals_season,
    }
    sort_col = _SORT.get(sort_by, ScoutingPlayer.name)
    order_fn = desc if sort_dir == "desc" else asc
    query = query.order_by(order_fn(sort_col))

    rows = query.limit(limit).all()
    #return [_player_dict_with_stats(p, stats) for p, stats in rows]
    return [_player_dict_with_stats(row[0], row) for row in rows]


@router.get("/top-xg")
def top_xg(
    limit:       int           = Query(20, ge=1, le=100),
    min_minutes: int           = Query(300, ge=0),
    position:    Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    sq = _get_season_stats_subquery(db)

    query = (
        db.query(ScoutingPlayer, sq)
        .join(sq, ScoutingPlayer.id == sq.c.player_id)
        .filter(sq.c.xg_per90.isnot(None))
    )
    if min_minutes > 0:
        query = query.filter(sq.c.minutes_season >= min_minutes)
    if position:
        query = query.filter(ScoutingPlayer.position.ilike(f"%{position}%"))

    rows = query.order_by(desc(sq.c.xg_per90)).limit(limit).all()

    return [
        {
            "id":              row[0].id,
            "name":            row[0].name,
            "club":            row[0].club,
            "position":        row[0].position,
            "nationality":     row[0].nationality,
            "age":             row[0].age,
            "xg_per90":        row.xg_per90,
            "xa_per90":        row.xa_per90,
            "npxg_per90":      row.npxg_per90,
            "finishing_score": _g(row[0], "finishing_score"),
            "finishing_pct":   _g(row[0], "finishing_pct"),
            "minutes":         row.minutes_season,
        }
        for row in rows
    ]


@router.get("/overperforming")
def overperforming(
    limit:       int           = Query(20, ge=1, le=100),
    min_minutes: int           = Query(300, ge=0),
    position:    Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    sq = _get_season_stats_subquery(db)

    query = (
        db.query(ScoutingPlayer, sq)
        .join(sq, ScoutingPlayer.id == sq.c.player_id)
        .filter(sq.c.xg_per90.isnot(None))
        .filter(sq.c.goals_season.isnot(None))
    )
    if min_minutes > 0:
        query = query.filter(sq.c.minutes_season >= min_minutes)
    if position:
        query = query.filter(ScoutingPlayer.position.ilike(f"%{position}%"))

    result = []
    for row in query.all():
        p = row[0]
        stats = row
        minutes = stats.minutes_season
        goals = stats.goals_season
        if not minutes or goals is None:
            continue
        xg_total = stats.xg_per90 * (minutes / 90)
        delta = goals - xg_total
        result.append({
            "id": p.id, "name": p.name, "club": p.club,
            "position": p.position, "nationality": p.nationality, "age": p.age,
            "goals": goals, "xg_per90": stats.xg_per90, "xa_per90": stats.xa_per90,
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
    sq = _get_season_stats_subquery(db)

    query = (
        db.query(ScoutingPlayer, sq)
        .join(sq, ScoutingPlayer.id == sq.c.player_id)
        .filter(sq.c.xg_per90.isnot(None))
        .filter(sq.c.goals_season.isnot(None))
    )
    if min_minutes > 0:
        query = query.filter(sq.c.minutes_season >= min_minutes)
    if position:
        query = query.filter(ScoutingPlayer.position.ilike(f"%{position}%"))

    result = []
    for row in query.all():
        p = row[0]
        stats = row
        minutes = stats.minutes_season
        goals = stats.goals_season
        if not minutes or goals is None:
            continue
        xg_total = stats.xg_per90 * (minutes / 90)
        delta = goals - xg_total
        result.append({
            "id": p.id, "name": p.name, "club": p.club,
            "position": p.position, "nationality": p.nationality, "age": p.age,
            "goals": goals, "xg_per90": stats.xg_per90, "xa_per90": stats.xa_per90,
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
    sq = _get_season_stats_subquery(db)

    def _find(name):
        row = (
            db.query(ScoutingPlayer, sq)
            .outerjoin(sq, ScoutingPlayer.id == sq.c.player_id)
            .filter(ScoutingPlayer.name.ilike(f"%{name.strip()}%"))
            .first()
        )
        if not row:
            raise HTTPException(404, f"Giocatore '{name}' non trovato")
        return row

    row1 = _find(name1)
    p1, s1 = row1[0], row1

    row2 = _find(name2)
    p2, s2 = row2[0], row2
    def _diff(a, b):
        if a is None or b is None:
            return None
        try:
            return round(float(a) - float(b), 3)
        except (TypeError, ValueError):
            return None

    d1 = _player_dict_with_stats(p1, s1)
    d2 = _player_dict_with_stats(p2, s2)

    METRICS = [
        "xg_per90", "xa_per90", "npxg_per90", "xgchain_per90", "xgbuildup_per90",
        "finishing_score", "creativity_score", "pressing_score",
        "carrying_score", "defending_obj_score", "buildup_obj_score",
        "finishing_pct", "creativity_pct", "pressing_pct",
        "carrying_pct", "defending_pct", "buildup_pct",
        "heading_score", "build_up_score", "defensive_score",
    ]

    return {
        "player1": d1,
        "player2": d2,
        "diff":    {m: _diff(d1.get(m), d2.get(m)) for m in METRICS},
    }