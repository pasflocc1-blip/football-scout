
from __future__ import annotations

"""
app/routers/scoring_sofascore.py  ─ v3.1-DEBUG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VERSIONE DEBUG: logging esteso per diagnosticare "0 giocatori scored".
Da sostituire con la versione pulita dopo il fix.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ScoutingPlayer
from app.models.fbref_models import PlayerFbrefStats, PlayerScoutingIndex
from app.models.sofascore_models import PlayerSofascoreStats

log = logging.getLogger(__name__)

router = APIRouter(prefix="/scoring", tags=["Scoring"])

# ── Costanti ──────────────────────────────────────────────────────────────────
MIN_MINUTES = 90   # ← DEBUG: abbassato a 1 partita per testare con pochi giocatori importati
                   #   Ripristinare a 450 in produzione

ROLE_WEIGHTS: dict[str, dict[str, float]] = {
    "GK":  {"finishing": 0.00, "creativity": 0.05, "pressing": 0.15, "carrying": 0.00, "defending": 0.50, "buildup": 0.30},
    "CB":  {"finishing": 0.05, "creativity": 0.10, "pressing": 0.20, "carrying": 0.10, "defending": 0.40, "buildup": 0.15},
    "LB":  {"finishing": 0.05, "creativity": 0.20, "pressing": 0.15, "carrying": 0.25, "defending": 0.25, "buildup": 0.10},
    "RB":  {"finishing": 0.05, "creativity": 0.20, "pressing": 0.15, "carrying": 0.25, "defending": 0.25, "buildup": 0.10},
    "DM":  {"finishing": 0.05, "creativity": 0.15, "pressing": 0.25, "carrying": 0.10, "defending": 0.30, "buildup": 0.15},
    "CM":  {"finishing": 0.10, "creativity": 0.25, "pressing": 0.20, "carrying": 0.15, "defending": 0.15, "buildup": 0.15},
    "AM":  {"finishing": 0.20, "creativity": 0.35, "pressing": 0.10, "carrying": 0.20, "defending": 0.05, "buildup": 0.10},
    "LW":  {"finishing": 0.25, "creativity": 0.25, "pressing": 0.10, "carrying": 0.30, "defending": 0.05, "buildup": 0.05},
    "RW":  {"finishing": 0.25, "creativity": 0.25, "pressing": 0.10, "carrying": 0.30, "defending": 0.05, "buildup": 0.05},
    "ST":  {"finishing": 0.40, "creativity": 0.15, "pressing": 0.15, "carrying": 0.20, "defending": 0.05, "buildup": 0.05},
    "CF":  {"finishing": 0.35, "creativity": 0.20, "pressing": 0.15, "carrying": 0.20, "defending": 0.05, "buildup": 0.05},
    "D":   {"finishing": 0.05, "creativity": 0.10, "pressing": 0.20, "carrying": 0.10, "defending": 0.40, "buildup": 0.15},
    "M":   {"finishing": 0.10, "creativity": 0.25, "pressing": 0.20, "carrying": 0.15, "defending": 0.15, "buildup": 0.15},
    "F":   {"finishing": 0.35, "creativity": 0.20, "pressing": 0.15, "carrying": 0.20, "defending": 0.05, "buildup": 0.05},
}
_DEFAULT_WEIGHTS = {
    "finishing": 0.17, "creativity": 0.17, "pressing": 0.17,
    "carrying": 0.17, "defending": 0.16, "buildup": 0.16,
}

ABS_SCALE_FALLBACK: dict[str, tuple[float, float]] = {
    "finishing":  (0.0,  0.30),
    "creativity": (0.0,  0.25),
    "pressing":   (0.0,  5.0),
    "carrying":   (0.0,  5.0),
    "defending":  (0.0,  70.0),
    "buildup":    (60.0, 92.0),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        "player_id":        player_id,
        "season":           idx.season,
        "position_group":   idx.position_group,
        "finishing_index":  idx.finishing_index,
        "creativity_index": idx.creativity_index,
        "pressing_index":   idx.pressing_index,
        "carrying_index":   idx.carrying_index,
        "defending_index":  idx.defending_index,
        "buildup_index":    idx.buildup_index,
        "overall_index":    idx.overall_index,
        "sources_used":     idx.sources_used,
        "data_confidence":  idx.data_confidence,
        "minutes_sample":   idx.minutes_sample,
        "computed_at":      idx.computed_at.isoformat() if idx.computed_at else None,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CORE: ricalcolo globale
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def recalculate_all(db: Session) -> dict:
    """
    Pipeline completa con debug logging v3.1.
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas richiesto: pip install pandas")

    # ── DEBUG: conta le righe nelle tabelle sorgente ───────────────────────
    total_players  = db.query(ScoutingPlayer).count()
    total_fbref    = db.query(PlayerFbrefStats).count()
    total_sofa     = db.query(PlayerSofascoreStats).count()
    log.warning(
        f"[DEBUG] Tabelle sorgente: "
        f"scouting_players={total_players}, "
        f"player_fbref_stats={total_fbref}, "
        f"player_sofascore_stats={total_sofa}"
    )

    players = db.query(ScoutingPlayer).all()
    log.warning(f"[DEBUG] Scoring multi-fonte v3.1: {len(players)} giocatori da processare")

    if not players:
        log.warning("[DEBUG] STOP: nessun giocatore in scouting_players!")
        return {"players_scored": 0, "reason": "nessun giocatore in scouting_players"}

    # ── FASE 1: estrai metriche raw per ogni giocatore ────────────────────
    records      = []
    skipped_mins = []   # (name, minutes)
    skipped_nodata = [] # name

    for p in players:
        raw = _extract_raw_metrics(db, p)
        minutes = raw.get("minutes", 0)

        # DEBUG primo giocatore in dettaglio
        if not records and not skipped_mins and not skipped_nodata:
            log.warning(
                f"[DEBUG] Primo giocatore campione → {p.name} (id={p.id}, pos={p.position}): "
                f"minutes={minutes}, sources={raw.get('sources')}, confidence={raw.get('confidence')}"
            )

        if minutes < 1:
            skipped_nodata.append(p.name)
        elif minutes < MIN_MINUTES:
            skipped_mins.append((p.name, minutes))
            # Log dettagliato per i giocatori con dati ma minuti insufficienti
            log.warning(
                f"[DEBUG-SKIP] {p.name} (id={p.id}): {minutes} min < {MIN_MINUTES} — "
                f"sources={raw.get('sources')}, confidence={raw.get('confidence')}"
            )
        else:
            records.append({"player": p, "raw": raw})

    # Riassunto dello skip
    log.warning(
        f"[DEBUG] Filtro minuti (MIN={MIN_MINUTES}): "
        f"idonei={len(records)}, "
        f"minuti_insufficienti={len(skipped_mins)}, "
        f"nessun_dato={len(skipped_nodata)}"
    )

    # Stampa i primi 10 giocatori per categoria (aiuta a capire dove si inceppa)
    if skipped_nodata:
        log.warning(
            f"[DEBUG] Giocatori senza minuti (prime 10): {skipped_nodata[:10]}"
        )
    if skipped_mins:
        sample = skipped_mins[:10]
        log.warning(
            f"[DEBUG] Giocatori con minuti < {MIN_MINUTES} (prime 10): "
            + ", ".join(f"{n}={m}" for n, m in sample)
        )
    if records:
        sample_names = [r["player"].name for r in records[:5]]
        log.warning(f"[DEBUG] Giocatori idonei (prime 5): {sample_names}")

    if not records:
        # ── DEBUG APPROFONDITO: perché tutti i giocatori vengono scartati? ──
        # Prendi il primo giocatore con fbref o sofascore e mostra raw completo
        first_with_data = None
        for p in players:
            has_fb = db.query(PlayerFbrefStats).filter_by(player_id=p.id).first()
            has_ss = db.query(PlayerSofascoreStats).filter_by(player_id=p.id).first()
            if has_fb or has_ss:
                first_with_data = p
                break

        if first_with_data:
            raw_sample = _extract_raw_metrics(db, first_with_data)
            fb_rows = db.query(PlayerFbrefStats).filter(PlayerFbrefStats.player_id == first_with_data.id).all()
            ss_rows = db.query(PlayerSofascoreStats).filter(PlayerSofascoreStats.player_id == first_with_data.id).all()
            log.warning(
                f"[DEBUG] Giocatore con dati ma 0 minuti: {first_with_data.name}\n"
                f"  FBref rows: {[(r.season, r.minutes) for r in fb_rows]}\n"
                f"  SofaScore rows: {[(r.season, r.minutes_played) for r in ss_rows]}\n"
                f"  raw dict: {raw_sample}"
            )
        else:
            log.warning(
                "[DEBUG] Nessun giocatore ha righe in player_fbref_stats "
                "NÉ in player_sofascore_stats. "
                "Controlla che l'import FBref/SofaScore sia andato a buon fine "
                "e che player_id sia correttamente popolato."
            )

        return {"players_scored": 0, "reason": "nessun giocatore con dati sufficienti"}

    # ── FASE 2: calcola score assoluti ─────────────────────────────────────
    for rec in records:
        rec["abs_scores"] = _compute_abs_scores(rec["raw"])

    # DEBUG: mostra abs_scores per il primo giocatore idoneo
    first_rec = records[0]
    log.warning(
        f"[DEBUG] abs_scores campione ({first_rec['player'].name}): "
        f"{first_rec['abs_scores']}"
    )

    # ── FASE 3: normalizza a percentile per gruppo-ruolo ───────────────────
    INDEX_COLS = ["finishing", "creativity", "pressing", "carrying", "defending", "buildup"]
    rows_df = []
    for rec in records:
        p   = rec["player"]
        pos = _position_group(p)
        row = {"player_id": p.id, "position_group": pos}
        for k, v in rec["abs_scores"].items():
            row[f"abs_{k}"] = v
        rows_df.append(row)

    df = pd.DataFrame(rows_df)

    # DEBUG: distribuzione per position_group
    if "position_group" in df.columns:
        pos_counts = df["position_group"].value_counts().to_dict()
        log.warning(f"[DEBUG] Distribuzione position_group: {pos_counts}")

    # DEBUG: quanti non-NULL per ogni indice
    for col in INDEX_COLS:
        abs_col = f"abs_{col}"
        if abs_col in df.columns:
            n_valid = df[abs_col].notna().sum()
            log.warning(f"[DEBUG] {abs_col}: {n_valid}/{len(df)} non-NULL")

    pct_map: dict[int, dict[str, Optional[float]]] = {
        rec["player"].id: {} for rec in records
    }

    for col in INDEX_COLS:
        abs_col = f"abs_{col}"
        if abs_col not in df.columns:
            log.warning(f"[DEBUG] Colonna {abs_col} assente nel DataFrame — skip")
            continue
        eligible = df[df[abs_col].notna()].copy()
        if eligible.empty:
            log.warning(f"[DEBUG] {abs_col}: 0 righe non-NULL — indice sarà NULL per tutti")
            continue
        if eligible[abs_col].nunique() <= 1:
            log.warning(
                f"[DEBUG] {abs_col}: tutti i valori identici "
                f"({eligible[abs_col].iloc[0]}) — 1 solo giocatore nel gruppo, "
                f"assegno percentile=50.0 come placeholder"
            )
            for pid in pct_map:
                if pid in eligible["player_id"].values:
                    pct_map[pid][col] = 50.0  # con 1 giocatore assegna mediana
            continue
        eligible[f"pct_{col}"] = (
            eligible.groupby("position_group")[abs_col]
            .rank(pct=True, method="average") * 100.0
        )
        for _, row in eligible.iterrows():
            pct_map[int(row["player_id"])][col] = round(float(row[f"pct_{col}"]), 1)

    # ── FASE 4: salva nel DB ───────────────────────────────────────────────
    scored     = 0
    season_now = _current_season()
    log.warning(f"[DEBUG] Season corrente calcolata: {season_now}")

    for rec in records:
        p      = rec["player"]
        raw    = rec["raw"]
        pcts   = pct_map.get(p.id, {})
        pos    = _position_group(p)
        weights = ROLE_WEIGHTS.get(pos, _DEFAULT_WEIGHTS)

        valid_pairs = [(pcts[k], w) for k, w in weights.items() if pcts.get(k) is not None]
        total_w = sum(w for _, w in valid_pairs)
        overall = round(sum(v * w for v, w in valid_pairs) / total_w, 1) if total_w else None

        # DEBUG primo salvataggio
        if scored == 0:
            log.warning(
                f"[DEBUG] Primo upsert: {p.name} (id={p.id}) → "
                f"pos={pos}, pcts={pcts}, overall={overall}, season={season_now}"
            )

        idx = (
            db.query(PlayerScoutingIndex)
            .filter_by(player_id=p.id, season=season_now)
            .first()
        )
        if idx is None:
            idx = PlayerScoutingIndex(player_id=p.id, season=season_now)
            db.add(idx)

        idx.position_group            = pos
        idx.finishing_index           = pcts.get("finishing")
        idx.creativity_index          = pcts.get("creativity")
        idx.pressing_index            = pcts.get("pressing")
        idx.carrying_index            = pcts.get("carrying")
        idx.defending_index           = pcts.get("defending")
        idx.buildup_index             = pcts.get("buildup")
        idx.overall_index             = overall
        idx.sources_used              = raw.get("sources")
        idx.data_confidence           = raw.get("confidence")
        idx.minutes_sample            = raw.get("minutes")
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
        idx.computed_at               = datetime.utcnow()

        p.finishing_score     = pcts.get("finishing")
        p.creativity_score    = pcts.get("creativity")
        p.pressing_score      = pcts.get("pressing")
        p.carrying_score      = pcts.get("carrying")
        p.defending_obj_score = pcts.get("defending")
        p.buildup_obj_score   = pcts.get("buildup")
        if raw.get("aerials_won_pct") is not None:
            p.heading_score = round(min(raw["aerials_won_pct"], 100.0), 1)

        scored += 1
        if scored % 100 == 0:
            db.commit()
            log.warning(f"[DEBUG] Scoring: {scored} giocatori elaborati (commit intermedio)")

    db.commit()
    log.warning(f"[DEBUG] Scoring v3 completato: {scored} giocatori su {len(players)} totali")
    return {"players_scored": scored, "season": season_now}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ESTRAZIONE METRICHE RAW — vera fusione FBref + SofaScore
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _normalize_season(s: str) -> str:
    """Normalizza "2025-2026" → "2025-26". Lascia invariato se già corto."""
    if not s:
        return s
    parts = s.split("-")
    if len(parts) == 2 and len(parts[1]) == 4:
        return f"{parts[0]}-{parts[1][2:]}"
    return s


