"""
services/scoring.py — Fase 2 + Fase 3 pipeline oggettivo
---------------------------------------------------------

FASE 2 — Normalizzazione per 90 min
    Tutti i valori raw stagionali vengono divisi per (minuti / 90).
    Questo elimina il bias da minutaggio: un giocatore con 30 partite
    non sembra automaticamente migliore di uno con 10.

    Convenzione di naming:
        _p90(raw_value, minutes)  →  raw_value / (minutes / 90)

    I valori per90 già presenti nel modello (xg_per90, xa_per90, npxg_per90,
    xgchain_per90, xgbuildup_per90) sono già normalizzati dalle sorgenti
    (Understat, StatsBomb) — non vanno ricalcolati qui.

    Valori raw che normalizziamo qui:
        goals_season         → goals_p90
        shots_season         → shots_p90
        key_passes_season    → key_passes_p90
        progressive_passes   → prog_passes_p90
        progressive_carries  → prog_carries_p90
        touches_att_pen      → touches_att_pen_p90
        pressures_season     → pressures_p90
        pressure_regains     → regains_p90
        tackles_season       → tackles_p90

FASE 3 — Score dimensionali 0-100
    Sei score compositi calcolati da valori per-90:

        finishing_score  = npxG/90 · 0.5 + tiri/90 · 0.3 + conversione gol/xG · 0.2
        creativity_score = xA/90   · 0.4 + PrgP/90 · 0.35 + key_passes/90 · 0.25
        pressing_score   = pressioni/90 · 0.5 + regains/90 · 0.5
        carrying_score   = PrgC/90 · 0.6 + tocchi_area/90 · 0.4
        defending_score  = duelli_vinti% · 0.4 + aerei_vinti% · 0.35 + tackle/90 · 0.25
        buildup_score    = xGChain/90 · 0.6 + xGBuildup/90 · 0.4

    Ogni score viene scalato su 0-100 rispetto a soglie di riferimento
    calibrate su Serie A / Premier League (puoi aggiustarle).

    Score legacy (heading_score, build_up_score, defensive_score)
    vengono mappati agli score oggettivi per compatibilità UI:
        heading_score   ← defending_obj_score (con peso aereo)
        build_up_score  ← buildup_obj_score
        defensive_score ← defending_obj_score

Come aggiornare dopo ogni importazione:
    POST /admin/recalculate-scores
    oppure da shell: python -m app.services.scoring
"""

from __future__ import annotations
from app.models.models import ScoutingPlayer


# ─────────────────────────────────────────────────────────────────
# SOGLIE DI RIFERIMENTO PER SCALATURA 0-100
# Rappresentano il valore "eccellente" (≈ top 5% Serie A / PL).
# Un giocatore che raggiunge la soglia ottiene ~100; chi è a metà ~50.
# ─────────────────────────────────────────────────────────────────
_REF = {
    # Finishing
    "npxg_p90":         0.60,   # ~top attaccanti PL/Serie A
    "shots_p90":        5.0,    # tiri per 90 (top finisher)
    "goal_conversion":  0.25,   # gol / xG (25% = eccellente finisher)

    # Creativity
    "xa_p90":           0.40,
    "prog_passes_p90":  8.0,    # passaggi progressivi / 90
    "key_passes_p90":   2.5,

    # Pressing
    "pressures_p90":    20.0,   # pressioni / 90 (top pressers)
    "regains_p90":      3.0,    # recuperi da pressing / 90

    # Carrying
    "prog_carries_p90": 5.0,    # conduzioni progressive / 90
    "touches_att_p90":  4.0,    # tocchi in area avv. / 90

    # Defending
    "duels_won_pct":    65.0,   # % duelli vinti (0-100)
    "aerial_won_pct":   65.0,   # % duelli aerei vinti (0-100)
    "tackles_p90":      3.0,    # tackle / 90

    # Build-up
    "xgchain_p90":      0.80,
    "xgbuildup_p90":    0.50,
}


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def _safe(val, default: float = 0.0) -> float:
    """Restituisce float(val) se non è None, altrimenti default."""
    return float(val) if val is not None else default


