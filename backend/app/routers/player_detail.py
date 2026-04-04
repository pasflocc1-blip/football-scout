"""
routers/player_detail.py  — v3.0
----------------------------------
MODIFICHE:
  1. search_by_name: deduplicazione per nome con ROW_NUMBER()
     → una sola riga per giocatore nell'autocomplete (la più recente)
  2. get_player_detail: aggiunge sofascore_attributes_avg_raw,
     competition_id/name, heatmap_points nelle competitions
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional

from app.database import get_db
from app.models.models import (
    ScoutingPlayer, PlayerSeasonStats, PlayerMatch,
    PlayerHeatmap, PlayerCareer, PlayerNationalStats,
)

router = APIRouter(prefix="/players", tags=["Player Detail"])


def _fmt(v, decimals=2):
    if v is None:
        return None
    try:
        return round(float(v), decimals)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────
# AUTOCOMPLETE — una riga per nome (più recente)
# ─────────────────────────────────────────────────────────────────

@router.get("/search-by-name")
def search_by_name(
    name: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Ricerca per nome con deduplicazione.

    Problema: con season_club in scouting_players, lo stesso giocatore
    può avere N righe (una per stagione). Questa query ritorna sempre
    e solo la riga più recente per ogni nome, evitando duplicati
    nella dropdown.

    Equivalente SQL Postgres:
      SELECT * FROM (
        SELECT *,
          ROW_NUMBER() OVER (
            PARTITION BY name
            ORDER BY last_updated_sofascore DESC NULLS LAST, id DESC
          ) AS rn
        FROM scouting_players
        WHERE name ILIKE '%<term>%'
      ) t WHERE rn = 1
      ORDER BY name LIMIT <n>;
    """
    # Step 1: subquery che assegna rn=1 alla riga più recente per ogni nome
    subq = (
        db.query(
            ScoutingPlayer.id,
            func.row_number().over(
                partition_by=ScoutingPlayer.name,
                order_by=[
                    ScoutingPlayer.last_updated_sofascore.desc().nullslast(),
                    ScoutingPlayer.id.desc(),
                ],
            ).label("rn"),
        )
        .filter(ScoutingPlayer.name.ilike(f"%{name}%"))
        .subquery()
    )

    # Step 2: join e filtro su rn=1
    players = (
        db.query(ScoutingPlayer)
        .join(subq, ScoutingPlayer.id == subq.c.id)
        .filter(subq.c.rn == 1)
        .order_by(ScoutingPlayer.name)
        .limit(limit)
        .all()
    )

    return [
        {
            "id":          p.id,
            "name":        p.name,
            "club":        p.club,
            "position":    p.position,
            "age":         p.age,
            "season_club": getattr(p, "season_club", None),
        }
        for p in players
    ]


# ─────────────────────────────────────────────────────────────────
# DETAIL
# ─────────────────────────────────────────────────────────────────

