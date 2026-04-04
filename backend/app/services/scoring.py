"""
services/scoring.py — v3.1
---------------------------
MODIFICHE v3.0 → v3.1:

  FIX 4 — defending score consapevole del ruolo CB/fullback:
    Il vecchio defending usava solo duels_won_pct + aerial_won_pct + tackles_p90.
    Per un CB (Gatti) questo dava score bassissimo perché i CB fanno pochi tackles
    ma molte respinte, intercetti e recuperi — dati presenti in SofaScore ma ignorati.

    Nuovo _compute_defending():
      Livello A (formula storica): duelli + tackles — buono per CM/DM
      Livello B (formula CB):      clearances + interceptions + ball_recovery +
                                   duelli aerei — buono per CB/fullback
      Risultato: max(A, B) — il giocatore prende sempre la formula più favorevole.

    Nuove metriche aggiunte a _merge_season_rows:
      clearances, interceptions, ball_recovery, tackles_won_pct

    Nuovi _REF calibrati (95° percentile CB):
      clearances_p90=5.0, interceptions_p90=1.5, ball_recovery_p90=4.5,
      tackles_won_pct=70.0

  Invariato rispetto a v3.0:
    FIX 1 — _merge_season_rows con priorità per fonte
    FIX 2 — soglie _REF ricalibrate
    FIX 3 — fallback onesti (pressing=0 se pressures=NULL)
"""

from __future__ import annotations
from app.models.models import ScoutingPlayer, PlayerSeasonStats


_REF = {
    "npxg_p90":           0.55,
    "shots_p90":          4.5,
    "goal_conversion":    0.30,
    "xa_p90":             0.35,
    "prog_passes_p90":    10.0,
    "key_passes_p90":     2.8,
    "pressures_p90":      30.0,
    "regains_p90":        4.0,
    "prog_carries_p90":   8.0,
    "dribbles_p90":       3.5,
    "touches_att_p90":    5.0,
    "duels_won_pct":      68.0,
    "aerial_won_pct":     68.0,
    "tackles_p90":        3.5,
    "tackles_won_pct":    70.0,   # % tackle vinti — 70% è buono per un difensore
    "clearances_p90":     5.0,    # 95° pct CB: ~5 respinte/90
    "interceptions_p90":  1.5,    # 95° pct CB: ~1.5 intercetti/90
    "ball_recovery_p90":  4.5,    # 95° pct: ~4.5 recuperi/90
    "xgchain_p90":        1.00,
    "xgbuildup_p90":      0.65,
}


def _safe(val, default: float = 0.0) -> float:
    return float(val) if val is not None else default


def _p90(raw, minutes) -> float:
    if raw is None or not minutes:
        return 0.0
    return float(raw) / (max(float(minutes), 1.0) / 90.0)


def _scale(value: float, ref: float) -> float:
    if ref <= 0:
        return 0.0
    return min(round((value / ref) * 100.0, 1), 100.0)


# Priorità fonte per ogni tipo di dato (numero più basso = più prioritario)
_SOURCE_PRIORITY = {
    'understat':     1,
    'fbref':         2,
    'sofascore':     3,
    'playwright_v9': 4,
    'playwright_v8': 5,
    'api_football':  6,
}

_FBREF_FIELDS = {
    'progressive_passes', 'progressive_carries', 'touches_att_pen',
    'pressures', 'pressure_regains', 'npxg_per90', 'xgchain_per90', 'xgbuildup_per90',
}
_UNDERSTAT_FIELDS = {'xg', 'xg_per90', 'xa', 'xa_per90'}