def _best_fbref(rows: list) -> Optional["PlayerFbrefStats"]:
    """
    Data una lista di righe FBref per lo stesso giocatore,
    trova la stagione più recente (normalizzata) e somma
    tutte le righe di quella stagione (es. Serie A + UCL).
    Restituisce un oggetto fittizio con i valori aggregati.
    """
    if not rows:
        return None

    # Stagione più recente per minuti totali
    from collections import defaultdict
    season_mins: dict[str, int] = defaultdict(int)
    for r in rows:
        season_mins[_normalize_season(r.season)] += int(r.minutes or 0)

    log.warning(
        f"[DEBUG-AGG] FBref season→mins map: {dict(season_mins)}"
    )

    best_season = max(season_mins, key=lambda s: (season_mins[s], s))
    season_rows = [r for r in rows if _normalize_season(r.season) == best_season]

    log.warning(
        f"[DEBUG-AGG] FBref stagione scelta: {best_season}, "
        f"righe={len(season_rows)}, "
        f"mins per riga={[r.minutes for r in season_rows]}"
    )

    if len(season_rows) == 1:
        return season_rows[0]

    # Aggrega più righe (es. Serie A + UCL) nella stessa stagione
    from copy import copy
    base = copy(season_rows[0])
    base.minutes = sum(int(r.minutes or 0) for r in season_rows)

    _int_fields = [
        "goals", "assists", "goals_pens", "pens_made", "pens_att",
        "yellow_cards", "red_cards",
        "shots", "shots_on_target",
        "passes_completed", "passes_attempted",
        "passes_long_completed", "passes_long_attempted",
        "key_passes", "passes_final_third", "passes_penalty_area",
        "crosses_penalty_area", "progressive_passes",
        "sca", "gca", "sca_pass_live", "sca_pass_dead",
        "sca_take_on", "sca_shot", "gca_pass_live", "gca_take_on",
        "tackles", "tackles_won", "challenge_tackles", "challenges",
        "blocks", "blocked_shots", "blocked_passes",
        "interceptions", "tkl_int", "clearances",
        "touches", "touches_att_pen", "take_ons_att", "take_ons_succ",
        "carries", "progressive_carries", "carries_final_third",
        "carries_penalty_area", "miscontrols", "dispossessed",
        "progressive_passes_received",
        "fouls_committed", "fouls_drawn", "offsides", "crosses",
        "ball_recoveries", "aerials_won", "aerials_lost",
    ]
    _float_fields = ["xg", "npxg", "xa", "npxg_xa"]
    for f in _int_fields + _float_fields:
        setattr(base, f, sum(getattr(r, f) or 0 for r in season_rows) or None)

    # Ricalcola % derivate
    m = base.minutes or 1
    base.xg_per90   = round((base.xg   or 0) / m * 90, 4)
    base.xa_per90   = round((base.xa   or 0) / m * 90, 4)
    base.npxg_per90 = round((base.npxg or 0) / m * 90, 4)
    base.sca_per90  = round((base.sca  or 0) / m * 90, 4)
    base.gca_per90  = round((base.gca  or 0) / m * 90, 4)
    if base.passes_attempted:
        base.pass_completion_pct = round((base.passes_completed or 0) / base.passes_attempted * 100, 1)
    total_aer = (base.aerials_won or 0) + (base.aerials_lost or 0)
    base.aerials_won_pct = round((base.aerials_won or 0) / total_aer * 100, 1) if total_aer else None
    if base.take_ons_att:
        base.take_ons_succ_pct = round((base.take_ons_succ or 0) / base.take_ons_att * 100, 1)
    if base.challenges:
        base.challenge_tackles_pct = round((base.challenge_tackles or 0) / base.challenges * 100, 1)
    return base