def _p90(raw: float | None, minutes: float | None) -> float:
    """
    Normalizza un valore raw per 90 minuti.
    Restituisce 0 se raw o minutes sono None/0.
    Usa max(minutes, 1) per evitare divisione per zero.
    """
    if raw is None or not minutes:
        return 0.0
    return float(raw) / (max(float(minutes), 1.0) / 90.0)


def _scale(value: float, ref: float) -> float:
    """
    Scala un valore su 0-100 rispetto a una soglia di riferimento.
    - value = 0          → score 0
    - value = ref        → score 100
    - value > ref        → score cappato a 100
    Usa scalatura lineare (semplice e interpretabile).
    """
    if ref <= 0:
        return 0.0
    return min(round((value / ref) * 100.0, 1), 100.0)


# ─────────────────────────────────────────────────────────────────
# FASE 2 — NORMALIZZAZIONE PER 90 MIN
# ─────────────────────────────────────────────────────────────────

def normalize_per90(p: ScoutingPlayer) -> dict:
    """
    Calcola tutti i valori normalizzati per 90 min a partire dai raw.
    NON scrive sul DB — restituisce un dizionario di valori intermedi
    usato da compute_objective_scores().

    I valori xg_per90, xa_per90, npxg_per90, xgchain_per90, xgbuildup_per90
    sono già per-90 (calcolati dalle sorgenti) — vengono riusati direttamente.
    """
    m = _safe(p.minutes_season)

    return {
        # già per-90 dalle sorgenti
        "npxg_p90":         _safe(p.npxg_per90)      or _safe(p.xg_per90),
        "xg_p90":           _safe(p.xg_per90),
        "xa_p90":           _safe(p.xa_per90),
        "xgchain_p90":      _safe(p.xgchain_per90),
        "xgbuildup_p90":    _safe(p.xgbuildup_per90),

        # normalizzati da raw stagionali
        "goals_p90":        _p90(p.goals_season,              m),
        "shots_p90":        _p90(p.shots_season,              m),
        "key_passes_p90":   _p90(p.key_passes_season,         m),
        "prog_passes_p90":  _p90(p.progressive_passes,        m),
        "prog_carries_p90": _p90(p.progressive_carries,       m),
        "touches_att_p90":  _p90(p.touches_att_pen_season,    m),
        "pressures_p90":    _p90(p.pressures_season,          m),
        "regains_p90":      _p90(p.pressure_regains_season,   m),
        "tackles_p90":      _p90(p.tackles_season,            m),

        # già percentuali (non vanno divise per minuti)
        "duels_won_pct":    _safe(p.duels_won_pct),
        "aerial_won_pct":   _safe(p.aerial_duels_won_pct),
        "pass_acc_pct":     _safe(p.pass_accuracy_pct),

        # conversione gol/xG (efficienza realizzativa)
        # rapporto tra gol reali e xG — >1 = overperforming
        "goal_conversion":  (
            _safe(p.goals_season) / max(_safe(p.xg_per90) * (m / 90.0), 0.01)
            if p.minutes_season and p.minutes_season > 0 and p.xg_per90
            else 0.0
        ),

        # minuti (utile per debug / percentili)
        "minutes": m,
    }


# ─────────────────────────────────────────────────────────────────
# FASE 3 — SCORE DIMENSIONALI 0-100
# ─────────────────────────────────────────────────────────────────