def _merge_season_rows(p: ScoutingPlayer) -> dict:
    """
    Aggrega le righe PlayerSeasonStats della stagione più recente.
    Per ogni campo prende il valore non-null dalla fonte con priorità più alta.
    """
    try:
        from sqlalchemy.orm import object_session
        from collections import defaultdict
        session = object_session(p)
        if not session:
            return {}

        rows = (
            session.query(PlayerSeasonStats)
            .filter(PlayerSeasonStats.player_id == p.id)
            .order_by(
                PlayerSeasonStats.season.desc(),
                PlayerSeasonStats.minutes_played.desc(),
            )
            .all()
        )
        if not rows:
            return {}

        # Prende la stagione più recente con più minuti
        best_season = rows[0].season
        # Tra tutte le leghe di quella stagione, prende quella con più minuti
        season_rows = [r for r in rows if r.season == best_season]
        best_league = max(
            set(r.league for r in season_rows),
            key=lambda lg: max(
                _safe(r.minutes_played) for r in season_rows if r.league == lg
            )
        )
        target_rows = [r for r in season_rows if r.league == best_league]

        def best_val(field, prefer_fbref=False, prefer_understat=False):
            if prefer_understat and field in _UNDERSTAT_FIELDS:
                priority_fn = lambda r: (
                    0 if 'understat' in (r.source or '') else
                    1 if 'fbref'     in (r.source or '') else
                    _SOURCE_PRIORITY.get(r.source, 99)
                )
            elif prefer_fbref or field in _FBREF_FIELDS:
                priority_fn = lambda r: (
                    0 if 'fbref'     in (r.source or '') else
                    _SOURCE_PRIORITY.get(r.source, 99)
                )
            else:
                priority_fn = lambda r: _SOURCE_PRIORITY.get(r.source, 99)

            for row in sorted(target_rows, key=priority_fn):
                val = getattr(row, field, None)
                if val is not None:
                    return val
            return None

        m = best_val('minutes_played') or 0

        return {
            'minutes_played':       m,
            'shots_total':          best_val('shots_total'),
            'xg':                   best_val('xg', prefer_understat=True),
            'xg_per90':             best_val('xg_per90', prefer_understat=True),
            'xa':                   best_val('xa', prefer_understat=True),
            'xa_per90':             best_val('xa_per90', prefer_understat=True),
            'npxg_per90':           best_val('npxg_per90', prefer_fbref=True),
            'goals':                best_val('goals'),
            'key_passes':           best_val('key_passes'),
            'progressive_passes':   best_val('progressive_passes', prefer_fbref=True),
            'progressive_carries':  best_val('progressive_carries', prefer_fbref=True),
            'touches_att_pen':      best_val('touches_att_pen', prefer_fbref=True),
            'pressures':            best_val('pressures', prefer_fbref=True),
            'pressure_regains':     best_val('pressure_regains', prefer_fbref=True),
            'tackles':              best_val('tackles'),
            'tackles_won_pct':      best_val('tackles_won_pct'),
            'total_duels_won_pct':  best_val('total_duels_won_pct'),
            'aerial_duels_won_pct': best_val('aerial_duels_won_pct'),
            'clearances':           best_val('clearances'),
            'interceptions':        best_val('interceptions'),
            'ball_recovery':        best_val('ball_recovery'),
            'successful_dribbles':  best_val('successful_dribbles'),
            'xgchain_per90':        best_val('xgchain_per90', prefer_fbref=True),
            'xgbuildup_per90':      best_val('xgbuildup_per90', prefer_fbref=True),
        }

    except Exception:
        return {}


