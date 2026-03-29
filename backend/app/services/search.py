"""
services/search.py — Fase 5: ricerca semantica su score percentili
------------------------------------------------------------------
La SEMANTIC_MAP usa i percentili per ruolo (*_pct) dove disponibili,
con fallback sugli score assoluti (0-100) per giocatori senza percentile.

Logica di soglia:
    - percentile > 70  →  top 30% nel proprio ruolo  (buono)
    - percentile > 80  →  top 20%                    (ottimo)
    - percentile > 90  →  top 10%                    (eccellente)

Per i valori senza percentile (giocatori con pochi minuti) il fallback
usa lo score assoluto con soglia calibrata.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, case, nulls_last, func
from app.models.models import ScoutingPlayer as M


# ─────────────────────────────────────────────────────────────────
# HELPER: condizione con fallback percentile → score assoluto
# ─────────────────────────────────────────────────────────────────

def _pct_or_score(pct_col, score_col, pct_threshold: float, score_threshold: float):
    """
    Restituisce una condizione OR:
        percentile >= pct_threshold   (se il percentile è disponibile)
        OR score >= score_threshold   (fallback se percentile è NULL)
    """
    pct_attr   = getattr(M, pct_col)
    score_attr = getattr(M, score_col)
    return or_(
        pct_attr   >= pct_threshold,
        and_(pct_attr.is_(None), score_attr >= score_threshold),
    )


# ─────────────────────────────────────────────────────────────────
# SEMANTIC MAP
# ─────────────────────────────────────────────────────────────────

SEMANTIC_MAP: dict = {

    # ── Qualità realizzativa ──────────────────────────────────────
    "finalizzatore":        lambda: _pct_or_score("finishing_pct",  "finishing_score",  70, 65),
    "bomber":               lambda: _pct_or_score("finishing_pct",  "finishing_score",  80, 72),
    "goleador":             lambda: _pct_or_score("finishing_pct",  "finishing_score",  80, 72),
    "realizzatore":         lambda: _pct_or_score("finishing_pct",  "finishing_score",  70, 60),
    "tiratore":             lambda: _pct_or_score("finishing_pct",  "finishing_score",  60, 55),
    "forte in area":        lambda: _pct_or_score("finishing_pct",  "finishing_score",  65, 58),

    # ── Creatività / assist ───────────────────────────────────────
    "assist man":           lambda: _pct_or_score("creativity_pct", "creativity_score", 70, 60),
    "creativo":             lambda: _pct_or_score("creativity_pct", "creativity_score", 65, 55),
    "ottimo passatore":     lambda: _pct_or_score("creativity_pct", "creativity_score", 70, 62),
    "tecnico":              lambda: _pct_or_score("creativity_pct", "creativity_score", 60, 52),
    "bravo col pallone":    lambda: _pct_or_score("creativity_pct", "creativity_score", 60, 52),

    # ── Pressing / intensità ──────────────────────────────────────
    "pressatore":           lambda: _pct_or_score("pressing_pct",   "pressing_score",   70, 60),
    "aggressivo":           lambda: _pct_or_score("pressing_pct",   "pressing_score",   65, 55),
    "intenso":              lambda: _pct_or_score("pressing_pct",   "pressing_score",   60, 50),
    "bravo in pressing":    lambda: _pct_or_score("pressing_pct",   "pressing_score",   70, 60),

    # ── Conduzioni / progressione ─────────────────────────────────
    "bravo in conduzione":  lambda: _pct_or_score("carrying_pct",   "carrying_score",   65, 55),
    "veloce":               lambda: _pct_or_score("carrying_pct",   "carrying_score",   70, 60),
    "portatore di palla":   lambda: _pct_or_score("carrying_pct",   "carrying_score",   70, 62),

    # ── Difesa ────────────────────────────────────────────────────
    "bravo in difesa":      lambda: _pct_or_score("defending_pct",  "defending_obj_score", 65, 58),
    "difensore solido":     lambda: _pct_or_score("defending_pct",  "defending_obj_score", 75, 65),
    "roccioso":             lambda: _pct_or_score("defending_pct",  "defending_obj_score", 80, 70),

    # ── Testa / duelli (score assoluto — già normalizzato) ─────────
    "bravo di testa":       lambda: M.heading_score >= 60,
    "forte fisicamente":    lambda: M.heading_score >= 55,
    "bravo nei duelli":     lambda: M.heading_score >= 60,

    # ── Build-up / costruzione ────────────────────────────────────
    "fa salire la squadra": lambda: _pct_or_score("buildup_pct",    "buildup_obj_score", 65, 55),
    "bravo in costruzione": lambda: _pct_or_score("buildup_pct",    "buildup_obj_score", 60, 50),
    "resistente":           lambda: _pct_or_score("buildup_pct",    "buildup_obj_score", 50, 42),

    # ── xG / xA diretti ───────────────────────────────────────────
    "alto xg":              lambda: M.xg_per90    >= 0.35,
    "alto xa":              lambda: M.xa_per90    >= 0.25,
    "npxg alto":            lambda: M.npxg_per90  >= 0.30,
    "xg chain":             lambda: M.xgchain_per90 >= 0.50,

    # ── Piede ─────────────────────────────────────────────────────
    "mancino":              lambda: M.preferred_foot == "Left",
    "destro":               lambda: M.preferred_foot == "Right",

    # ── Posizione ─────────────────────────────────────────────────
    "centravanti":          lambda: M.position == "ST",
    "trequartista":         lambda: M.position == "AM",
    "ala":                  lambda: M.position.in_(["LW", "RW"]),
    "terzino":              lambda: M.position.in_(["LB", "RB"]),
    "centrocampista":       lambda: M.position.in_(["CM", "DM", "AM"]),
    "mediano":              lambda: M.position.in_(["DM", "CM"]),
    "difensore centrale":   lambda: M.position == "CB",
    "portiere":             lambda: M.position == "GK",

    # ── Età ───────────────────────────────────────────────────────
    "giovane":              lambda: M.age <= 23,
    "under 21":             lambda: M.age <= 21,
    "under 23":             lambda: M.age <= 23,
    "under 25":             lambda: M.age <= 25,
    "esperto":              lambda: M.age >= 30,

    # ── Nazionalità ───────────────────────────────────────────────
    "italiano":             lambda: M.nationality.ilike("%italian%"),
    "francese":             lambda: M.nationality.ilike("%french%"),
    "brasiliano":           lambda: M.nationality.ilike("%brazil%"),
    "argentino":            lambda: M.nationality.ilike("%argentin%"),
    "spagnolo":             lambda: M.nationality.ilike("%spanish%"),
    "inglese":              lambda: M.nationality.ilike("%english%"),
    "tedesco":              lambda: M.nationality.ilike("%german%"),
    "portoghese":           lambda: M.nationality.ilike("%portugu%"),
}


# ─────────────────────────────────────────────────────────────────

def build_conditions(text: str) -> list:
    text_lower = text.lower()
    return [fn() for kw, fn in SEMANTIC_MAP.items() if kw in text_lower]


def _has_data_expr():
    return case(
        (M.xg_per90.isnot(None) | M.finishing_score.isnot(None), 0),
        else_=1,
    )


def _score_sum_expr():
    """Usa percentili se disponibili, fallback score assoluti."""
    return (
        func.coalesce(M.finishing_pct,  M.finishing_score,     0.0) +
        func.coalesce(M.creativity_pct, M.creativity_score,    0.0) +
        func.coalesce(M.defending_pct,  M.defending_obj_score, 0.0)
    )


def search_players(
    db: Session,
    text: str,
    position: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    nationality: str | None = None,
    limit: int = 20,
) -> list:
    conditions = build_conditions(text)

    if position:
        conditions.append(M.position == position)
    if min_age is not None:
        conditions.append(M.age >= min_age)
    if max_age is not None:
        conditions.append(M.age <= max_age)
    if nationality:
        conditions.append(M.nationality.ilike(f"%{nationality}%"))

    query = db.query(M)
    if conditions:
        query = query.filter(and_(*conditions))

    return (
        query
        .order_by(
            _has_data_expr().asc(),
            nulls_last(_score_sum_expr().desc()),
        )
        .limit(limit)
        .all()
    )