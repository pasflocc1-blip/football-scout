"""
app/routers/player_detail_final.py

Versione Unificata:
1. Autocomplete con deduplicazione
2. Struttura dati a tre pilastri: Profile, Scouting (Algoritmo), Sources (FBRef/Sofascore)
3. _fbref_stats_to_dict: tutti i campi di PlayerFbrefStats (completato)
4. Heatmap: array per competizione (heatmaps: [{league, season, points}])
"""

from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List, Dict, Any

from app.database import get_db
from app.models.models import (
    ScoutingPlayer, PlayerSeasonStats, PlayerMatch,
    PlayerHeatmap, PlayerCareer, PlayerNationalStats
)
from app.models.fbref_models import (
    PlayerFbrefStats, PlayerFbrefMatchLog, PlayerScoutingIndex
)
from app.models.sofascore_models import PlayerSofascoreStats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/players", tags=["Player Detail"])


# ─── HELPER PER SERIALIZZAZIONE ──────────────────────────────────

def _fmt(val, decimals: int = 2):
    """Formatta i valori numerici per il JSON."""
    if val is None:
        return None
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return val


def _fbref_stats_to_dict(s: PlayerFbrefStats) -> dict:
    """
    Serializza UNA RIGA PlayerFbrefStats in dict pulito.
    TUTTI i campi del modello sono inclusi.
    """
    return {
        "source":  "fbref",
        "season":  s.season,
        "league":  s.league,

        # ── Standard ─────────────────────────────────────────────
        "appearances":    s.appearances,
        "starts":         s.starts,
        "minutes":        s.minutes,
        "goals":          s.goals,
        "assists":        s.assists,
        "goals_pens":     s.goals_pens,
        "pens_made":      s.pens_made,
        "pens_att":       s.pens_att,
        "yellow_cards":   s.yellow_cards,
        "red_cards":      s.red_cards,
        "xg":             _fmt(s.xg),
        "npxg":           _fmt(s.npxg),
        "xa":             _fmt(s.xa),
        "npxg_xa":        _fmt(s.npxg_xa),
        "goals_per90":    _fmt(s.goals_per90),
        "assists_per90":  _fmt(s.assists_per90),
        "xg_per90":       _fmt(s.xg_per90),
        "xa_per90":       _fmt(s.xa_per90),
        "npxg_per90":     _fmt(s.npxg_per90),

        # ── Shooting ─────────────────────────────────────────────
        "shots":               s.shots,
        "shots_on_target":     s.shots_on_target,
        "shots_on_target_pct": _fmt(s.shots_on_target_pct),
        "shots_per90":         _fmt(s.shots_per90),
        "sot_per90":           _fmt(s.sot_per90),
        "goals_per_shot":      _fmt(s.goals_per_shot),
        "goals_per_sot":       _fmt(s.goals_per_sot),
        "avg_shot_distance":   _fmt(s.avg_shot_distance),
        "npxg_per_shot":       _fmt(s.npxg_per_shot),
        "xg_net":              _fmt(s.xg_net),
        "npxg_net":            _fmt(s.npxg_net),

        # ── Passing ──────────────────────────────────────────────
        "passes_completed":       s.passes_completed,
        "passes_attempted":       s.passes_attempted,
        "pass_completion_pct":    _fmt(s.pass_completion_pct),
        "passes_total_dist":      _fmt(s.passes_total_dist),
        "passes_prog_dist":       _fmt(s.passes_prog_dist),
        "passes_short_pct":       _fmt(s.passes_short_pct),
        "passes_medium_pct":      _fmt(s.passes_medium_pct),
        "passes_long_completed":  s.passes_long_completed,
        "passes_long_attempted":  s.passes_long_attempted,
        "passes_long_pct":        _fmt(s.passes_long_pct),
        "key_passes":             s.key_passes,
        "passes_final_third":     s.passes_final_third,
        "passes_penalty_area":    s.passes_penalty_area,
        "crosses_penalty_area":   s.crosses_penalty_area,
        "progressive_passes":     s.progressive_passes,
        "xa_pass":                _fmt(s.xa_pass),

        # ── GCA ──────────────────────────────────────────────────
        "sca":           s.sca,
        "sca_per90":     _fmt(s.sca_per90),
        "sca_pass_live": s.sca_pass_live,
        "sca_pass_dead": s.sca_pass_dead,
        "sca_take_on":   s.sca_take_on,
        "sca_shot":      s.sca_shot,
        "gca":           s.gca,
        "gca_per90":     _fmt(s.gca_per90),
        "gca_pass_live": s.gca_pass_live,
        "gca_take_on":   s.gca_take_on,

        # ── Defense ──────────────────────────────────────────────
        "tackles":               s.tackles,
        "tackles_won":           s.tackles_won,
        "tackles_def_3rd":       s.tackles_def_3rd,
        "tackles_mid_3rd":       s.tackles_mid_3rd,
        "tackles_att_3rd":       s.tackles_att_3rd,
        "challenge_tackles":     s.challenge_tackles,
        "challenges":            s.challenges,
        "challenge_tackles_pct": _fmt(s.challenge_tackles_pct),
        "blocks":                s.blocks,
        "blocked_shots":         s.blocked_shots,
        "blocked_passes":        s.blocked_passes,
        "interceptions":         s.interceptions,
        "tkl_int":               s.tkl_int,
        "clearances":            s.clearances,
        "errors":                s.errors,

        # ── Possession ───────────────────────────────────────────
        "touches":             s.touches,
        "touches_def_pen":     s.touches_def_pen,
        "touches_def_3rd":     s.touches_def_3rd,
        "touches_mid_3rd":     s.touches_mid_3rd,
        "touches_att_3rd":     s.touches_att_3rd,
        "touches_att_pen":     s.touches_att_pen,
        "take_ons_att":        s.take_ons_att,
        "take_ons_succ":       s.take_ons_succ,
        "take_ons_succ_pct":   _fmt(s.take_ons_succ_pct),
        "take_ons_tackled":    s.take_ons_tackled,
        "carries":             s.carries,
        "carries_prog_dist":   _fmt(s.carries_prog_dist),
        "progressive_carries": s.progressive_carries,
        "carries_final_third": s.carries_final_third,
        "carries_penalty_area": s.carries_penalty_area,
        "miscontrols":         s.miscontrols,
        "dispossessed":        s.dispossessed,
        "progressive_passes_received": s.progressive_passes_received,

        # ── Misc ─────────────────────────────────────────────────
        "fouls_committed": s.fouls_committed,
        "fouls_drawn":     s.fouls_drawn,
        "offsides":        s.offsides,
        "crosses":         s.crosses,
        "pens_won":        s.pens_won,
        "pens_conceded":   s.pens_conceded,
        "own_goals":       s.own_goals,
        "ball_recoveries": s.ball_recoveries,
        "aerials_won":     s.aerials_won,
        "aerials_lost":    s.aerials_lost,
        "aerials_won_pct": _fmt(s.aerials_won_pct),
    }