def normalize_per90(p: ScoutingPlayer) -> dict:
    merged = _merge_season_rows(p)

    if not merged:
        m = _safe(p.minutes_season)
        return {k: 0.0 for k in [
            "npxg_p90", "xg_p90", "xa_p90", "xgchain_p90", "xgbuildup_p90",
            "shots_p90", "key_passes_p90", "prog_passes_p90", "prog_carries_p90",
            "dribbles_p90", "touches_att_p90", "pressures_p90", "regains_p90",
            "tackles_p90", "tackles_won_pct", "clearances_p90", "interceptions_p90",
            "ball_recovery_p90", "duels_won_pct", "aerial_won_pct", "goal_conversion",
        ]} | {"minutes": m}

    m = _safe(merged.get('minutes_played'))

    npxg_p90_val = (
        _safe(merged.get('npxg_per90'))
        or _safe(merged.get('xg_per90'))
        or _p90(merged.get('xg'), m)
    )
    xg_p90_val = _safe(merged.get('xg_per90')) or _p90(merged.get('xg'), m)

    xa_per90_raw = _safe(merged.get('xa_per90'))
    xa_total = _safe(merged.get('xa'))
    if xa_per90_raw > 1.5 and m > 0:
        xa_p90_val = _p90(xa_total if xa_total else xa_per90_raw, m)
    else:
        xa_p90_val = xa_per90_raw or _p90(xa_total, m)

    goals_val = _safe(merged.get('goals'))
    xg_total  = _safe(merged.get('xg'))
    goal_conversion_val = (goals_val / xg_total) if xg_total > 0.01 else 0.0

    return {
        "npxg_p90":         npxg_p90_val,
        "xg_p90":           xg_p90_val,
        "xa_p90":           xa_p90_val,
        "xgchain_p90":      _safe(merged.get('xgchain_per90')),
        "xgbuildup_p90":    _safe(merged.get('xgbuildup_per90')),
        "shots_p90":        _p90(merged.get('shots_total'), m),
        "key_passes_p90":   _p90(merged.get('key_passes'), m),
        "prog_passes_p90":  _p90(merged.get('progressive_passes'), m),
        "prog_carries_p90": _p90(merged.get('progressive_carries'), m),
        "dribbles_p90":     _p90(merged.get('successful_dribbles'), m),
        "touches_att_p90":  _p90(merged.get('touches_att_pen'), m),
        "pressures_p90":    _p90(merged.get('pressures'), m),
        "regains_p90":      _p90(merged.get('pressure_regains'), m),
        "tackles_p90":      _p90(merged.get('tackles'), m),
        "tackles_won_pct":  _safe(merged.get('tackles_won_pct')),
        "clearances_p90":   _p90(merged.get('clearances'), m),
        "interceptions_p90":_p90(merged.get('interceptions'), m),
        "ball_recovery_p90":_p90(merged.get('ball_recovery'), m),
        "duels_won_pct":    _safe(merged.get('total_duels_won_pct')),
        "aerial_won_pct":   _safe(merged.get('aerial_duels_won_pct')),
        "goal_conversion":  goal_conversion_val,
        "minutes":          m,
    }


def _compute_defending(v: dict) -> float:
    """
    Calcola il defending score con due livelli di dati:

    Livello A — dati FBref (pressures, regains): formula completa
    Livello B — solo dati SofaScore (clearances, interceptions, ball_recovery):
                formula alternativa pensata per CB e fullback che fanno
                pochi tackle ma molte respinte/intercetti/recuperi.

    Se entrambi i livelli hanno dati, prende il massimo tra i due
    (un giocatore non deve essere penalizzato per avere dati più ricchi).
    """
    # Livello A: formula storica con duelli + tackles (funziona per CM/DM)
    score_a = (
        _scale(v["duels_won_pct"],  _REF["duels_won_pct"])  * 0.40 +
        _scale(v["aerial_won_pct"], _REF["aerial_won_pct"]) * 0.35 +
        _scale(v["tackles_p90"],    _REF["tackles_p90"])     * 0.25
    )

    # Livello B: formula CB/fullback con clearances, interceptions, ball_recovery
    # Disponibili da SofaScore — proxy solido per difensori puri
    has_cb_data = (
        v.get("clearances_p90", 0) > 0 or
        v.get("interceptions_p90", 0) > 0 or
        v.get("ball_recovery_p90", 0) > 0
    )
    if has_cb_data:
        score_b = (
            _scale(v["duels_won_pct"],      _REF["duels_won_pct"])      * 0.20 +
            _scale(v["aerial_won_pct"],     _REF["aerial_won_pct"])     * 0.20 +
            _scale(v["clearances_p90"],     _REF["clearances_p90"])     * 0.25 +
            _scale(v["interceptions_p90"],  _REF["interceptions_p90"])  * 0.20 +
            _scale(v["ball_recovery_p90"],  _REF["ball_recovery_p90"])  * 0.15
        )
        # Bonus tackles_won_pct se disponibile (qualità del tackle, non volume)
        if v.get("tackles_won_pct", 0) > 0:
            score_b = score_b * 0.90 + _scale(v["tackles_won_pct"], _REF["tackles_won_pct"]) * 0.10
        return max(score_a, score_b)

    return score_a


