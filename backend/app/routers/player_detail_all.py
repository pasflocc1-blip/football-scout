"""
app/api/routers/player_detail.py

Endpoint per la scheda calciatore (GET /api/players/{player_id}).

Risposta strutturata in tre sezioni:
  a) profile      — anagrafica (da scouting_players)
  b) scouting     — indici algoritmici (da player_scouting_index)
  c) sources      — statistiche per fonte (fbref / sofascore)
                    + match_logs FBref per la tab Partite
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ScoutingPlayer, PlayerSeasonStats, PlayerMatch, PlayerCareer
from app.models.fbref_models import PlayerFbrefStats, PlayerFbrefMatchLog, PlayerScoutingIndex

router = APIRouter(prefix="/players", tags=["players"])


# ─────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────

def _fmt(val, decimals: int = 2):
    """Arrotonda float, lascia None intatto."""
    if val is None:
        return None
    if isinstance(val, float):
        return round(val, decimals)
    return val


def _stats_to_dict(s: PlayerSeasonStats) -> dict:
    """Serializza una riga PlayerSeasonStats in dict pulito."""
    return {
        "source":           s.source,
        "season":           s.season,
        "league":           s.league,
        "sofascore_rating": _fmt(s.sofascore_rating),
        "appearances":      s.appearances,
        "matches_started":  s.matches_started,
        "minutes_played":   s.minutes_played,
        "goals":            s.goals,
        "assists":          s.assists,
        # Tiro
        "shots_total":      s.shots_total,
        "shots_on_target":  s.shots_on_target,
        "big_chances_created": s.big_chances_created,
        "xg":               _fmt(s.xg),
        "xg_per90":         _fmt(s.xg_per90),
        "xa":               _fmt(s.xa),
        "xa_per90":         _fmt(s.xa_per90),
        "goal_conversion_pct": _fmt(s.goal_conversion_pct),
        # Passaggi
        "accurate_passes":  s.accurate_passes,
        "total_passes":     s.total_passes,
        "pass_accuracy_pct": _fmt(s.pass_accuracy_pct),
        "key_passes":       s.key_passes,
        "accurate_crosses": s.accurate_crosses,
        "accurate_long_balls": s.accurate_long_balls,
        # Dribbling / duelli
        "successful_dribbles":   s.successful_dribbles,
        "dribble_success_pct":   _fmt(s.dribble_success_pct),
        "aerial_duels_won":      s.aerial_duels_won,
        "aerial_duels_won_pct":  _fmt(s.aerial_duels_won_pct),
        "total_duels_won_pct":   _fmt(s.total_duels_won_pct),
        # Difesa
        "tackles":          s.tackles,
        "tackles_won":      s.tackles_won,
        "interceptions":    s.interceptions,
        "clearances":       s.clearances,
        "ball_recovery":    s.ball_recovery,
        # Disciplina
        "yellow_cards":     s.yellow_cards,
        "red_cards":        s.red_cards,
        "fouls_committed":  s.fouls_committed,
        "fouls_won":        s.fouls_won,
    }


def _fbref_stats_to_dict(s: PlayerFbrefStats) -> dict:
    """Serializza una riga PlayerFbrefStats in dict pulito."""
    return {
        "source":  "fbref",
        "season":  s.season,
        "league":  s.league,
        # Standard
        "appearances":    s.appearances,
        "starts":         s.starts,
        "minutes":        s.minutes,
        "goals":          s.goals,
        "assists":        s.assists,
        "yellow_cards":   s.yellow_cards,
        "red_cards":      s.red_cards,
        "xg":             _fmt(s.xg),
        "npxg":           _fmt(s.npxg),
        "xa":             _fmt(s.xa),
        "xg_per90":       _fmt(s.xg_per90),
        "xa_per90":       _fmt(s.xa_per90),
        "npxg_per90":     _fmt(s.npxg_per90),
        # Shooting
        "shots":              s.shots,
        "shots_on_target":    s.shots_on_target,
        "shots_on_target_pct": _fmt(s.shots_on_target_pct),
        "goals_per_shot":     _fmt(s.goals_per_shot),
        "goals_per_sot":      _fmt(s.goals_per_sot),
        "xg_net":             _fmt(s.xg_net),
        # Passing
        "passes_completed":    s.passes_completed,
        "passes_attempted":    s.passes_attempted,
        "pass_completion_pct": _fmt(s.pass_completion_pct),
        "key_passes":          s.key_passes,
        "progressive_passes":  s.progressive_passes,
        "xa_pass":             _fmt(s.xa_pass),
        # GCA
        "sca":       s.sca,
        "sca_per90": _fmt(s.sca_per90),
        "gca":       s.gca,
        "gca_per90": _fmt(s.gca_per90),
        # Defense
        "tackles":          s.tackles,
        "tackles_won":      s.tackles_won,
        "interceptions":    s.interceptions,
        "clearances":       s.clearances,
        "blocks":           s.blocks,
        "errors":           s.errors,
        # Possession
        "touches":              s.touches,
        "touches_att_pen":      s.touches_att_pen,
        "take_ons_att":         s.take_ons_att,
        "take_ons_succ":        s.take_ons_succ,
        "take_ons_succ_pct":    _fmt(s.take_ons_succ_pct),
        "progressive_carries":  s.progressive_carries,
        "carries_prog_dist":    _fmt(s.carries_prog_dist),
        "dispossessed":         s.dispossessed,
        "progressive_passes_received": s.progressive_passes_received,
        # Misc
        "fouls_committed":  s.fouls_committed,
        "fouls_drawn":      s.fouls_drawn,
        "crosses":          s.crosses,
        "aerials_won":      s.aerials_won,
        "aerials_won_pct":  _fmt(s.aerials_won_pct),
        "ball_recoveries":  s.ball_recoveries,
    }


def _fbref_log_to_dict(m: PlayerFbrefMatchLog) -> dict:
    return {
        "date":         m.date,
        "comp":         m.comp,
        "round":        m.round,
        "venue":        m.venue,
        "result":       m.result,
        "team":         m.team,
        "opponent":     m.opponent,
        "game_started": m.game_started,
        "position":     m.position,
        "minutes":      m.minutes,
        "goals":        m.goals,
        "assists":      m.assists,
        "shots":        m.shots,
        "shots_on_target": m.shots_on_target,
        "yellow_card":  m.yellow_card,
        "red_card":     m.red_card,
        "crosses":      m.crosses,
        "tackles_won":  m.tackles_won,
        "interceptions": m.interceptions,
        "fouls_committed": m.fouls_committed,
        "fouls_drawn":  m.fouls_drawn,
    }


def _match_to_dict(m: PlayerMatch) -> dict:
    return {
        "date":          m.date.isoformat() if m.date else None,
        "tournament":    m.tournament,
        "home_team":     m.home_team,
        "away_team":     m.away_team,
        "home_score":    m.home_score,
        "away_score":    m.away_score,
        "rating":        _fmt(m.rating),
        "minutes_played": m.minutes_played,
        "goals":         m.goals,
        "assists":       m.assists,
        "yellow_card":   m.yellow_card,
        "red_card":      m.red_card,
        "source":        m.source,
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


# ─────────────────────────────────────────────────────────────────
# ENDPOINT PRINCIPALE
# ─────────────────────────────────────────────────────────────────

@router.get("/{player_id}")
def get_player_detail(player_id: int, db: Session = Depends(get_db)):
    """
    Restituisce la scheda completa del calciatore strutturata in:
      a) profile   — anagrafica
      b) scouting  — indici algoritmici
      c) sources   — dati per fonte (fbref / sofascore) + match logs
    """
    player = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Giocatore non trovato")

    # ── a) PROFILE ────────────────────────────────────────────────
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
        # Identificatori provider (utili per link diretti)
        "fbref_id":        player.fbref_id,
        "sofascore_id":    player.sofascore_id,
        "transfermarkt_id": player.transfermarkt_id,
        # Attributi radar SofaScore
        "sofascore_attributes": player.sofascore_attributes_raw,
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
            "season":         idx.season,
            "position_group": idx.position_group,
            # Indici principali (mostrati nel frontend come barre 0-100)
            "finishing_index":  _fmt(idx.finishing_index, 1),
            "creativity_index": _fmt(idx.creativity_index, 1),
            "pressing_index":   _fmt(idx.pressing_index, 1),
            "carrying_index":   _fmt(idx.carrying_index, 1),
            "defending_index":  _fmt(idx.defending_index, 1),
            "buildup_index":    _fmt(idx.buildup_index, 1),
            "overall_index":    _fmt(idx.overall_index, 1),
            # Metadati
            "sources_used":     idx.sources_used,
            "data_confidence":  _fmt(idx.data_confidence),
            "minutes_sample":   idx.minutes_sample,
            "computed_at":      idx.computed_at.isoformat() if idx.computed_at else None,
            # Valori grezzi (tooltip / dettaglio)
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

    # — FBref —
    fbref_stats_rows = (
        db.query(PlayerFbrefStats)
        .filter_by(player_id=player_id)
        .order_by(PlayerFbrefStats.season.desc())
        .all()
    )

    fbref_match_logs = (
        db.query(PlayerFbrefMatchLog)
        .filter_by(player_id=player_id)
        .order_by(PlayerFbrefMatchLog.date.desc())
        .all()
    )

    # — SofaScore —
    sofascore_stats = (
        db.query(PlayerSeasonStats)
        .filter_by(player_id=player_id, source="sofascore")
        .order_by(PlayerSeasonStats.season.desc())
        .all()
    )

    # — Partite SofaScore (player_matches) —
    sofa_matches = (
        db.query(PlayerMatch)
        .filter_by(player_id=player_id)
        .order_by(PlayerMatch.date.desc())
        .limit(50)
        .all()
    )

    # — Carriera —
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
            "stats":   [_stats_to_dict(s) for s in sofascore_stats],
            "matches": [_match_to_dict(m) for m in sofa_matches],
        },
    }

    return {
        "profile":  profile,
        "scouting": scouting,
        "sources":  sources,
        "career":   [_career_to_dict(c) for c in career],
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT TRIGGER IMPORT (opzionale, da usare dal frontend admin)
# ─────────────────────────────────────────────────────────────────

@router.post("/admin/fbref-import")
def trigger_fbref_import(filename: str | None = None):
    """
    Avvia l'importazione dei JSON FBref dalla directory data/fbref.
    Opzionale: filename per importare un solo file.
    Solo per uso admin/sviluppo.
    """
    from app.routers.fbref.import_json import run_import
    import threading

    thread = threading.Thread(target=run_import, args=(filename,), daemon=True)
    thread.start()
    return {"status": "import avviato", "filename": filename or "tutti i file"}