def _best_sofa(rows: list) -> Optional["PlayerSofascoreStats"]:
    """
    Stessa logica di _best_fbref ma per SofaScore.
    """
    if not rows:
        return None

    from collections import defaultdict
    season_mins: dict[str, int] = defaultdict(int)
    for r in rows:
        season_mins[_normalize_season(r.season)] += int(r.minutes_played or 0)

    log.warning(
        f"[DEBUG-AGG] SofaScore season→mins map: {dict(season_mins)}"
    )

    best_season = max(season_mins, key=lambda s: (season_mins[s], s))
    season_rows = [r for r in rows if _normalize_season(r.season) == best_season]

    log.warning(
        f"[DEBUG-AGG] SofaScore stagione scelta: {best_season}, "
        f"righe={len(season_rows)}, "
        f"mins per riga={[r.minutes_played for r in season_rows]}"
    )

    if len(season_rows) == 1:
        return season_rows[0]

    from copy import copy
    base = copy(season_rows[0])
    base.minutes_played = sum(int(r.minutes_played or 0) for r in season_rows)

    _int_fields = [
        "goals", "assists", "shots_total", "shots_on_target",
        "big_chances_created", "big_chances_missed",
        "accurate_passes", "inaccurate_passes", "total_passes",
        "accurate_long_balls", "total_long_balls",
        "accurate_crosses", "total_crosses", "key_passes",
        "accurate_final_third_passes",
        "successful_dribbles", "dribble_attempts", "dribbled_past", "dispossessed",
        "ground_duels_won", "aerial_duels_won", "aerial_duels_lost",
        "total_duels_won", "total_contest",
        "tackles", "tackles_won", "interceptions", "clearances",
        "blocked_shots", "ball_recovery", "possession_won_att_third",
        "touches", "fouls_committed", "fouls_won",
        "yellow_cards", "red_cards",
    ]
    _float_fields = ["xg", "xa"]
    for f in _int_fields + _float_fields:
        setattr(base, f, sum(getattr(r, f) or 0 for r in season_rows) or None)

    m = base.minutes_played or 1
    base.xg_per90 = round((base.xg or 0) / m * 90, 4)
    base.xa_per90 = round((base.xa or 0) / m * 90, 4)
    if base.total_passes:
        base.pass_accuracy_pct = round((base.accurate_passes or 0) / base.total_passes * 100, 1)
    if base.total_crosses:
        base.cross_accuracy_pct = round((base.accurate_crosses or 0) / base.total_crosses * 100, 1)
    if base.dribble_attempts:
        base.dribble_success_pct = round((base.successful_dribbles or 0) / base.dribble_attempts * 100, 1)
    total_aer = (base.aerial_duels_won or 0) + (base.aerial_duels_lost or 0)
    base.aerial_duels_won_pct = round((base.aerial_duels_won or 0) / total_aer * 100, 1) if total_aer else None
    if base.total_contest:
        base.total_duels_won_pct = round((base.total_duels_won or 0) / base.total_contest * 100, 1)
    if base.tackles:
        base.tackles_won_pct = round((base.tackles_won or 0) / base.tackles * 100, 1)
    return base