def compute_objective_scores(p: ScoutingPlayer) -> dict:
    v = normalize_per90(p)

    finishing = (
        _scale(v["npxg_p90"],        _REF["npxg_p90"])        * 0.50 +
        _scale(v["shots_p90"],       _REF["shots_p90"])        * 0.30 +
        _scale(v["goal_conversion"], _REF["goal_conversion"])  * 0.20
    )
    creativity = (
        _scale(v["xa_p90"],          _REF["xa_p90"])           * 0.40 +
        _scale(v["prog_passes_p90"], _REF["prog_passes_p90"])  * 0.35 +
        _scale(v["key_passes_p90"],  _REF["key_passes_p90"])   * 0.25
    )
    # Pressing: 0 se pressures NULL — nessun proxy inventato
    pressing = (
        _scale(v["pressures_p90"],   _REF["pressures_p90"])    * 0.50 +
        _scale(v["regains_p90"],     _REF["regains_p90"])       * 0.50
    )
    # Carrying: fallback su dribbles se carries mancano
    if v["prog_carries_p90"] > 0:
        carrying = (
            _scale(v["prog_carries_p90"], _REF["prog_carries_p90"]) * 0.60 +
            _scale(v["touches_att_p90"],  _REF["touches_att_p90"])  * 0.40
        )
    elif v["dribbles_p90"] > 0:
        carrying = (
            _scale(v["dribbles_p90"],    _REF["dribbles_p90"])      * 0.60 +
            _scale(v["touches_att_p90"], _REF["touches_att_p90"])   * 0.40
        )
    else:
        carrying = 0.0

    defending = _compute_defending(v)
    # Buildup: proxy xa+prog_passes se xgchain NULL (penalizzato -25%)
    if v["xgchain_p90"] > 0 or v["xgbuildup_p90"] > 0:
        buildup = (
            _scale(v["xgchain_p90"],    _REF["xgchain_p90"])    * 0.60 +
            _scale(v["xgbuildup_p90"],  _REF["xgbuildup_p90"])  * 0.40
        )
    else:
        buildup = (
            _scale(v["xa_p90"],          _REF["xa_p90"])          * 0.50 +
            _scale(v["prog_passes_p90"], _REF["prog_passes_p90"]) * 0.50
        ) * 0.75

    def clamp(x): return min(round(x, 1), 100.0)

    finishing_s  = clamp(finishing)
    creativity_s = clamp(creativity)
    pressing_s   = clamp(pressing)
    carrying_s   = clamp(carrying)
    defending_s  = clamp(defending)
    buildup_s    = clamp(buildup)
    heading_s    = clamp(
        _scale(v["aerial_won_pct"], _REF["aerial_won_pct"]) * 0.60 +
        defending_s                                          * 0.40
    )

    return {
        "finishing_score":     finishing_s,
        "creativity_score":    creativity_s,
        "pressing_score":      pressing_s,
        "carrying_score":      carrying_s,
        "defending_obj_score": defending_s,
        "buildup_obj_score":   buildup_s,
        "heading_score":       heading_s,
        "build_up_score":      buildup_s,
        "defensive_score":     defending_s,
    }


def compute_scores(p: ScoutingPlayer) -> dict:
    return compute_objective_scores(p)


def recalculate_all(db, progress_cb=None) -> int:
    players = db.query(ScoutingPlayer).all()
    total   = len(players)
    updated = 0
    for i, p in enumerate(players):
        scores = compute_objective_scores(p)
        for key, val in scores.items():
            if hasattr(p, key):
                setattr(p, key, val)
        updated += 1
        if progress_cb and i % 100 == 0:
            progress_cb(i + 1, total)
    db.commit()
    print(f"  → scoring: {updated} giocatori aggiornati su {total}")
    return updated


if __name__ == "__main__":
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        n = recalculate_all(db)
        print(f"Completato: {n} giocatori aggiornati.")
    finally:
        db.close()