def _fbref_log_to_dict(m: PlayerFbrefMatchLog) -> dict:
    return {
        "date":            m.date,
        "comp":            m.comp,
        "round":           m.round,
        "venue":           m.venue,
        "result":          m.result,
        "team":            m.team,
        "opponent":        m.opponent,
        "game_started":    m.game_started,
        "position":        m.position,
        "minutes":         m.minutes,
        "goals":           m.goals,
        "assists":         m.assists,
        "shots":           m.shots,
        "shots_on_target": m.shots_on_target,
        "yellow_card":     m.yellow_card,
        "red_card":        m.red_card,
        "crosses":         m.crosses,
        "tackles_won":     m.tackles_won,
        "interceptions":   m.interceptions,
        "fouls_committed": m.fouls_committed,
        "fouls_drawn":     m.fouls_drawn,
    }


def _sofascore_stats_to_dict(s: PlayerSofascoreStats) -> dict:
    return {
        "source":             "sofascore",
        "season":             s.season,
        "league":             s.league,
        "tournament_id":      s.tournament_id,
        "season_id":          s.season_id,
        "sofascore_rating":   _fmt(s.sofascore_rating, 2),
        "appearances":        s.appearances,
        "matches_started":    s.matches_started,
        "minutes_played":     s.minutes_played,
        "goals":              s.goals,
        "assists":            s.assists,
        "goals_assists_sum":  s.goals_assists_sum,
        "shots_total":        s.shots_total,
        "shots_on_target":    s.shots_on_target,
        "shots_off_target":   s.shots_off_target,
        "big_chances_created": s.big_chances_created,
        "big_chances_missed":  s.big_chances_missed,
        "goal_conversion_pct": _fmt(s.goal_conversion_pct, 1),
        "headed_goals":       s.headed_goals,
        "penalty_goals":      s.penalty_goals,
        "penalty_won":        s.penalty_won,
        "xg":                 _fmt(s.xg, 2),
        "xa":                 _fmt(s.xa, 2),
        "xg_per90":           _fmt(s.xg_per90, 3),
        "xa_per90":           _fmt(s.xa_per90, 3),
        # Passaggi
        "accurate_passes":             s.accurate_passes,
        "inaccurate_passes":           s.inaccurate_passes,
        "total_passes":                s.total_passes,
        "pass_accuracy_pct":           _fmt(s.pass_accuracy_pct, 1),
        "accurate_long_balls":         s.accurate_long_balls,
        "long_ball_accuracy_pct":      _fmt(s.long_ball_accuracy_pct, 1),
        "total_long_balls":            s.total_long_balls,
        "accurate_crosses":            s.accurate_crosses,
        "cross_accuracy_pct":          _fmt(s.cross_accuracy_pct, 1),
        "total_crosses":               s.total_crosses,
        "key_passes":                  s.key_passes,
        "accurate_own_half_passes":    s.accurate_own_half_passes,
        "accurate_opp_half_passes":    s.accurate_opp_half_passes,
        "accurate_final_third_passes": s.accurate_final_third_passes,
        # Dribbling
        "successful_dribbles":   s.successful_dribbles,
        "dribble_attempts":      s.dribble_attempts,
        "dribble_success_pct":   _fmt(s.dribble_success_pct, 1),
        "dribbled_past":         s.dribbled_past,
        "dispossessed":          s.dispossessed,
        # Duelli
        "ground_duels_won":      s.ground_duels_won,
        "ground_duels_won_pct":  _fmt(s.ground_duels_won_pct, 1),
        "aerial_duels_won":      s.aerial_duels_won,
        "aerial_duels_lost":     s.aerial_duels_lost,
        "aerial_duels_won_pct":  _fmt(s.aerial_duels_won_pct, 1),
        "total_duels_won":       s.total_duels_won,
        "total_duels_won_pct":   _fmt(s.total_duels_won_pct, 1),
        "total_contest":         s.total_contest,
        # Difesa
        "tackles":               s.tackles,
        "tackles_won":           s.tackles_won,
        "tackles_won_pct":       _fmt(s.tackles_won_pct, 1),
        "interceptions":         s.interceptions,
        "clearances":            s.clearances,
        "blocked_shots":         s.blocked_shots,
        "errors_led_to_goal":    s.errors_led_to_goal,
        "errors_led_to_shot":    s.errors_led_to_shot,
        "ball_recovery":         s.ball_recovery,
        "possession_won_att_third": s.possession_won_att_third,
        # Possesso
        "touches":               s.touches,
        "possession_lost":       s.possession_lost,
        # Disciplina
        "yellow_cards":          s.yellow_cards,
        "yellow_red_cards":      s.yellow_red_cards,
        "red_cards":             s.red_cards,
        "fouls_committed":       s.fouls_committed,
        "fouls_won":             s.fouls_won,
        "offsides":              s.offsides,
        "hit_woodwork":          s.hit_woodwork,
        # Portiere
        "saves":                 s.saves,
        "goals_conceded":        s.goals_conceded,
        "clean_sheets":          s.clean_sheets,
        "penalty_saved":         s.penalty_saved,
        "penalty_faced":         s.penalty_faced,
        "high_claims":           s.high_claims,
        "punches":               s.punches,
    }