def _extract_raw_metrics(db: Session, player: ScoutingPlayer) -> dict:
    """
    Fonde i dati FBref e SofaScore in un unico vettore di metriche /90.
    Aggrega tutte le righe della stagione più ricca di minuti (es. Serie A + UCL).

    MODIFICHE v3.2:
    ───────────────
    1. yellow_cards: SofaScore è ora la fonte primaria.
       FBref aggrega le YC di TUTTE le competizioni nella tabella `standard`
       (es. Serie A + Supercoppa), gonfiando il conteggio per la singola lega.
       SofaScore tiene invece i conteggi separati per competizione → più preciso.

    2. fouls_committed / fouls_won: aggiunti al dict di ritorno.
       Erano calcolati internamente ma non esposti, rendendo impossibile
       usarli nei calcoli di pressing e disciplina downstream.
    """
    all_fbref = (
        db.query(PlayerFbrefStats)
        .filter(PlayerFbrefStats.player_id == player.id)
        .all()
    )
    all_sofa = (
        db.query(PlayerSofascoreStats)
        .filter(PlayerSofascoreStats.player_id == player.id)
        .all()
    )

    if all_fbref or all_sofa:
        log.warning(
            f"[DEBUG-RAW] {player.name} (id={player.id}): "
            f"fbref_rows={len(all_fbref)}, sofa_rows={len(all_sofa)} | "
            f"fbref seasons={[f'{r.season}:{r.minutes}min' for r in all_fbref]} | "
            f"sofa seasons={[f'{r.season}:{r.minutes_played}min' for r in all_sofa]}"
        )

    fbref = _best_fbref(all_fbref)
    sofa = _best_sofa(all_sofa)

    sources = []
    if fbref: sources.append("fbref")
    if sofa:  sources.append("sofascore")

    if not fbref and not sofa:
        return {"minutes": 0, "sources": [], "confidence": 0.0}

    fb_mins = int(_v(fbref, "minutes") or 0)
    ss_mins = int(_v(sofa, "minutes_played") or 0)
    minutes = max(fb_mins, ss_mins)

    log.warning(
        f"[DEBUG-RAW] {player.name}: fb_mins={fb_mins}, ss_mins={ss_mins}, "
        f"→ minutes_usati={minutes}"
    )

    if minutes < 1:
        return {"minutes": 0, "sources": sources, "confidence": 0.0}

    ref_mins = fb_mins if fb_mins >= ss_mins else ss_mins
    p90 = 90.0 / ref_mins

    source_score = 1.0 if len(sources) == 2 else 0.6
    min_score = min(1.0, ref_mins / 900.0)
    confidence = round(source_score * min_score, 3)

    def _per90(val) -> Optional[float]:
        if val is None: return None
        return round(float(val) * p90, 4)

    def _merge(fb_val, ss_val, fb_w=0.6, ss_w=0.4) -> Optional[float]:
        if fb_val is not None and ss_val is not None:
            return round(float(fb_val) * fb_w + float(ss_val) * ss_w, 4)
        return fb_val if fb_val is not None else ss_val

    xg_per90 = _merge(_v(fbref, "xg_per90"), _per90(_v(sofa, "xg")))
    xa_per90 = _merge(_v(fbref, "xa_per90"), _v(sofa, "xa_per90") or _per90(_v(sofa, "xa")))
    npxg_per90 = _v(fbref, "npxg_per90")

    fb_goals = _v(fbref, "goals") or 0
    ss_goals = _v(sofa, "goals") or 0
    fb_shots = _v(fbref, "shots") or 0
    ss_shots = _v(sofa, "shots_total") or 0
    fb_sot = _v(fbref, "shots_on_target") or 0
    ss_sot = _v(sofa, "shots_on_target") or 0

    goals = fb_goals if fb_goals >= ss_goals else ss_goals
    shots = fb_shots if fb_shots >= ss_shots else ss_shots
    sot = fb_sot if fb_sot >= ss_sot else ss_sot

    goals_per_shot = round(goals / shots, 4) if shots >= 3 else None
    sot_pct = round(sot / shots * 100, 1) if shots > 0 else None

    goal_conv_ss = _v(sofa, "goal_conversion_pct")
    goal_conv_fb = round(goals / shots * 100, 1) if shots >= 3 else None
    goal_conv = _merge(goal_conv_fb, goal_conv_ss)

    sca_per90 = _per90(_v(fbref, "sca"))
    gca_per90 = _per90(_v(fbref, "gca"))
    key_passes_per90 = _merge(_per90(_v(fbref, "key_passes")), _per90(_v(sofa, "key_passes")))
    bcc_per90 = _per90(_v(sofa, "big_chances_created"))
    prog_passes_per90 = _per90(_v(fbref, "progressive_passes"))
    passes_final3_per90 = _per90(_v(fbref, "passes_final_third") or _v(sofa, "accurate_final_third_passes"))

    pass_completion_pct = _merge(_v(fbref, "pass_completion_pct"), _v(sofa, "pass_accuracy_pct"))
    passes_long_pct = _v(fbref, "passes_long_pct")
    prog_rec_per90 = _per90(_v(fbref, "progressive_passes_received"))
    cross_acc_pct = _v(sofa, "cross_accuracy_pct")
    crosses_per90 = _per90(_v(fbref, "crosses") or _v(sofa, "total_crosses"))

    tackles_won = _merge(_v(fbref, "tackles_won"), _v(sofa, "tackles_won"))
    tackles_won_per90 = _per90(tackles_won)
    interceptions = _merge(_v(fbref, "interceptions"), _v(sofa, "interceptions"))
    interceptions_per90 = _per90(interceptions)
    clearances_per90 = _merge(_per90(_v(fbref, "clearances")), _per90(_v(sofa, "clearances")))
    ball_rec = _merge(_v(fbref, "ball_recoveries"), _v(sofa, "ball_recovery"))
    ball_recoveries_per90 = _per90(ball_rec)
    poss_won_att_per90 = _per90(_v(sofa, "possession_won_att_third"))

    prog_carries_per90 = _per90(_v(fbref, "progressive_carries"))
    carries_final3_p90 = _per90(_v(fbref, "carries_final_third"))
    touches_att_pen_p90 = _per90(_v(fbref, "touches_att_pen"))
    take_ons_succ_pct = _merge(_v(fbref, "take_ons_succ_pct"), _v(sofa, "dribble_success_pct"))
    succ_drib_per90 = _per90(_v(sofa, "successful_dribbles"))

    aerials_won_pct = _merge(_v(fbref, "aerials_won_pct"), _v(sofa, "aerial_duels_won_pct"))
    duels_won_pct = _v(sofa, "total_duels_won_pct")
    blocked_per90 = _merge(_per90(_v(fbref, "blocked_shots")), _per90(_v(sofa, "blocked_shots")))
    challenge_tkl_pct = _v(fbref, "challenge_tackles_pct")

    # ── MODIFICA 1: yellow_cards — SofaScore primario ─────────────────────────
    # FBref `tables.standard.cards_yellow` aggrega TUTTE le competizioni della
    # stagione in un'unica riga (Serie A + Supercoppa + UCL ecc.), quindi il
    # valore che finisce in player_fbref_stats per la riga "Serie A" è già
    # sovrascritto con il totale multi-competizione → numero gonfiato.
    # SofaScore tiene i conteggi per-competizione → più preciso per la lega.
    # Fallback su FBref solo se SofaScore non è disponibile.
    yellow_cards = (
        _v(fbref, "yellow_cards")  # FBref: da match_log, più completo ✅
        if fbref is not None
        else _v(sofa, "yellow_cards")      # SofaScore: solo se FBref assente
    )
    yellow_cards_per90 = _per90(yellow_cards)

    # ── MODIFICA 2: fouls — esposti nel dict di ritorno ───────────────────────
    # Erano ignorati prima; utili per indici di disciplina/pressing downstream.
    fouls_committed = _merge(_v(fbref, "fouls"), _v(sofa, "fouls_committed"))
    fouls_committed_per90 = _per90(fouls_committed)
    fouls_won_per90 = _per90(_v(sofa, "fouls_won"))

    return {
        "minutes": minutes,
        "sources": sources,
        "confidence": confidence,
        # ── Finishing ───────────────────────────────────────
        "xg_per90": xg_per90,
        "xa_per90": xa_per90,
        "npxg_per90": npxg_per90,
        "goals_per_shot": goals_per_shot,
        "sot_pct": sot_pct,
        "goal_conv_pct": goal_conv,
        # ── Creatività ──────────────────────────────────────
        "key_passes_per90": key_passes_per90,
        "bcc_per90": bcc_per90,
        "sca_per90": sca_per90,
        "gca_per90": gca_per90,
        "prog_passes_per90": prog_passes_per90,
        "passes_final3_per90": passes_final3_per90,
        # ── Costruzione ─────────────────────────────────────
        "pass_completion_pct": pass_completion_pct,
        "passes_long_pct": passes_long_pct,
        "prog_rec_per90": prog_rec_per90,
        "cross_acc_pct": cross_acc_pct,
        "crosses_per90": crosses_per90,
        # ── Pressing ────────────────────────────────────────
        "tackles_won_per90": tackles_won_per90,
        "interceptions_per90": interceptions_per90,
        "clearances_per90": clearances_per90,
        "ball_recoveries_per90": ball_recoveries_per90,
        "poss_won_att_per90": poss_won_att_per90,
        # ── Carrying ────────────────────────────────────────
        "prog_carries_per90": prog_carries_per90,
        "carries_final3_p90": carries_final3_p90,
        "touches_att_pen_p90": touches_att_pen_p90,
        "take_ons_succ_pct": take_ons_succ_pct,
        "succ_drib_per90": succ_drib_per90,
        # ── Difesa ──────────────────────────────────────────
        "aerials_won_pct": aerials_won_pct,
        "duels_won_pct": duels_won_pct,
        "blocked_per90": blocked_per90,
        "challenge_tkl_pct": challenge_tkl_pct,
        # ── Disciplina (NUOVO) ───────────────────────────────
        "yellow_cards": yellow_cards,  # valore assoluto stagionale
        "yellow_cards_per90": yellow_cards_per90,
        "fouls_committed_per90": fouls_committed_per90,
        "fouls_won_per90": fouls_won_per90,
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CALCOLO SCORE ASSOLUTI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _compute_abs_scores(raw: dict) -> dict:
    def _avg(*vals, weights=None) -> Optional[float]:
        pairs = [
            (float(v), (weights[i] if weights else 1.0))
            for i, v in enumerate(vals)
            if v is not None
        ]
        if not pairs:
            return None
        total_w = sum(w for _, w in pairs)
        return round(sum(v * w for v, w in pairs) / total_w, 6)

    finishing = _avg(
        raw.get("npxg_per90") or raw.get("xg_per90"),
        raw.get("goals_per_shot"),
        raw.get("sot_pct"),
        weights=[4, 3, 2],
    )
    creativity = _avg(
        raw.get("xa_per90"),
        raw.get("key_passes_per90"),
        raw.get("sca_per90"),
        raw.get("gca_per90"),
        raw.get("bcc_per90") or raw.get("prog_passes_per90"),
        weights=[3, 2, 3, 3, 1],
    )
    pressing = _avg(
        raw.get("tackles_won_per90"),
        raw.get("interceptions_per90"),
        raw.get("ball_recoveries_per90"),
        raw.get("clearances_per90"),
        raw.get("poss_won_att_per90"),
        weights=[3, 3, 2, 1, 2],
    )
    if raw.get("prog_carries_per90") is not None:
        carrying = _avg(
            raw.get("prog_carries_per90"),
            raw.get("take_ons_succ_pct"),
            raw.get("touches_att_pen_p90"),
            raw.get("succ_drib_per90"),
            weights=[4, 2, 2, 1],
        )
    else:
        carrying = _avg(
            raw.get("succ_drib_per90"),
            raw.get("take_ons_succ_pct"),
            raw.get("crosses_per90"),
            weights=[3, 3, 1],
        )
    defending = _avg(
        raw.get("interceptions_per90"),
        raw.get("clearances_per90"),
        raw.get("aerials_won_pct"),
        raw.get("duels_won_pct"),
        raw.get("challenge_tkl_pct"),
        raw.get("blocked_per90"),
        weights=[3, 2, 2, 2, 2, 1],
    )
    buildup = _avg(
        raw.get("pass_completion_pct"),
        raw.get("prog_passes_per90"),
        raw.get("passes_final3_per90"),
        raw.get("xa_per90"),
        raw.get("cross_acc_pct"),
        weights=[3, 3, 2, 2, 1],
    )

    return {
        "finishing":  finishing,
        "creativity": creativity,
        "pressing":   pressing,
        "carrying":   carrying,
        "defending":  defending,
        "buildup":    buildup,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _v(obj, attr: str) -> Optional[float]:
    if obj is None:
        return None
    val = getattr(obj, attr, None)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _position_group(player: ScoutingPlayer) -> str:
    pos = (player.position or "CM").strip().upper()
    aliases = {"G": "GK", "POR": "GK", "DC": "CB", "DL": "LB", "DR": "RB",
               "WB": "LB", "MC": "CM", "ML": "LM", "MR": "RM", "CAM": "AM",
               "CDM": "DM", "MID": "CM", "FW": "ST", "FWD": "ST",
               "CENTRE-FORWARD": "ST",
               "CENTRE FORWARD": "ST",
               "ATTACKING MIDFIELDER": "AM",
               "CENTRAL MIDFIELDER": "CM",
               "DEFENSIVE MIDFIELDER": "DM",
               "LEFT MIDFIELDER": "LW",
               "RIGHT MIDFIELDER": "RW",
               "LEFT BACK": "LB",
               "RIGHT BACK": "RB",
               "CENTRE BACK": "CB",
               "GOALKEEPER": "GK",
               "LEFT WINGER": "LW",
               "RIGHT WINGER": "RW",
               }
    return aliases.get(pos, pos)


def _current_season() -> str:
    """Restituisce la stagione corrente in formato corto es. "2025-26"."""
    now = datetime.utcnow()
    y, m = now.year, now.month
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"