"""
app/routers/scoring_sofascore.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Algoritmo di scoring MULTI-FONTE che fonde dati FBref + SofaScore.

Questo file è il gemello di app/routers/fbref/scoring.py:
  ● fbref/scoring.py  → usava SOLO PlayerFbrefStats
  ● scoring_sofascore.py → usa PlayerFbrefStats (primario) +
                           PlayerSofascoreStats (fallback/integrazione)
    e scrive il risultato in PlayerScoutingIndex + colonne score
    di ScoutingPlayer.

ENDPOINT:
  POST /scoring/run           → avvia ricalcolo in background
  POST /scoring/run/sync      → ricalcolo sincrono (testing)
  GET  /scoring/status/{id}   → stato calcolo per singolo giocatore

LOGICA INDICI (0-100, basata su per90 rispetto al gruppo-ruolo):
  finishing_index  : goals_per_shot, shots_on_target_pct, xg_net, npxg/90
  creativity_index : key_passes/90, xa/90, sca/90, gca/90, prog_passes/90
  pressing_index   : tackles_won/90, interceptions/90, ball_recoveries/90
  carrying_index   : prog_carries/90, take_ons_succ_pct, touches_att_pen/90
  defending_index  : challenge_tackles_pct, interceptions/90, clearances/90, aerials_won_pct
  buildup_index    : pass_completion_pct, passes_long_pct, prog_passes_received/90, xa
  overall_index    : media pesata per ruolo dei 6 indici
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.models import ScoutingPlayer, PlayerSeasonStats
from app.models.fbref_models import PlayerFbrefStats, PlayerScoutingIndex
from app.models.sofascore_models import PlayerSofascoreStats

log = logging.getLogger(__name__)

router = APIRouter(prefix="/scoring", tags=["Scoring"])

# ── Soglia minima minuti per entrare nel calcolo ──────────────────
MIN_MINUTES = 450

# ── Pesi per ruolo (overall_index) ───────────────────────────────
ROLE_WEIGHTS: dict[str, dict[str, float]] = {
    "GK":  {"finishing": 0.0, "creativity": 0.0, "pressing": 0.15, "carrying": 0.0,  "defending": 0.50, "buildup": 0.35},
    "CB":  {"finishing": 0.05,"creativity": 0.10,"pressing": 0.20, "carrying": 0.10, "defending": 0.40, "buildup": 0.15},
    "LB":  {"finishing": 0.05,"creativity": 0.20,"pressing": 0.15, "carrying": 0.25, "defending": 0.25, "buildup": 0.10},
    "RB":  {"finishing": 0.05,"creativity": 0.20,"pressing": 0.15, "carrying": 0.25, "defending": 0.25, "buildup": 0.10},
    "DM":  {"finishing": 0.05,"creativity": 0.15,"pressing": 0.25, "carrying": 0.10, "defending": 0.30, "buildup": 0.15},
    "CM":  {"finishing": 0.10,"creativity": 0.25,"pressing": 0.20, "carrying": 0.15, "defending": 0.15, "buildup": 0.15},
    "AM":  {"finishing": 0.20,"creativity": 0.35,"pressing": 0.10, "carrying": 0.20, "defending": 0.05, "buildup": 0.10},
    "LW":  {"finishing": 0.25,"creativity": 0.25,"pressing": 0.10, "carrying": 0.30, "defending": 0.05, "buildup": 0.05},
    "RW":  {"finishing": 0.25,"creativity": 0.25,"pressing": 0.10, "carrying": 0.30, "defending": 0.05, "buildup": 0.05},
    "ST":  {"finishing": 0.40,"creativity": 0.15,"pressing": 0.15, "carrying": 0.20, "defending": 0.05, "buildup": 0.05},
    "CF":  {"finishing": 0.35,"creativity": 0.20,"pressing": 0.15, "carrying": 0.20, "defending": 0.05, "buildup": 0.05},
}
_DEFAULT_WEIGHTS = {"finishing": 0.17,"creativity": 0.17,"pressing": 0.17,"carrying": 0.17,"defending": 0.17,"buildup": 0.15}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/run")
def run_scoring(background_tasks: BackgroundTasks):
    """Avvia il ricalcolo scoring multi-fonte in background."""
    def _task():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            result = recalculate_all(db)
            log.info(f"Scoring completato: {result}")
        finally:
            db.close()

    background_tasks.add_task(_task)
    return {"message": "Ricalcolo scoring avviato in background"}


@router.post("/run/sync")
def run_scoring_sync(db: Session = Depends(get_db)):
    """Ricalcolo sincrono — utile per test e debug."""
    result = recalculate_all(db)
    return {"message": f"Scoring completato per {result['players_scored']} giocatori", **result}


@router.get("/status/{player_id}")
def scoring_status(player_id: int, db: Session = Depends(get_db)):
    """Restituisce l'indice di scouting calcolato per un singolo giocatore."""
    idx = (
        db.query(PlayerScoutingIndex)
        .filter_by(player_id=player_id)
        .order_by(PlayerScoutingIndex.season.desc())
        .first()
    )
    if not idx:
        return {"player_id": player_id, "status": "not_computed"}
    return {
        "player_id":       player_id,
        "season":          idx.season,
        "position_group":  idx.position_group,
        "finishing_index": idx.finishing_index,
        "creativity_index":idx.creativity_index,
        "pressing_index":  idx.pressing_index,
        "carrying_index":  idx.carrying_index,
        "defending_index": idx.defending_index,
        "buildup_index":   idx.buildup_index,
        "overall_index":   idx.overall_index,
        "sources_used":    idx.sources_used,
        "data_confidence": idx.data_confidence,
        "computed_at":     idx.computed_at.isoformat() if idx.computed_at else None,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CORE: ricalcolo globale
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def recalculate_all(db: Session) -> dict:
    """
    Ricalcola gli indici per tutti i giocatori con dati sufficienti.

    Pipeline:
      1. Carica tutti i giocatori con almeno MIN_MINUTES
      2. Per ogni giocatore fonde FBref + SofaScore in un vettore raw
      3. Calcola i 6 indici grezzi (valori assoluti)
      4. Normalizza a percentile-like 0-100 rispetto al gruppo-ruolo
      5. Scrive PlayerScoutingIndex + campi score in ScoutingPlayer
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas richiesto: pip install pandas")

    players = db.query(ScoutingPlayer).all()
    log.info(f"Scoring multi-fonte: {len(players)} giocatori da valutare")

    # ── FASE 1: costruisci il vettore raw per ogni giocatore ────────
    records = []
    for p in players:
        raw = _extract_raw_metrics(db, p)
        if raw["minutes"] < MIN_MINUTES:
            continue
        records.append({"player": p, "raw": raw})

    if not records:
        return {"players_scored": 0, "reason": "nessun giocatore con dati sufficienti"}

    # ── FASE 2: calcola valori assoluti degli indici ────────────────
    for rec in records:
        rec["abs_scores"] = _compute_abs_scores(rec["raw"])

    # ── FASE 3: normalizza a percentile per gruppo-ruolo ───────────
    df = _build_dataframe(records)
    INDEX_COLS = ["finishing", "creativity", "pressing", "carrying", "defending", "buildup"]
    pct_map: dict[int, dict[str, Optional[float]]] = {
        rec["player"].id: {} for rec in records
    }
    for col in INDEX_COLS:
        abs_col = f"abs_{col}"
        if abs_col not in df.columns:
            continue
        eligible = df[df[abs_col].notna()].copy()
        if eligible.empty or eligible[abs_col].nunique() <= 1:
            for pid in pct_map:
                pct_map[pid][col] = None
            continue
        eligible[f"pct_{col}"] = eligible.groupby("position_group")[abs_col].rank(
            pct=True, method="average"
        ) * 100.0
        for _, row in eligible.iterrows():
            pct_map[row["player_id"]][col] = round(float(row[f"pct_{col}"]), 1)

    # ── FASE 4: scrivi nel DB ───────────────────────────────────────
    scored     = 0
    season_now = _current_season()

    for rec in records:
        p      = rec["player"]
        raw    = rec["raw"]
        pcts   = pct_map.get(p.id, {})
        pos    = (p.position or "CM").upper()
        weights = ROLE_WEIGHTS.get(pos, _DEFAULT_WEIGHTS)

        # Overall = media pesata per ruolo
        components = [pcts.get(k) for k in ["finishing","creativity","pressing","carrying","defending","buildup"]]
        valid_pairs = [(pcts.get(k), w) for k, w in weights.items() if pcts.get(k) is not None]
        if valid_pairs:
            total_w = sum(w for _, w in valid_pairs)
            overall = round(sum(v * w for v, w in valid_pairs) / total_w, 1) if total_w else None
        else:
            overall = None

        # Upsert PlayerScoutingIndex
        idx = (
            db.query(PlayerScoutingIndex)
            .filter_by(player_id=p.id, season=season_now)
            .first()
        )
        if idx is None:
            idx = PlayerScoutingIndex(player_id=p.id, season=season_now)
            db.add(idx)

        idx.position_group          = pos
        idx.finishing_index         = pcts.get("finishing")
        idx.creativity_index        = pcts.get("creativity")
        idx.pressing_index          = pcts.get("pressing")
        idx.carrying_index          = pcts.get("carrying")
        idx.defending_index         = pcts.get("defending")
        idx.buildup_index           = pcts.get("buildup")
        idx.overall_index           = overall
        idx.sources_used            = raw.get("sources")
        idx.data_confidence         = raw.get("confidence")
        idx.minutes_sample          = raw.get("minutes")
        # Valori grezzi per tracciabilità
        idx.xg_per90                = raw.get("xg_per90")
        idx.xa_per90                = raw.get("xa_per90")
        idx.npxg_per90              = raw.get("npxg_per90")
        idx.sca_per90               = raw.get("sca_per90")
        idx.gca_per90               = raw.get("gca_per90")
        idx.progressive_carries_per90 = raw.get("prog_carries_per90")
        idx.progressive_passes_per90  = raw.get("prog_passes_per90")
        idx.tackles_won_per90        = raw.get("tackles_won_per90")
        idx.interceptions_per90      = raw.get("interceptions_per90")
        idx.aerials_won_pct          = raw.get("aerials_won_pct")
        idx.take_ons_succ_pct        = raw.get("take_ons_succ_pct")
        idx.pass_completion_pct      = raw.get("pass_completion_pct")
        idx.goals_per_shot           = raw.get("goals_per_shot")
        idx.ball_recoveries_per90    = raw.get("ball_recoveries_per90")
        idx.computed_at              = datetime.utcnow()

        # Copia i punteggi anche su ScoutingPlayer (compatibilità UI legacy)
        p.finishing_score     = pcts.get("finishing")
        p.creativity_score    = pcts.get("creativity")
        p.pressing_score      = pcts.get("pressing")
        p.carrying_score      = pcts.get("carrying")
        p.defending_obj_score = pcts.get("defending")
        p.buildup_obj_score   = pcts.get("buildup")
        # heading_score = proxy aerei
        if raw.get("aerials_won_pct") is not None:
            p.heading_score = round(min(raw["aerials_won_pct"], 100), 1)

        scored += 1
        if scored % 100 == 0:
            db.commit()
            log.info(f"  Scoring: {scored} giocatori elaborati")

    db.commit()
    log.info(f"Scoring completato: {scored} giocatori aggiornati")
    return {"players_scored": scored, "season": season_now}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ESTRAZIONE METRICHE RAW (FBref prima, SofaScore come fallback)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _extract_raw_metrics(db: Session, player: ScoutingPlayer) -> dict:
    """
    Fonde i dati FBref e SofaScore in un unico vettore di metriche per90.

    Strategia di fusione:
      • FBref è la fonte primaria per le metriche avanzate (pressures, sca, gca,
        progressive carries/passes, aerials).
      • SofaScore è la fonte primaria per rating, big_chances, dribbles, xG/xA
        quando FBref non ha dati.
      • I minuti vengono scelti dalla fonte con più dati.
    """
    # ── FBref (stagione più recente) ───────────────────────────────
    fbref = (
        db.query(PlayerFbrefStats)
        .filter_by(player_id=player.id)
        .order_by(PlayerFbrefStats.season.desc())
        .first()
    )

    # ── SofaScore (stagione più recente) ──────────────────────────
    sofa = (
        db.query(PlayerSofascoreStats)
        .filter_by(player_id=player.id)
        .order_by(PlayerSofascoreStats.season.desc())
        .first()
    )

    sources = []
    if fbref:
        sources.append("fbref")
    if sofa:
        sources.append("sofascore")

    if not fbref and not sofa:
        return {"minutes": 0, "sources": [], "confidence": 0.0}

    # ── Minuti: preferisci FBref ────────────────────────────────────
    minutes = _val(fbref, "minutes") or _val(sofa, "minutes_played") or 0
    if minutes < 1:
        return {"minutes": 0, "sources": sources, "confidence": 0.0}

    p90 = 90.0 / minutes

    # ── Confidence: 1.0 = entrambe le fonti, 0.6 = solo una ───────
    confidence = 1.0 if len(sources) == 2 else 0.6

    def _per90(val) -> Optional[float]:
        if val is None:
            return None
        return round(float(val) * p90, 4)

    # ── Metriche combinate ─────────────────────────────────────────
    # xG/xA: FBref > Sofascore
    xg_per90    = _val(fbref, "xg_per90")   or _per90(_val(sofa, "xg"))
    xa_per90    = _val(fbref, "xa_per90")   or _per90(_val(sofa, "xa"))
    npxg_per90  = _val(fbref, "npxg_per90")

    # Shot quality
    goals       = _val(fbref, "goals")      or _val(sofa, "goals") or 0
    shots       = _val(fbref, "shots")      or _val(sofa, "shots_total") or 0
    sot         = _val(fbref, "shots_on_target") or _val(sofa, "shots_on_target") or 0
    goals_per_shot = round(goals / shots, 4) if shots > 0 else None
    sot_pct        = round(sot / shots * 100, 1) if shots > 0 else None
    xg_net         = round(goals - float(_val(fbref, "xg") or _val(sofa, "xg") or 0), 4)

    # Passing / creativity
    key_passes_per90   = _per90(_val(fbref, "key_passes")      or _val(sofa, "key_passes"))
    sca_per90          = _per90(_val(fbref, "sca"))
    gca_per90          = _per90(_val(fbref, "gca"))
    prog_passes_per90  = _per90(_val(fbref, "progressive_passes"))
    pass_completion    = _val(fbref, "pass_completion_pct") or _val(sofa, "pass_accuracy_pct")
    passes_long_pct    = _val(fbref, "passes_long_pct")

    # Carrying
    prog_carries_per90 = _per90(_val(fbref, "progressive_carries"))
    take_ons_succ_pct  = _val(fbref, "take_ons_succ_pct") or _val(sofa, "dribble_success_pct")
    touches_att_pen_p90 = _per90(_val(fbref, "touches_att_pen"))

    # Defending
    tackles_won        = _val(fbref, "tackles_won") or _val(sofa, "tackles_won")
    tackles_won_per90  = _per90(tackles_won)
    interceptions      = _val(fbref, "interceptions") or _val(sofa, "interceptions")
    interceptions_per90 = _per90(interceptions)
    clearances_per90   = _per90(_val(fbref, "clearances") or _val(sofa, "clearances"))
    aerials_won_pct    = _val(fbref, "aerials_won_pct") or _val(sofa, "aerial_duels_won_pct")
    challenge_tkl_pct  = _val(fbref, "challenge_tackles_pct")

    # Pressing / ball recovery (solo FBref)
    ball_recoveries    = _val(fbref, "ball_recoveries") or _val(sofa, "ball_recovery")
    ball_rec_per90     = _per90(ball_recoveries)

    # Build-up
    prog_rec_per90     = _per90(_val(fbref, "progressive_passes_received"))

    return {
        "minutes":             minutes,
        "sources":             sources,
        "confidence":          confidence,
        # Finishing
        "xg_per90":            xg_per90,
        "xa_per90":            xa_per90,
        "npxg_per90":          npxg_per90,
        "goals_per_shot":      goals_per_shot,
        "sot_pct":             sot_pct,
        "xg_net":              xg_net,
        # Creativity
        "key_passes_per90":    key_passes_per90,
        "sca_per90":           sca_per90,
        "gca_per90":           gca_per90,
        "prog_passes_per90":   prog_passes_per90,
        # Pressing
        "tackles_won_per90":   tackles_won_per90,
        "interceptions_per90": interceptions_per90,
        "ball_recoveries_per90": ball_rec_per90,
        # Carrying
        "prog_carries_per90":  prog_carries_per90,
        "take_ons_succ_pct":   take_ons_succ_pct,
        "touches_att_pen_p90": touches_att_pen_p90,
        # Defending
        "clearances_per90":    clearances_per90,
        "aerials_won_pct":     aerials_won_pct,
        "challenge_tkl_pct":   challenge_tkl_pct,
        # Build-up
        "pass_completion_pct": pass_completion,
        "passes_long_pct":     passes_long_pct,
        "prog_rec_per90":      prog_rec_per90,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CALCOLO SCORE ASSOLUTI (PRE-NORMALIZZAZIONE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _compute_abs_scores(raw: dict) -> dict:
    """
    Calcola 6 score assoluti (scala arbitraria, poi normalizzati a percentile).
    Ogni score è la media pesata delle metriche disponibili per quell'indice.
    """
    def _avg(*vals, weights=None):
        pairs = [(v, (weights[i] if weights else 1.0))
                 for i, v in enumerate(vals) if v is not None]
        if not pairs:
            return None
        total_w = sum(w for _, w in pairs)
        return round(sum(v * w for v, w in pairs) / total_w, 4)

    return {
        "finishing": _avg(
            raw.get("npxg_per90") or raw.get("xg_per90"),
            raw.get("goals_per_shot"),
            raw.get("sot_pct"),
            weights=[3, 2, 1],
        ),
        "creativity": _avg(
            raw.get("xa_per90"),
            raw.get("key_passes_per90"),
            raw.get("sca_per90"),
            raw.get("gca_per90"),
            raw.get("prog_passes_per90"),
            weights=[3, 2, 2, 3, 1],
        ),
        "pressing": _avg(
            raw.get("tackles_won_per90"),
            raw.get("interceptions_per90"),
            raw.get("ball_recoveries_per90"),
            weights=[3, 3, 2],
        ),
        "carrying": _avg(
            raw.get("prog_carries_per90"),
            raw.get("take_ons_succ_pct"),
            raw.get("touches_att_pen_p90"),
            weights=[3, 2, 2],
        ),
        "defending": _avg(
            raw.get("challenge_tkl_pct"),
            raw.get("interceptions_per90"),
            raw.get("clearances_per90"),
            raw.get("aerials_won_pct"),
            weights=[2, 3, 2, 2],
        ),
        "buildup": _avg(
            raw.get("pass_completion_pct"),
            raw.get("passes_long_pct"),
            raw.get("prog_rec_per90"),
            raw.get("xa_per90"),
            weights=[2, 1, 2, 3],
        ),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _val(obj, attr: str):
    """Legge un attributo da un ORM object (o None se obj è None)."""
    if obj is None:
        return None
    return getattr(obj, attr, None)


def _build_dataframe(records: list) -> "pd.DataFrame":
    import pandas as pd
    rows = []
    for rec in records:
        p      = rec["player"]
        ab     = rec["abs_scores"]
        row    = {
            "player_id":      p.id,
            "position_group": (p.position or "CM").upper(),
        }
        for k, v in ab.items():
            row[f"abs_{k}"] = v
        rows.append(row)
    return pd.DataFrame(rows)


def _current_season() -> str:
    now = datetime.utcnow()
    y, m = now.year, now.month
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[-2:]}"