def _match_to_dict(m: PlayerMatch) -> dict:
    return {
        "date":           m.date.isoformat() if m.date else None,
        "tournament":     m.tournament,
        "home_team":      m.home_team,
        "away_team":      m.away_team,
        "home_score":     m.home_score,
        "away_score":     m.away_score,
        "rating":         _fmt(m.rating),
        "minutes_played": m.minutes_played,
        "goals":          m.goals,
        "assists":        m.assists,
        "yellow_card":    m.yellow_card,
        "red_card":       m.red_card,
        "source":         m.source,
    }


def _career_to_dict(c: PlayerCareer) -> dict:
    return {
        "from_team":     c.from_team,
        "to_team":       c.to_team,
        "transfer_date": c.transfer_date.isoformat() if c.transfer_date else None,
        "fee":           _fmt(c.fee),
        "transfer_type": c.transfer_type,
        "season":        c.season,
        "source":        c.source,
    }


# ─── 1. RICERCA / AUTOCOMPLETE ───────────────────────────────────

@router.get("/search-by-name")
def search_by_name(
        name: str = Query(..., min_length=2),
        limit: int = Query(10, ge=1, le=50),
        db: Session = Depends(get_db),
):
    """Ricerca deduplicata per nome (prende il record più recente)."""
    subq = (
        db.query(
            ScoutingPlayer,
            func.row_number().over(
                partition_by=ScoutingPlayer.name,
                order_by=desc(ScoutingPlayer.id)
            ).label("rn")
        )
        .filter(ScoutingPlayer.name.ilike(f"%{name}%"))
        .subquery()
    )
    results = db.query(subq).filter(subq.c.rn == 1).limit(limit).all()

    return [
        {
            "id":       r.id,
            "name":     r.name,
            "position": r.position,
            "club":     r.club,
        }
        for r in results
    ]