@router.get("/{player_id}/detail")
def get_player_detail(player_id: int, db: Session = Depends(get_db)):
    player = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == player_id).first()
    if not player:
        raise HTTPException(404, f"Giocatore {player_id} non trovato")

    # Heatmap map (season, league) → points
    heatmap_map = {
        (h.season, h.league): h.points or []
        for h in db.query(PlayerHeatmap)
            .filter(PlayerHeatmap.player_id == player_id).all()
    }

    # Competitions
    season_stats = (
        db.query(PlayerSeasonStats)
        .filter(PlayerSeasonStats.player_id == player_id)
        .order_by(desc(PlayerSeasonStats.fetched_at))
        .all()
    )

    competitions = []
    for s in season_stats:
        competitions.append({
            "competition_id":   s.id,
            "competition_name": s.league,
            "heatmap_points":   heatmap_map.get((s.season, s.league), []),
            "id":              s.id,
            "season":          s.season,
            "league":          s.league,
            "source":          s.source,
            "tournament_id":   s.tournament_id,
            "season_id":       s.season_id,
            "sofascore_rating": _fmt(s.sofascore_rating, 2),
            "appearances":      s.appearances,
            "matches_started":  s.matches_started,
            "minutes_played":   s.minutes_played,
            "goals":            s.goals,
            "assists":          s.assists,
            "goals_assists_sum": s.goals_assists_sum,
            "shots_total":      s.shots_total,
            "shots_on_target":  s.shots_on_target,
            "big_chances_created": s.big_chances_created,
            "big_chances_missed":  s.big_chances_missed,
            "goal_conversion_pct": _fmt(s.goal_conversion_pct, 1),
            "xg":               _fmt(s.xg, 2),
            "xa":               _fmt(s.xa, 2),
            "xg_per90":         _fmt(s.xg_per90, 3),
            "xa_per90":         _fmt(s.xa_per90, 3),
            "npxg_per90":       _fmt(s.npxg_per90, 3),
            "accurate_passes":      s.accurate_passes,
            "total_passes":         s.total_passes,
            "pass_accuracy_pct":    _fmt(s.pass_accuracy_pct, 1),
            "key_passes":           s.key_passes,
            "accurate_crosses":     s.accurate_crosses,
            "cross_accuracy_pct":   _fmt(s.cross_accuracy_pct, 1),
            "accurate_long_balls":  s.accurate_long_balls,
            "long_ball_accuracy_pct": _fmt(s.long_ball_accuracy_pct, 1),
            "successful_dribbles":  s.successful_dribbles,
            "dribble_success_pct":  _fmt(s.dribble_success_pct, 1),
            "ground_duels_won_pct": _fmt(s.ground_duels_won_pct, 1),
            "aerial_duels_won":     s.aerial_duels_won,
            "aerial_duels_won_pct": _fmt(s.aerial_duels_won_pct, 1),
            "total_duels_won_pct":  _fmt(s.total_duels_won_pct, 1),
            "tackles":           s.tackles,
            "tackles_won_pct":   _fmt(s.tackles_won_pct, 1),
            "interceptions":     s.interceptions,
            "clearances":        s.clearances,
            "blocked_shots":     s.blocked_shots,
            "ball_recovery":     s.ball_recovery,
            "yellow_cards":      s.yellow_cards,
            "red_cards":         s.red_cards,
            "fouls_committed":   s.fouls_committed,
            "fouls_won":         s.fouls_won,
            "saves":             s.saves,
            "goals_conceded":    s.goals_conceded,
            "clean_sheets":      s.clean_sheets,
            "penalty_saved":     s.penalty_saved,
        })

    # Career
    career_list = [
        {
            "from_team":     c.from_team,
            "to_team":       c.to_team,
            "transfer_date": c.transfer_date.isoformat() if c.transfer_date else None,
            "fee":           c.fee,
            "transfer_type": c.transfer_type,
            "season":        c.season,
        }
        for c in db.query(PlayerCareer)
            .filter(PlayerCareer.player_id == player_id)
            .order_by(desc(PlayerCareer.transfer_date)).all()
    ]

    # National
    national_list = [
        {
            "national_team": n.national_team,
            "season":        getattr(n, "season", None),
            "appearances":   n.appearances,
            "goals":         n.goals,
            "assists":       n.assists,
            "minutes":       n.minutes,
            "rating":        _fmt(n.rating, 2),
            "yellow_cards":  n.yellow_cards,
            "red_cards":     n.red_cards,
        }
        for n in db.query(PlayerNationalStats)
            .filter(PlayerNationalStats.player_id == player_id).all()
    ]

    # Scores
    scores = {
        "finishing_score":     _fmt(player.finishing_score, 1),
        "creativity_score":    _fmt(player.creativity_score, 1),
        "pressing_score":      _fmt(player.pressing_score, 1),
        "carrying_score":      _fmt(player.carrying_score, 1),
        "defending_obj_score": _fmt(player.defending_obj_score, 1),
        "buildup_obj_score":   _fmt(player.buildup_obj_score, 1),
        "finishing_pct":       _fmt(player.finishing_pct, 1),
        "creativity_pct":      _fmt(player.creativity_pct, 1),
        "pressing_pct":        _fmt(player.pressing_pct, 1),
        "carrying_pct":        _fmt(player.carrying_pct, 1),
        "defending_pct":       _fmt(player.defending_pct, 1),
        "buildup_pct":         _fmt(player.buildup_pct, 1),
        "heading_score":       _fmt(player.heading_score, 1),
        "build_up_score":      _fmt(player.build_up_score, 1),
        "defensive_score":     _fmt(player.defensive_score, 1),
    }

    # ── Attributi SofaScore ───────────────────────────────────────
    sofascore_attributes = None
    sofascore_attributes_avg = None

    attrs_raw = getattr(player, "sofascore_attributes_raw", None)
    if attrs_raw and isinstance(attrs_raw, dict):
        entry = {
            "attacking":  attrs_raw.get("attr_attacking"),
            "technical":  attrs_raw.get("attr_technical"),
            "tactical":   attrs_raw.get("attr_tactical"),
            "defending":  attrs_raw.get("attr_defending"),
            "creativity": attrs_raw.get("attr_creativity"),
            "yearShift":  0,
        }
        if any(v is not None for k, v in entry.items() if k != "yearShift"):
            sofascore_attributes = [entry]

    # Media: prima cerca in sofascore_attributes_avg_raw (nuova colonna)
    # poi fallback su chiavi attr_avg_* in sofascore_attributes_raw (vecchio formato)
    def _build_avg_entry(src: dict) -> Optional[dict]:
        """Estrae i 5 assi del radar dalla media, supporta struttura piatta e a gruppi."""
        # Struttura piatta: attr_attacking, attr_technical, ...
        entry = {
            "attacking":  src.get("attr_attacking"),
            "technical":  src.get("attr_technical"),
            "tactical":   src.get("attr_tactical"),
            "defending":  src.get("attr_defending"),
            "creativity": src.get("attr_creativity"),
        }
        if any(v is not None for v in entry.values()):
            return entry
        # Struttura a gruppi: attr_avg_Attacco, attr_avg_Tecnica, ...
        GROUP_MAP = {
            "attacking": ["attr_avg_Attacco",    "attr_avg_Attack",    "attr_avg_Attacking"],
            "technical": ["attr_avg_Tecnica",    "attr_avg_Technical", "attr_avg_Technique"],
            "tactical":  ["attr_avg_Tattica",    "attr_avg_Tactical"],
            "defending": ["attr_avg_Difesa",     "attr_avg_Defense",   "attr_avg_Defending"],
            "creativity":["attr_avg_Creatività", "attr_avg_Creativity"],
        }
        entry = {}
        for axis, candidates in GROUP_MAP.items():
            for cand in candidates:
                if src.get(cand) is not None:
                    entry[axis] = src[cand]
                    break
        return entry if any(v is not None for v in entry.values()) else None

    attrs_avg_raw = getattr(player, "sofascore_attributes_avg_raw", None)
    if attrs_avg_raw and isinstance(attrs_avg_raw, dict):
        avg_entry = _build_avg_entry(attrs_avg_raw)
        if avg_entry:
            sofascore_attributes_avg = [avg_entry]
    elif attrs_raw and isinstance(attrs_raw, dict):
        # Fallback: vecchio formato dove _map_attributes metteva tutto insieme
        avg_entry = _build_avg_entry(attrs_raw)
        if avg_entry:
            sofascore_attributes_avg = [avg_entry]

    return {
        "id":                player.id,
        "name":              player.name,
        "position":          player.position,
        "position_detail":   player.position_detail,
        "club":              player.club,
        "nationality":       player.nationality,
        "age":               player.age,
        "birth_date":        player.birth_date.isoformat() if player.birth_date else None,
        "preferred_foot":    player.preferred_foot,
        "height":            player.height,
        "weight":            player.weight,
        "jersey_number":     player.jersey_number,
        "gender":            player.gender,
        "market_value":      player.market_value,
        "contract_until":    player.contract_until.isoformat() if player.contract_until else None,
        "sofascore_id":      player.sofascore_id,
        "sofascore_rating":  _fmt(player.sofascore_rating, 2),
        "season_club":       getattr(player, "season_club", None),
        "scores":            scores,
        "competitions":      competitions,
        "career":            career_list,
        "national_stats":    national_list,
        "sofascore_attributes":     sofascore_attributes,
        "sofascore_attributes_avg": sofascore_attributes_avg,
        "last_updated_sofascore": (
            player.last_updated_sofascore.isoformat()
            if player.last_updated_sofascore else None
        ),
    }


