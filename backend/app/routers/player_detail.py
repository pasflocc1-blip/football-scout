"""
routers/player_detail.py
------------------------
Endpoint per il dettaglio completo di un giocatore (stile SofaScore).

GET  /players/{player_id}/detail     → profilo + stats per competizione + carriera + nazionale
GET  /players/{player_id}/matches    → ultime partite
GET  /players/{player_id}/heatmap    → heatmap stagionale
GET  /players/search-by-name?name=   → cerca per nome (per autocomplete)

PATCH v2:
  - get_player_detail: aggiunge heatmap_points per competition (join su season+league)
  - get_player_detail: aggiunge competition_id e competition_name (attesi dal Vue)
  - get_player_detail: aggiunge sofascore_attributes e sofascore_attributes_avg
    letti dalla nuova colonna ScoutingPlayer.sofascore_attributes_raw (JSON)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional

from app.database import get_db
from app.models.models import (
    ScoutingPlayer,
    PlayerSeasonStats,
    PlayerMatch,
    PlayerHeatmap,
    PlayerCareer,
    PlayerNationalStats,
)

router = APIRouter(prefix="/players", tags=["Player Detail"])


def _fmt(v, decimals=2):
    if v is None:
        return None
    try:
        return round(float(v), decimals)
    except (TypeError, ValueError):
        return None


@router.get("/search-by-name")
def search_by_name(
    name: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Ricerca rapida per nome (per autocomplete nella UI)."""
    players = (
        db.query(ScoutingPlayer)
        .filter(ScoutingPlayer.name.ilike(f"%{name}%"))
        .order_by(ScoutingPlayer.name)
        .limit(limit)
        .all()
    )
    return [
        {
            "id":       p.id,
            "name":     p.name,
            "club":     p.club,
            "position": p.position,
            "age":      p.age,
        }
        for p in players
    ]