# ─── 2. DETTAGLIO CALCIATORE ─────────────────────────────────────

@router.get("/{player_id}")
def get_player_detail(player_id: int, db: Session = Depends(get_db)):
    """
    Restituisce la scheda completa strutturata in:
      a) profile   — anagrafica + attributi radar SofaScore
      b) scouting  — indici algoritmici (PlayerScoutingIndex)
      c) sources   — dati grezzi per fonte
         sources.fbref.stats       → list[dict] (player_fbref_stats, tutti i campi)
         sources.fbref.match_logs  → list[dict]
         sources.sofascore.stats   → list[dict] (player_sofascore_stats)
         sources.sofascore.matches → list[dict] (player_matches)
         sources.sofascore.heatmaps→ list[{league, season, heatmap_points}]
                                      Una entry per competizione/stagione con dati heatmap.
    """
    player = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Giocatore non trovato")

    logger.info(f"[player_detail_final v2] GET /players/{player_id} — {player.name}")

    # ── a) PROFILE ────────────────────────────────────────────────
    def _extract_radar_attrs(src: dict):
        if not src or not isinstance(src, dict):
            return None
        entry = {
            "attacking":  src.get("attr_attacking"),
            "technical":  src.get("attr_technical"),
            "tactical":   src.get("attr_tactical"),
            "defending":  src.get("attr_defending"),
            "creativity": src.get("attr_creativity"),
        }
        if any(v is not None for v in entry.values()):
            return [entry]
        return None

    def _extract_radar_avg(src: dict):
        if not src or not isinstance(src, dict):
            return None
        entry = {
            "attacking":  src.get("attr_attacking"),
            "technical":  src.get("attr_technical"),
            "tactical":   src.get("attr_tactical"),
            "defending":  src.get("attr_defending"),
            "creativity": src.get("attr_creativity"),
        }
        if any(v is not None for v in entry.values()):
            return entry
        GROUP_MAP = {
            "attacking": ["attr_avg_Attacco", "attr_avg_Attack", "attr_avg_Attacking"],
            "technical": ["attr_avg_Tecnica", "attr_avg_Technical", "attr_avg_Technique"],
            "tactical":  ["attr_avg_Tattica", "attr_avg_Tactical"],
            "defending": ["attr_avg_Difesa",  "attr_avg_Defense",  "attr_avg_Defending"],
            "creativity":["attr_avg_Creatività", "attr_avg_Creativity"],
        }
        entry = {}
        for axis, candidates in GROUP_MAP.items():
            for cand in candidates:
                if src.get(cand) is not None:
                    entry[axis] = src[cand]
                    break
        return entry if any(v is not None for v in entry.values()) else None

    latest_attrs = db.query(PlayerSofascoreStats).filter(
        PlayerSofascoreStats.player_id == player_id,
        PlayerSofascoreStats.attributes_raw.isnot(None)
    ).order_by(desc(PlayerSofascoreStats.season)).first()
    attrs_raw = latest_attrs.attributes_raw if latest_attrs else None
    attrs_avg_raw = latest_attrs.attributes_avg_raw if latest_attrs else None

    sofa_attrs           = _extract_radar_attrs(attrs_raw)
    sofa_attrs_avg_entry = _extract_radar_avg(attrs_avg_raw) or _extract_radar_avg(attrs_raw)
    sofa_attrs_avg       = [sofa_attrs_avg_entry] if sofa_attrs_avg_entry else None

    profile = {
        "id":              player.id,
        "name":            player.name,
        "club":            player.club,
        "nationality":     player.nationality,
        "age":             player.age,
        "birth_date":      player.birth_date.isoformat() if player.birth_date else None,
        "position":        player.position,
        "position_detail": player.position_detail,
        "preferred_foot":  player.preferred_foot,
        "height":          player.height,
        "weight":          player.weight,
        "jersey_number":   player.jersey_number,
        "market_value":    _fmt(player.market_value),
        "contract_until":  player.contract_until.isoformat() if player.contract_until else None,
        "sofascore_rating": _fmt(player.sofascore_rating),
        "fbref_id":        getattr(player, "fbref_id", None),
        "sofascore_id":    player.sofascore_id,
        "transfermarkt_id": getattr(player, "transfermarkt_id", None),
        "sofascore_attributes":     sofa_attrs,
        "sofascore_attributes_avg": sofa_attrs_avg,
    }

    # ── b) SCOUTING INDEX ─────────────────────────────────────────
    idx = (
        db.query(PlayerScoutingIndex)
        .filter_by(player_id=player_id)
        .order_by(PlayerScoutingIndex.season.desc())
        .first()
    )

    scouting = None
    if idx:
        scouting = {
            "season":           idx.season,
            "position_group":   idx.position_group,
            "finishing_index":  _fmt(idx.finishing_index, 1),
            "creativity_index": _fmt(idx.creativity_index, 1),
            "pressing_index":   _fmt(idx.pressing_index, 1),
            "carrying_index":   _fmt(idx.carrying_index, 1),
            "defending_index":  _fmt(idx.defending_index, 1),
            "buildup_index":    _fmt(idx.buildup_index, 1),
            "overall_index":    _fmt(idx.overall_index, 1),
            "sources_used":     idx.sources_used,
            "data_confidence":  _fmt(idx.data_confidence),
            "minutes_sample":   idx.minutes_sample,
            "computed_at":      idx.computed_at.isoformat() if idx.computed_at else None,
            "raw": {
                "xg_per90":                  _fmt(idx.xg_per90),
                "xa_per90":                  _fmt(idx.xa_per90),
                "npxg_per90":                _fmt(idx.npxg_per90),
                "sca_per90":                 _fmt(idx.sca_per90),
                "gca_per90":                 _fmt(idx.gca_per90),
                "progressive_carries_per90": _fmt(idx.progressive_carries_per90),
                "progressive_passes_per90":  _fmt(idx.progressive_passes_per90),
                "tackles_won_per90":         _fmt(idx.tackles_won_per90),
                "interceptions_per90":       _fmt(idx.interceptions_per90),
                "aerials_won_pct":           _fmt(idx.aerials_won_pct),
                "take_ons_succ_pct":         _fmt(idx.take_ons_succ_pct),
                "pass_completion_pct":       _fmt(idx.pass_completion_pct),
                "goals_per_shot":            _fmt(idx.goals_per_shot),
                "ball_recoveries_per90":     _fmt(idx.ball_recoveries_per90),
                "crosses_per90":             _fmt(idx.crosses_per90),
            },
        }

    # ── c) SOURCES ────────────────────────────────────────────────

    # FBref —
    fbref_stats_rows = (
        db.query(PlayerFbrefStats)
        .filter_by(player_id=player_id)
        .order_by(PlayerFbrefStats.season.desc())
        .all()
    )
    logger.info(f"[player_detail_final v2] fbref_stats trovate: {len(fbref_stats_rows)} righe per player_id={player_id}")
    fbref_match_logs = (
        db.query(PlayerFbrefMatchLog)
        .filter_by(player_id=player_id)
        .order_by(PlayerFbrefMatchLog.date.desc())
        .all()
    )

    # SofaScore stats —
    sofascore_stats = (
        db.query(PlayerSofascoreStats)
        .filter_by(player_id=player_id)
        .order_by(PlayerSofascoreStats.season.desc())
        .all()
    )

    # Partite SofaScore —
    sofa_matches = (
        db.query(PlayerMatch)
        .filter_by(player_id=player_id)
        .order_by(PlayerMatch.date.desc())
        .limit(50)
        .all()
    )

    # Heatmap SofaScore — tutte le competizioni disponibili nel DB.
    # Il modello PlayerHeatmap ha: player_id, season, league, source, points, point_count.
    # Restituiamo un array [{league, season, heatmap_points}] così il frontend
    # può filtrare per competizione selezionata.
    heatmap_rows = (
        db.query(PlayerHeatmap)
        .filter_by(player_id=player_id)
        .order_by(desc(PlayerHeatmap.fetched_at))
        .all()
    )

    # Costruisce la lista heatmaps per competizione, evitando duplicati
    # (stesso league+season: teniamo quella con più punti).
    _hm_map: dict[tuple, dict] = {}
    for h in heatmap_rows:
        key = (h.league or "", h.season or "")
        pts = h.points or []
        if key not in _hm_map or len(pts) > len(_hm_map[key]["heatmap_points"]):
            _hm_map[key] = {
                "league":         h.league or "",
                "season":         h.season or "",
                "heatmap_points": pts,
                "point_count":    h.point_count or len(pts),
                "source":         h.source or "sofascore",
            }
    heatmaps_list = list(_hm_map.values())

    # Carriera —
    career = (
        db.query(PlayerCareer)
        .filter_by(player_id=player_id)
        .order_by(PlayerCareer.transfer_date.desc())
        .all()
    )

    sources = {
        "fbref": {
            "stats":      [_fbref_stats_to_dict(s) for s in fbref_stats_rows],
            "match_logs": [_fbref_log_to_dict(m) for m in fbref_match_logs],
        },
        "sofascore": {
            "stats":    [_sofascore_stats_to_dict(s) for s in sofascore_stats],
            "matches":  [_match_to_dict(m) for m in sofa_matches],
            # Array di heatmap per competizione — il frontend seleziona in base
            # alla competizione scelta nel dropdown.
            "heatmaps": heatmaps_list,
        },
    }

    return {
        "profile":  profile,
        "scouting": scouting,
        "sources":  sources,
        "career":   [_career_to_dict(c) for c in career],
    }


