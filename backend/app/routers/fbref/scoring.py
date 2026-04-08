"""
app/ingest/fbref/scoring.py

Calcola il PlayerScoutingIndex a partire dai dati FBref (PlayerFbrefStats).

DESIGN
──────
1. Normalizza le metriche /90 (dividiamo per minuti_90s = minutes / 90).
2. Applica pesi per ruolo (DEF, MID, FWD, GK) per combinare le metriche
   nei 6 indici componenti.
3. I percentili (0-100) vengono calcolati rispetto a tutti i giocatori
   dello stesso position_group che hanno almeno MIN_MINUTES minuti.
   Se in DB ci sono < 5 giocatori confrontabili, il percentile è stimato
   su scale assolute (fallback).
4. overall_index = media pesata dei 6 indici in base al ruolo.

AGGIUNGERE NUOVE FONTI
──────────────────────
Per integrare SofaScore basta aggiungere una funzione _merge_sofascore()
che legge PlayerSeasonStats (source='sofascore') e sovrascrive / integra
le metriche prima del calcolo.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer, PlayerSeasonStats
from app.models.fbref_models import PlayerFbrefStats, PlayerScoutingIndex

log = logging.getLogger("FBRefScoring")

MIN_MINUTES = 200  # soglia minima per essere inclusi nel calcolo percentili

# ── Pesi per ruolo ────────────────────────────────────────────────
# (finishing, creativity, pressing, carrying, defending, buildup)
ROLE_WEIGHTS: dict[str, tuple[float, ...]] = {
    "FWD": (0.30, 0.25, 0.10, 0.15, 0.05, 0.15),
    "MID": (0.15, 0.25, 0.15, 0.15, 0.10, 0.20),
    "DEF": (0.05, 0.10, 0.20, 0.10, 0.35, 0.20),
    "GK":  (0.00, 0.05, 0.15, 0.00, 0.50, 0.30),
}
DEFAULT_WEIGHTS = (0.17, 0.17, 0.17, 0.17, 0.16, 0.16)

# ── Scale assolute di riferimento per il fallback (quando <5 giocatori) ──
# Ogni tupla: (valore_tipico_medio, valore_eccellente)
# Il risultato viene clampato a [0, 100].
ABS_SCALE: dict[str, tuple[float, float]] = {
    "npxg_per90":              (0.10, 0.50),
    "goals_per_shot":          (0.08, 0.25),
    "shots_on_target_pct":     (30.0, 60.0),
    "xa_per90":                (0.05, 0.30),
    "sca_per90":               (1.5,  5.0),
    "gca_per90":               (0.10, 0.60),
    "progressive_passes_per90":(2.0,  8.0),
    "tackles_won_per90":       (0.5,  3.0),
    "interceptions_per90":     (0.3,  2.0),
    "ball_recoveries_per90":   (1.0,  6.0),
    "aerials_won_pct":         (30.0, 75.0),
    "progressive_carries_per90":(1.0, 6.0),
    "take_ons_succ_pct":       (30.0, 70.0),
    "crosses_per90":           (0.5,  4.0),
    "pass_completion_pct":     (65.0, 92.0),
}


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def _abs_score(value: Optional[float], metric: str) -> Optional[float]:
    """Normalizzazione su scale assoluta → 0-100."""
    if value is None:
        return None
    low, high = ABS_SCALE.get(metric, (0, 1))
    if high == low:
        return 50.0
    return _clamp((value - low) / (high - low) * 100)


def _percentile_score(value: Optional[float], population: list[float]) -> Optional[float]:
    """Calcola il percentile di value nella population (lista di float)."""
    if value is None or not population:
        return None
    below = sum(1 for v in population if v < value)
    return _clamp(below / len(population) * 100)


def _position_group(player: ScoutingPlayer) -> str:
    """Mappa la posizione FBref/SofaScore in GK/DEF/MID/FWD."""
    pos = (player.position or "").upper()
    if pos in ("G", "GK", "POR"):
        return "GK"
    if pos in ("D", "DC", "DL", "DR", "WB", "LB", "RB", "CB", "DEF"):
        return "DEF"
    if pos in ("M", "MC", "ML", "MR", "AM", "DM", "MID", "CM", "CAM", "CDM"):
        return "MID"
    # Default offensivo per tutti gli altri (F, W, SS, CF, FWD, LW, RW …)
    return "FWD"


# ═════════════════════════════════════════════════════════════════
# RACCOLTA METRICHE GREZZE
# ═════════════════════════════════════════════════════════════════

def _collect_raw_metrics(stats: PlayerFbrefStats) -> dict:
    """
    Ricava tutte le metriche /90 dalla riga PlayerFbrefStats.
    Restituisce un dict con chiavi = nomi usati nel modello.
    """
    mins = stats.minutes or 0
    m90  = mins / 90.0 if mins >= MIN_MINUTES else None  # None blocca il calcolo

    def per90(val):
        return _safe_div(val, m90)

    return {
        # Finishing
        "npxg_per90":               stats.npxg_per90 or per90(stats.npxg),
        "goals_per_shot":           stats.goals_per_shot,
        "shots_on_target_pct":      stats.shots_on_target_pct,
        # Creativity
        "xa_per90":                 stats.xa_per90 or per90(stats.xa),
        "sca_per90":                stats.sca_per90 or per90(stats.sca),
        "gca_per90":                stats.gca_per90 or per90(stats.gca),
        "progressive_passes_per90": per90(stats.progressive_passes),
        # Pressing
        "tackles_won_per90":        per90(stats.tackles_won),
        "interceptions_per90":      per90(stats.interceptions),
        "ball_recoveries_per90":    per90(stats.ball_recoveries),
        # Carrying
        "progressive_carries_per90": per90(stats.progressive_carries),
        "take_ons_succ_pct":        stats.take_ons_succ_pct,
        "crosses_per90":            per90(stats.crosses),
        # Defending
        "aerials_won_pct":          stats.aerials_won_pct,
        "challenge_tackles_pct":    stats.challenge_tackles_pct,
        # Buildup
        "pass_completion_pct":      stats.pass_completion_pct,
        # Misc
        "xg_per90":                 stats.xg_per90,
        "minutes_sample":           mins,
    }


# ═════════════════════════════════════════════════════════════════
# CALCOLO INDICI (singolo giocatore)
# ═════════════════════════════════════════════════════════════════

def _score_index(
    raw: dict,
    population_raw: list[dict],
    metric_list: list[str],
) -> Optional[float]:
    """
    Calcola un singolo indice come media dei percentili delle metriche.
    Usa percentili reali se ci sono ≥5 giocatori in population, altrimenti
    usa scale assolute.
    """
    scores = []
    use_percentile = len(population_raw) >= 5

    for metric in metric_list:
        val = raw.get(metric)
        if val is None:
            continue

        if use_percentile:
            pop_vals = [p[metric] for p in population_raw if p.get(metric) is not None]
            s = _percentile_score(val, pop_vals)
        else:
            s = _abs_score(val, metric)

        if s is not None:
            scores.append(s)

    return round(sum(scores) / len(scores), 1) if scores else None


def _compute_indices(raw: dict, population_raw: list[dict], pos_group: str) -> dict:
    indices = {
        "finishing_index": _score_index(raw, population_raw, [
            "npxg_per90", "goals_per_shot", "shots_on_target_pct",
        ]),
        "creativity_index": _score_index(raw, population_raw, [
            "xa_per90", "sca_per90", "gca_per90", "progressive_passes_per90",
        ]),
        "pressing_index": _score_index(raw, population_raw, [
            "tackles_won_per90", "interceptions_per90", "ball_recoveries_per90",
        ]),
        "carrying_index": _score_index(raw, population_raw, [
            "progressive_carries_per90", "take_ons_succ_pct", "crosses_per90",
        ]),
        "defending_index": _score_index(raw, population_raw, [
            "aerials_won_pct", "challenge_tackles_pct",
            "tackles_won_per90", "interceptions_per90",
        ]),
        "buildup_index": _score_index(raw, population_raw, [
            "pass_completion_pct", "progressive_passes_per90",
        ]),
    }

    # overall_index: media pesata per ruolo
    weights = ROLE_WEIGHTS.get(pos_group, DEFAULT_WEIGHTS)
    keys = ["finishing_index", "creativity_index", "pressing_index",
            "carrying_index", "defending_index", "buildup_index"]
    num = sum(indices[k] * w for k, w in zip(keys, weights) if indices[k] is not None)
    den = sum(w for k, w in zip(keys, weights) if indices[k] is not None)
    indices["overall_index"] = round(num / den, 1) if den > 0 else None

    return indices


# ═════════════════════════════════════════════════════════════════
# ENTRY POINT — chiamato da import_json.py
# ═════════════════════════════════════════════════════════════════

def compute_scouting_index(db: Session, player: ScoutingPlayer) -> None:
    """
    Calcola/aggiorna PlayerScoutingIndex per il giocatore.
    Legge l'ultima PlayerFbrefStats disponibile.
    """
    # Prendi l'ultima riga FBref disponibile
    stats: Optional[PlayerFbrefStats] = (
        db.query(PlayerFbrefStats)
        .filter_by(player_id=player.id)
        .order_by(PlayerFbrefStats.season.desc())
        .first()
    )
    if not stats:
        log.debug(f"  Nessuna FBref stats per {player.name}, skip scoring.")
        return

    pos_group = _position_group(player)
    raw = _collect_raw_metrics(stats)
    mins = raw.get("minutes_sample", 0)

    if mins < MIN_MINUTES:
        log.warning(
            f"  {player.name}: solo {mins} minuti, sotto soglia {MIN_MINUTES}. "
            f"Indici calcolati con scala assoluta."
        )

    # Raccoglie la "population" per i percentili: tutti i giocatori
    # dello stesso ruolo con stessa stagione e abbastanza minuti.
    # Escludiamo il giocatore corrente.
    peer_stats = (
        db.query(PlayerFbrefStats)
        .join(ScoutingPlayer, PlayerFbrefStats.player_id == ScoutingPlayer.id)
        .filter(
            PlayerFbrefStats.season == stats.season,
            PlayerFbrefStats.player_id != player.id,
        )
        .all()
    )

    population_raw = []
    for ps in peer_stats:
        peer_player = db.query(ScoutingPlayer).get(ps.player_id)
        if peer_player and _position_group(peer_player) == pos_group:
            pr = _collect_raw_metrics(ps)
            if (pr.get("minutes_sample") or 0) >= MIN_MINUTES:
                population_raw.append(pr)

    indices = _compute_indices(raw, population_raw, pos_group)

    # Determina le fonti usate
    sources = ["fbref"]
    sofa = db.query(PlayerSeasonStats).filter_by(
        player_id=player.id, source="sofascore"
    ).order_by(PlayerSeasonStats.season.desc()).first()
    if sofa:
        sources.append("sofascore")

    # data_confidence: 1.0 se >900 min + 2 fonti, scala linearmente
    confidence = min(1.0, (mins / 900) * (0.7 + 0.3 * len(sources) / 2))

    # Upsert PlayerScoutingIndex
    idx = (
        db.query(PlayerScoutingIndex)
        .filter_by(player_id=player.id, season=stats.season)
        .first()
    )
    if not idx:
        idx = PlayerScoutingIndex(player_id=player.id, season=stats.season)
        db.add(idx)

    idx.position_group           = pos_group
    idx.finishing_index          = indices.get("finishing_index")
    idx.creativity_index         = indices.get("creativity_index")
    idx.pressing_index           = indices.get("pressing_index")
    idx.carrying_index           = indices.get("carrying_index")
    idx.defending_index          = indices.get("defending_index")
    idx.buildup_index            = indices.get("buildup_index")
    idx.overall_index            = indices.get("overall_index")

    # Tracciabilità valori grezzi
    idx.xg_per90                 = raw.get("xg_per90")
    idx.xa_per90                 = raw.get("xa_per90")
    idx.npxg_per90               = raw.get("npxg_per90")
    idx.sca_per90                = raw.get("sca_per90")
    idx.gca_per90                = raw.get("gca_per90")
    idx.progressive_carries_per90 = raw.get("progressive_carries_per90")
    idx.progressive_passes_per90  = raw.get("progressive_passes_per90")
    idx.tackles_won_per90        = raw.get("tackles_won_per90")
    idx.interceptions_per90      = raw.get("interceptions_per90")
    idx.aerials_won_pct          = raw.get("aerials_won_pct")
    idx.take_ons_succ_pct        = raw.get("take_ons_succ_pct")
    idx.pass_completion_pct      = raw.get("pass_completion_pct")
    idx.goals_per_shot           = raw.get("goals_per_shot")
    idx.ball_recoveries_per90    = raw.get("ball_recoveries_per90")
    idx.crosses_per90            = raw.get("crosses_per90")

    idx.sources_used             = sources
    idx.data_confidence          = round(confidence, 2)
    idx.minutes_sample           = mins
    idx.updated_at               = datetime.now(timezone.utc)