@router.get("/{player_id}/detail")
def get_player_detail(
    player_id: int,
    db: Session = Depends(get_db),
):
    """
    Restituisce il profilo completo del giocatore con tutte le statistiche
    organizzate per competizione, più carriera e nazionale.

    Il response include:
      - competitions[].competition_id    → id univoco della riga (usato dal Vue per il canvas)
      - competitions[].competition_name  → nome leggibile (usato nel titolo heatmap)
      - competitions[].heatmap_points    → lista [{x, y}] da PlayerHeatmap, join su season+league
      - sofascore_attributes             → lista [{attacking, technical, tactical, defending,
                                                   creativity, yearShift}]
      - sofascore_attributes_avg         → lista con i valori medi (None se non disponibile)
    """
    player = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == player_id).first()
    if not player:
        raise HTTPException(404, f"Giocatore {player_id} non trovato")

    # ── Heatmap: precarica tutte le righe del giocatore ──────────────
    # Chiave: (season, league) → points[]
    # La chiave viene usata nel loop competitions per iniettare heatmap_points
    # senza fare una query per ogni competizione.
    heatmaps_raw = (
        db.query(PlayerHeatmap)
        .filter(PlayerHeatmap.player_id == player_id)
        .all()
    )
    heatmap_map: dict[tuple, list] = {
        (h.season, h.league): h.points or []
        for h in heatmaps_raw
    }

    # ── Statistiche per competizione ─────────────────────────────────
    season_stats = (
        db.query(PlayerSeasonStats)
        .filter(PlayerSeasonStats.player_id == player_id)
        .order_by(desc(PlayerSeasonStats.fetched_at))
        .all()
    )

    competitions = []
    for s in season_stats:
        # Recupera i punti heatmap per questa (season, league)
        # Se non esistono, lista vuota — il Vue mostra "Nessun dato heatmap"
        heat_pts = heatmap_map.get((s.season, s.league), [])

        competitions.append({
            # ── Identificatori per il Vue ──────────────────────────
            # competition_id: usato come chiave per il ref del canvas heatmap (riga 324 Vue)
            "competition_id":   s.id,
            # competition_name: usato nel titolo della card heatmap (riga 294 Vue)
            "competition_name": s.league,
            # ── Campi esistenti ────────────────────────────────────
            "id":              s.id,
            "season":          s.season,
            "league":          s.league,
            "source":          s.source,
            "tournament_id":   s.tournament_id,
            "season_id":       s.season_id,
            # Heatmap iniettata: [{x: float, y: float}, ...]
            # Il Vue usa p.count || 1 come fallback — count non è richiesto
            "heatmap_points":  heat_pts,
            # Rating & presenze
            "sofascore_rating": _fmt(s.sofascore_rating, 2),
            "appearances":      s.appearances,
            "matches_started":  s.matches_started,
            "minutes_played":   s.minutes_played,
            # Attacco
            "goals":            s.goals,
            "assists":          s.assists,
            "goals_assists_sum": s.goals_assists_sum,
            "shots_total":      s.shots_total,
            "shots_on_target":  s.shots_on_target,
            "big_chances_created": s.big_chances_created,
            "big_chances_missed":  s.big_chances_missed,
            "goal_conversion_pct": _fmt(s.goal_conversion_pct, 1),
            # xG/xA
            "xg":               _fmt(s.xg, 2),
            "xa":               _fmt(s.xa, 2),
            "xg_per90":         _fmt(s.xg_per90, 3),
            "xa_per90":         _fmt(s.xa_per90, 3),
            "npxg_per90":       _fmt(s.npxg_per90, 3),
            # Passaggi
            "accurate_passes":      s.accurate_passes,
            "total_passes":         s.total_passes,
            "pass_accuracy_pct":    _fmt(s.pass_accuracy_pct, 1),
            "key_passes":           s.key_passes,
            "accurate_crosses":     s.accurate_crosses,
            "cross_accuracy_pct":   _fmt(s.cross_accuracy_pct, 1),
            "accurate_long_balls":  s.accurate_long_balls,
            "long_ball_accuracy_pct": _fmt(s.long_ball_accuracy_pct, 1),
            # Dribbling & Duelli
            "successful_dribbles":  s.successful_dribbles,
            "dribble_success_pct":  _fmt(s.dribble_success_pct, 1),
            "ground_duels_won_pct": _fmt(s.ground_duels_won_pct, 1),
            "aerial_duels_won":     s.aerial_duels_won,
            "aerial_duels_won_pct": _fmt(s.aerial_duels_won_pct, 1),
            "total_duels_won_pct":  _fmt(s.total_duels_won_pct, 1),
            # Difesa
            "tackles":           s.tackles,
            "tackles_won_pct":   _fmt(s.tackles_won_pct, 1),
            "interceptions":     s.interceptions,
            "clearances":        s.clearances,
            "blocked_shots":     s.blocked_shots,
            "ball_recovery":     s.ball_recovery,
            # Disciplina
            "yellow_cards":      s.yellow_cards,
            "red_cards":         s.red_cards,
            "fouls_committed":   s.fouls_committed,
            "fouls_won":         s.fouls_won,
            # Portiere
            "saves":             s.saves,
            "goals_conceded":    s.goals_conceded,
            "clean_sheets":      s.clean_sheets,
            "penalty_saved":     s.penalty_saved,
        })

    # ── Carriera / trasferimenti ──────────────────────────────────────
    career = (
        db.query(PlayerCareer)
        .filter(PlayerCareer.player_id == player_id)
        .order_by(desc(PlayerCareer.transfer_date))
        .all()
    )
    career_list = [
        {
            "from_team":     c.from_team,
            "to_team":       c.to_team,
            "transfer_date": c.transfer_date.isoformat() if c.transfer_date else None,
            "fee":           c.fee,
            "transfer_type": c.transfer_type,
            "season":        c.season,
        }
        for c in career
    ]

    # ── Statistiche in nazionale ──────────────────────────────────────
    national = (
        db.query(PlayerNationalStats)
        .filter(PlayerNationalStats.player_id == player_id)
        .all()
    )
    national_list = [
        {
            "national_team": n.national_team,
            "appearances":   n.appearances,
            "goals":         n.goals,
            "assists":       n.assists,
            "minutes":       n.minutes,
            "rating":        _fmt(n.rating, 2),
            "yellow_cards":  n.yellow_cards,
            "red_cards":     n.red_cards,
        }
        for n in national
    ]

    # ── Score / Percentili ────────────────────────────────────────────
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

    # ── Attributi SofaScore ───────────────────────────────────────────
    # Letti da ScoutingPlayer.sofascore_attributes_raw (colonna JSON).
    # L'RPA salva un dict piatto: {"attr_attacking": 72, "attr_technical": 68, ...}
    # Lo trasformiamo nel formato atteso dal Vue:
    #   sofascore_attributes:     [{attacking, technical, tactical, defending, creativity, yearShift}]
    #   sofascore_attributes_avg: [{attacking, technical, tactical, defending, creativity}]
    sofascore_attributes = None
    sofascore_attributes_avg = None

    attrs_raw = getattr(player, 'sofascore_attributes_raw', None)
    if attrs_raw and isinstance(attrs_raw, dict):
        # Struttura piatta da _map_attributes() dell'RPA
        # Chiavi player: attr_attacking, attr_technical, attr_tactical, attr_defending, attr_creativity
        # Chiavi media:  attr_avg_<gruppo> (meno affidabili, spesso non presenti)
        player_attrs = {
            "attacking":  attrs_raw.get("attr_attacking"),
            "technical":  attrs_raw.get("attr_technical"),
            "tactical":   attrs_raw.get("attr_tactical"),
            "defending":  attrs_raw.get("attr_defending"),
            "creativity": attrs_raw.get("attr_creativity"),
            "yearShift":  0,
        }
        # Esponi solo se almeno un valore è presente
        if any(v is not None for k, v in player_attrs.items() if k != "yearShift"):
            sofascore_attributes = [player_attrs]

        # Media: cerca chiavi attr_avg_* nel dict
        avg_vals = {k: v for k, v in attrs_raw.items() if k.startswith("attr_avg_")}
        if avg_vals:
            # Tentiamo di mappare i nomi gruppo ai nomi asse del radar
            # (SofaScore usa titoli localizzati — usiamo un mapping best-effort)
            GROUP_MAP = {
                "attacking": ["attr_avg_Attacco", "attr_avg_Attack", "attr_avg_Attacking"],
                "technical":  ["attr_avg_Tecnica", "attr_avg_Technical", "attr_avg_Technique"],
                "tactical":   ["attr_avg_Tattica", "attr_avg_Tactical"],
                "defending":  ["attr_avg_Difesa", "attr_avg_Defense", "attr_avg_Defending"],
                "creativity": ["attr_avg_Creatività", "attr_avg_Creativity", "attr_avg_Creative"],
            }
            avg_entry = {}
            for axis, candidates in GROUP_MAP.items():
                for candidate in candidates:
                    if candidate in avg_vals:
                        avg_entry[axis] = avg_vals[candidate]
                        break
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
        "scores":            scores,
        "competitions":      competitions,
        "career":            career_list,
        "national_stats":    national_list,
        # Attributi SofaScore (None se non ancora scaricati dall'RPA)
        "sofascore_attributes":     sofascore_attributes,
        "sofascore_attributes_avg": sofascore_attributes_avg,
        "last_updated_sofascore": player.last_updated_sofascore.isoformat() if player.last_updated_sofascore else None,
    }


@router.get("/{player_id}/matches")
def get_player_matches(
    player_id: int,
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Ultime partite del giocatore."""
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
                "event_id":      m.event_id,
                "date":          m.date.isoformat() if m.date else None,
                "season":        m.season,
                "tournament":    m.tournament,
                "home_team":     m.home_team,
                "away_team":     m.away_team,
                "home_score":    m.home_score,
                "away_score":    m.away_score,
                "rating":        _fmt(m.rating, 2),
                "minutes_played": m.minutes_played,
                "goals":         m.goals,
                "assists":       m.assists,
                "yellow_card":   m.yellow_card,
                "red_card":      m.red_card,
            }
            for m in matches
        ]
    }


@router.get("/{player_id}/heatmap")
def get_player_heatmap(
    player_id: int,
    league: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Dati heatmap del giocatore."""
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
        ]
    }