# ─── 4. DEBUG ENDPOINT ───────────────────────────────────────────

@router.get("/{player_id}/debug")
def debug_player_data(player_id: int, db: Session = Depends(get_db)):
    """
    Endpoint di debug: mostra quante righe vengono trovate per questo player_id
    nelle tabelle principali. Utile per diagnosticare dati mancanti nel frontend.
    Chiamare: GET /players/{id}/debug
    """
    player = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Giocatore non trovato")

    fbref_count = db.query(PlayerFbrefStats).filter_by(player_id=player_id).count()
    fbref_rows  = db.query(PlayerFbrefStats.season, PlayerFbrefStats.league)\
                    .filter_by(player_id=player_id).all()

    sofa_count  = db.query(PlayerSofascoreStats).filter_by(player_id=player_id).count()
    sofa_rows   = db.query(PlayerSofascoreStats.season, PlayerSofascoreStats.league)\
                    .filter_by(player_id=player_id).all()

    match_count = db.query(PlayerMatch).filter_by(player_id=player_id).count()
    heat_count  = db.query(PlayerHeatmap).filter_by(player_id=player_id).count()

    # Cerca anche per sofascore_id (per capire se i dati sono stati importati con ID sbagliato)
    fbref_by_sofa_id = []
    if player.sofascore_id:
        fbref_by_sofa_id = db.query(PlayerFbrefStats.player_id, PlayerFbrefStats.season, PlayerFbrefStats.league)\
            .filter(PlayerFbrefStats.player_id == player.sofascore_id).limit(5).all()

    return {
        "player_id":        player_id,
        "player_name":      player.name,
        "sofascore_id":     player.sofascore_id,
        "fbref_id":         getattr(player, "fbref_id", None),
        "fbref_stats": {
            "count": fbref_count,
            "rows":  [{"season": r.season, "league": r.league} for r in fbref_rows],
        },
        "sofascore_stats": {
            "count": sofa_count,
            "rows":  [{"season": r.season, "league": r.league} for r in sofa_rows],
        },
        "player_matches":   {"count": match_count},
        "player_heatmaps":  {"count": heat_count},
        # Se fbref_by_sofa_id ha righe, i dati sono stati importati con sofascore_id come player_id
        "fbref_rows_by_sofascore_id": [
            {"player_id": r.player_id, "season": r.season, "league": r.league}
            for r in fbref_by_sofa_id
        ],
    }