# ─────────────────────────────────────────────────────────────────
# MATCHES
# ─────────────────────────────────────────────────────────────────

@router.get("/{player_id}/matches")
def get_player_matches(
    player_id: int,
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    player = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == player_id).first()
    if not player:
        raise HTTPException(404, f"Giocatore {player_id} non trovato")

    matches = (
        db.query(PlayerMatch)
        .filter(PlayerMatch.player_id == player_id)
        .order_by(desc(PlayerMatch.date))
        .limit(limit)
        .all()
    )
    return {
        "player_id":   player_id,
        "player_name": player.name,
        "matches": [
            {
                "event_id":       m.event_id,
                "date":           m.date.isoformat() if m.date else None,
                "season":         m.season,
                "tournament":     m.tournament,
                "home_team":      m.home_team,
                "away_team":      m.away_team,
                "home_score":     m.home_score,
                "away_score":     m.away_score,
                "rating":         _fmt(m.rating, 2),
                "minutes_played": m.minutes_played,
                "goals":          m.goals,
                "assists":        m.assists,
                "yellow_card":    m.yellow_card,
                "red_card":       m.red_card,
            }
            for m in matches
        ],
    }


# ─────────────────────────────────────────────────────────────────
# HEATMAP
# ─────────────────────────────────────────────────────────────────

@router.get("/{player_id}/heatmap")
def get_player_heatmap(
    player_id: int,
    league: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    player = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == player_id).first()
    if not player:
        raise HTTPException(404, f"Giocatore {player_id} non trovato")

    query = db.query(PlayerHeatmap).filter(PlayerHeatmap.player_id == player_id)
    if league:
        query = query.filter(PlayerHeatmap.league.ilike(f"%{league}%"))
    heatmaps = query.order_by(desc(PlayerHeatmap.fetched_at)).all()

    return {
        "player_id":   player_id,
        "player_name": player.name,
        "heatmaps": [
            {
                "season":          h.season,
                "league":          h.league,
                "position_played": h.position_played,
                "point_count":     h.point_count,
                "points":          h.points or [],
                "source":          h.source,
            }
            for h in heatmaps
        ],
    }