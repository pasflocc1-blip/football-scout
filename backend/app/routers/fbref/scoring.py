"""
app/routers/fbref/scoring.py  ─ v3.0 (delegato a scoring_sofascore)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CAMBIO DESIGN
─────────────
Questo file era la pipeline SOLO-FBREF, usata da import_json.py per
calcolare PlayerScoutingIndex immediatamente dopo l'import FBref.

Con la v3 la logica di calcolo è unificata in scoring_sofascore.py,
che usa sia FBref che SofaScore. Questa funzione rimane come entry
point chiamato da import_json.py, ma delega tutta la logica al modulo
unificato.

Se SofaScore non è ancora importato per questo giocatore, il calcolo
avviene comunque usando solo FBref (il modulo unificato gestisce il
caso fonti parziali).

USAGE (da import_json.py, invariato):
    from app.routers.fbref.scoring import compute_scouting_index
    compute_scouting_index(db, player)
"""
from __future__ import annotations

import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer
from app.models.fbref_models import PlayerFbrefStats, PlayerScoutingIndex
from app.models.sofascore_models import PlayerSofascoreStats

# Importa la logica unificata
from app.routers.scoring_sofascore import (
    _extract_raw_metrics,
    _compute_abs_scores,
    _position_group,
    ROLE_WEIGHTS,
    _DEFAULT_WEIGHTS,
    MIN_MINUTES,
    ABS_SCALE_FALLBACK,
    _current_season,
    _v,
)

log = logging.getLogger("FBRefScoring")


def compute_scouting_index(db: Session, player: ScoutingPlayer) -> None:
    """
    Calcola/aggiorna PlayerScoutingIndex per il giocatore appena importato.

    A differenza di recalculate_all(), qui usiamo scale assolute di
    riferimento invece dei percentili globali, perché al momento
    dell'import un singolo giocatore non può essere confrontato col
    gruppo completo.

    I percentili reali vengono calcolati da POST /scoring/run (o /run/sync)
    che opera su tutti i giocatori contemporaneamente.
    """
    # Verifica che ci siano dati FBref
    fbref: Optional[PlayerFbrefStats] = (
        db.query(PlayerFbrefStats)
        .filter_by(player_id=player.id)
        .order_by(PlayerFbrefStats.season.desc())
        .first()
    )
    if not fbref:
        log.debug(f"  Nessuna FBref stats per {player.name}, skip scoring.")
        return

    # Estrai metriche fuse (usa anche SS se disponibile)
    raw = _extract_raw_metrics(db, player)
    minutes = raw.get("minutes", 0)

    if minutes < MIN_MINUTES:
        log.info(
            f"  {player.name}: {minutes} min < {MIN_MINUTES}. "
            "Calcolo con scala assoluta (non percentile)."
        )

    # Score assoluti
    abs_scores = _compute_abs_scores(raw)

    # Normalizzazione su scale assoluta di riferimento (non percentile)
    # → 0 = valore minimo tipico, 100 = valore eccellente
    def _abs_norm(value: Optional[float], metric: str) -> Optional[float]:
        if value is None:
            return None
        low, high = ABS_SCALE_FALLBACK.get(metric, (0.0, 1.0))
        if high == low:
            return 50.0
        return max(0.0, min(100.0, (value - low) / (high - low) * 100.0))

    indices = {
        "finishing":  _abs_norm(abs_scores.get("finishing"),  "finishing"),
        "creativity": _abs_norm(abs_scores.get("creativity"), "creativity"),
        "pressing":   _abs_norm(abs_scores.get("pressing"),   "pressing"),
        "carrying":   _abs_norm(abs_scores.get("carrying"),   "carrying"),
        "defending":  _abs_norm(abs_scores.get("defending"),  "defending"),
        "buildup":    _abs_norm(abs_scores.get("buildup"),    "buildup"),
    }

    # Overall pesato per ruolo
    pos     = _position_group(player)
    weights = ROLE_WEIGHTS.get(pos, _DEFAULT_WEIGHTS)
    valid_pairs = [(indices[k], w) for k, w in weights.items() if indices.get(k) is not None]
    total_w = sum(w for _, w in valid_pairs)
    overall = round(sum(v * w for v, w in valid_pairs) / total_w, 1) if total_w else None

    season = fbref.season or _current_season()

    # Upsert PlayerScoutingIndex
    idx = (
        db.query(PlayerScoutingIndex)
        .filter_by(player_id=player.id, season=season)
        .first()
    )
    if not idx:
        idx = PlayerScoutingIndex(player_id=player.id, season=season)
        db.add(idx)

    from datetime import datetime, timezone
    idx.position_group            = pos
    idx.finishing_index           = indices.get("finishing")
    idx.creativity_index          = indices.get("creativity")
    idx.pressing_index            = indices.get("pressing")
    idx.carrying_index            = indices.get("carrying")
    idx.defending_index           = indices.get("defending")
    idx.buildup_index             = indices.get("buildup")
    idx.overall_index             = overall
    idx.sources_used              = raw.get("sources")
    idx.data_confidence           = raw.get("confidence")
    idx.minutes_sample            = minutes
    idx.xg_per90                  = raw.get("xg_per90")
    idx.xa_per90                  = raw.get("xa_per90")
    idx.npxg_per90                = raw.get("npxg_per90")
    idx.sca_per90                 = raw.get("sca_per90")
    idx.gca_per90                 = raw.get("gca_per90")
    idx.progressive_carries_per90 = raw.get("prog_carries_per90")
    idx.progressive_passes_per90  = raw.get("prog_passes_per90")
    idx.tackles_won_per90         = raw.get("tackles_won_per90")
    idx.interceptions_per90       = raw.get("interceptions_per90")
    idx.aerials_won_pct           = raw.get("aerials_won_pct")
    idx.take_ons_succ_pct         = raw.get("take_ons_succ_pct")
    idx.pass_completion_pct       = raw.get("pass_completion_pct")
    idx.goals_per_shot            = raw.get("goals_per_shot")
    idx.ball_recoveries_per90     = raw.get("ball_recoveries_per90")
    idx.crosses_per90             = raw.get("crosses_per90")
    idx.updated_at                = datetime.now(timezone.utc)

    log.info(
        f"  {player.name} ({pos}): "
        f"fin={indices.get('finishing')} cre={indices.get('creativity')} "
        f"pre={indices.get('pressing')} car={indices.get('carrying')} "
        f"def={indices.get('defending')} bld={indices.get('buildup')} "
        f"overall={overall} | fonti={raw.get('sources')} conf={raw.get('confidence')}"
    )