@router.get("/{player_id}/heatmap")
def get_player_heatmap(player_id: int, db: Session = Depends(get_db)):
    """Ritorna la heatmap con più punti (lazy load / fallback)."""
    rows = (
        db.query(PlayerHeatmap)
        .filter_by(player_id=player_id)
        .order_by(desc(PlayerHeatmap.fetched_at))
        .all()
    )
    if not rows:
        return {"points": [], "heatmaps": []}
    best = max(rows, key=lambda h: h.point_count or 0)
    return {
        "points": best.points or [],
        "season": best.season,
        "league": best.league,
        "heatmaps": [
            {
                "league": h.league or "",
                "season": h.season or "",
                "heatmap_points": h.points or [],
                "point_count": h.point_count or 0,
            }
            for h in rows
        ],
    }

# ─────────────────────────────────────────────────────────────────
# MATCHES (Ultime partite)
# ─────────────────────────────────────────────────────────────────

@router.get("/{player_id}/matches")
def get_player_matches(
        player_id: int,
        limit: int = Query(50, ge=1, le=100),
        db: Session = Depends(get_db)
):
    matches = (
        db.query(PlayerMatch)
        .filter(PlayerMatch.player_id == player_id)
        .order_by(desc(PlayerMatch.date))
        .limit(limit)
        .all()
    )

    return {
        "player_id": player_id,
        "matches": [
            {
                "date": m.date.strftime("%Y-%m-%d") if getattr(m, "date", None) else None,
                # Proviamo i vari nomi possibili per il torneo e la stagione
                "tournament": getattr(m, "tournament", None) or getattr(m, "tournament_name", ""),
                "season": getattr(m, "season", None) or getattr(m, "season_year", ""),

                "home_team": getattr(m, "home_team", ""),
                "away_team": getattr(m, "away_team", ""),

                # Gestione punteggi e statistiche (se None -> 0)
                "home_score": getattr(m, "home_score") if getattr(m, "home_score") is not None else 0,
                "away_score": getattr(m, "away_score") if getattr(m, "away_score") is not None else 0,
                "minutes_played": getattr(m, "minutes_played") if getattr(m, "minutes_played") is not None else 0,
                "goals": getattr(m, "goals") if getattr(m, "goals") is not None else 0,
                "assists": getattr(m, "assists") if getattr(m, "assists") is not None else 0,
                "yellow_card": getattr(m, "yellow_card") if getattr(m, "yellow_card") is not None else 0,
                "red_card": getattr(m, "red_card") if getattr(m, "red_card") is not None else 0,

                # Il Rating: lo formattiamo a 1 decimale (es: 7.2)
                "rating": round(float(m.rating), 1) if getattr(m, "rating", None) else None,
            }
            for m in matches
        ],
    }