def compute_objective_scores(p: ScoutingPlayer) -> dict:
    """
    Calcola i sei score dimensionali oggettivi (0-100) + i tre legacy.

    Pipeline:
        raw stagionali  →  normalizzazione p90  →  score composito  →  scalatura 0-100

    Ritorna un dizionario con tutti i campi da salvare nel DB.
    """
    v = normalize_per90(p)

    # ── Finishing Score ──────────────────────────────────────────
    # Misura la pericolosità realizzativa: qualità e quantità del tiro
    finishing = (
        _scale(v["npxg_p90"],       _REF["npxg_p90"])       * 0.50 +
        _scale(v["shots_p90"],      _REF["shots_p90"])       * 0.30 +
        _scale(v["goal_conversion"],_REF["goal_conversion"]) * 0.20
    )

    # ── Creativity Score ─────────────────────────────────────────
    # Misura la capacità di creare occasioni per i compagni
    creativity = (
        _scale(v["xa_p90"],         _REF["xa_p90"])          * 0.40 +
        _scale(v["prog_passes_p90"],_REF["prog_passes_p90"]) * 0.35 +
        _scale(v["key_passes_p90"], _REF["key_passes_p90"])  * 0.25
    )

    # ── Pressing Score ───────────────────────────────────────────
    # Misura l'intensità e l'efficacia del pressing
    pressing = (
        _scale(v["pressures_p90"],  _REF["pressures_p90"])   * 0.50 +
        _scale(v["regains_p90"],    _REF["regains_p90"])      * 0.50
    )

    # ── Carrying Score ───────────────────────────────────────────
    # Misura la capacità di portare la palla in avanti con continuità
    carrying = (
        _scale(v["prog_carries_p90"],_REF["prog_carries_p90"])* 0.60 +
        _scale(v["touches_att_p90"], _REF["touches_att_p90"]) * 0.40
    )

    # ── Defending Score ──────────────────────────────────────────
    # Misura l'efficacia difensiva su duelli, aerei e contrasti
    defending = (
        _scale(v["duels_won_pct"],  _REF["duels_won_pct"])   * 0.40 +
        _scale(v["aerial_won_pct"], _REF["aerial_won_pct"])   * 0.35 +
        _scale(v["tackles_p90"],    _REF["tackles_p90"])      * 0.25
    )

    # ── Build-up Score ───────────────────────────────────────────
    # Misura il contributo al gioco di costruzione (xGChain / xGBuildup)
    buildup = (
        _scale(v["xgchain_p90"],    _REF["xgchain_p90"])      * 0.60 +
        _scale(v["xgbuildup_p90"],  _REF["xgbuildup_p90"])    * 0.40
    )

    # Clamp finale 0-100 su tutti
    def clamp(x):
        return min(round(x, 1), 100.0)

    finishing_s  = clamp(finishing)
    creativity_s = clamp(creativity)
    pressing_s   = clamp(pressing)
    carrying_s   = clamp(carrying)
    defending_s  = clamp(defending)
    buildup_s    = clamp(buildup)

    # ── Score legacy — mappati agli oggettivi per compatibilità UI ─
    # heading_score   → defending con peso speciale per i duelli aerei
    heading_s = clamp(
        _scale(v["aerial_won_pct"], _REF["aerial_won_pct"]) * 0.60 +
        defending_s                                          * 0.40
    )

    return {
        # Score oggettivi (Fase 3)
        "finishing_score":     finishing_s,
        "creativity_score":    creativity_s,
        "pressing_score":      pressing_s,
        "carrying_score":      carrying_s,
        "defending_obj_score": defending_s,
        "buildup_obj_score":   buildup_s,

        # Score legacy (compatibilità UI / ricerca semantica)
        "heading_score":   heading_s,
        "build_up_score":  buildup_s,
        "defensive_score": defending_s,
    }


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT: recalculate_all
# ─────────────────────────────────────────────────────────────────

def compute_scores(p: ScoutingPlayer) -> dict:
    """
    Alias pubblico usato da admin.py e dai test.
    Chiama compute_objective_scores() (Fase 2 + 3).
    """
    return compute_objective_scores(p)


def recalculate_all(db, progress_cb=None) -> int:
    """
    Ricalcola tutti gli score per ogni giocatore nel DB.
    Chiama: POST /admin/recalculate-scores

    Args:
        db:          SQLAlchemy Session
        progress_cb: callable(done, total) opzionale per UI progress

    Returns:
        Numero di giocatori aggiornati.
    """
    players = db.query(ScoutingPlayer).all()
    total   = len(players)
    updated = 0

    for i, p in enumerate(players):
        scores = compute_objective_scores(p)
        for key, val in scores.items():
            # Scrive solo se la colonna esiste nel modello
            # (protezione se migration non ancora applicata)
            if hasattr(p, key):
                setattr(p, key, val)
        updated += 1

        if progress_cb and i % 100 == 0:
            progress_cb(i + 1, total)

    db.commit()
    print(f"  → scoring: {updated} giocatori aggiornati su {total}")
    return updated


# ─────────────────────────────────────────────────────────────────
# RUN DIRETTO  (python -m app.services.scoring)
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        n = recalculate_all(db)
        print(f"Completato: {n} giocatori aggiornati.")
    finally:
        db.close()