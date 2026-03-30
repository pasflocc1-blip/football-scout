"""
services/search.py — v2.1
------------------------------------------------------------------
FIX applicati in questa versione:
  - Aggiunta keyword "scarsa efficacia di testa su calcio da fermo"
    e varianti per testa / palle inattive
  - Aggiunta keyword "scarsa in difesa" già presente ma rafforzata
    con posizioni in formato esteso (CB, LB, RB, Defence, ecc.)
    come sicurezza durante la migrazione DB posizioni
  - q diventa opzionale (solo filtri espliciti funzionano)
  - Ricerca per frasi più lunghe ha priorità (sorted by len desc)
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, case, nulls_last, func
from app.models.models import ScoutingPlayer as M


# ─────────────────────────────────────────────────────────────────
# HELPER: condizione con fallback percentile → score assoluto
# ─────────────────────────────────────────────────────────────────

def _pct_or_score(pct_col, score_col, pct_threshold: float, score_threshold: float):
    pct_attr   = getattr(M, pct_col)
    score_attr = getattr(M, score_col)
    return or_(
        pct_attr   >= pct_threshold,
        and_(pct_attr.is_(None), score_attr >= score_threshold),
    )


def _is_defender():
    """Condizione che copre sia i codici standard che i formati estesi ancora presenti nel DB."""
    return M.position.in_([
        'CB', 'LB', 'RB', 'LWB', 'RWB', 'DM',
        # formati estesi (durante migrazione DB)
        'Centre-Back', 'Left-Back', 'Right-Back', 'Defence',
        'Defender', 'Defensive Midfield', 'Difensore', 'DF',
    ])


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

    # ── Difesa — frasi positive ───────────────────────────────────
    "bravo in difesa":      lambda: _pct_or_score("defending_pct",  "defending_obj_score", 65, 58),
    "difensore solido":     lambda: _pct_or_score("defending_pct",  "defending_obj_score", 75, 65),
    "roccioso":             lambda: _pct_or_score("defending_pct",  "defending_obj_score", 80, 70),
    "difensore affidabile": lambda: _pct_or_score("defending_pct",  "defending_obj_score", 70, 62),
    "difensore":            lambda: _is_defender(),
    "difensore centrale":   lambda: M.position.in_(['CB', 'Centre-Back', 'Centre Back']),
    "terzino":              lambda: M.position.in_(['LB', 'RB', 'LWB', 'RWB', 'Left-Back', 'Right-Back']),

    # ── Difesa — frasi NEGATIVE della squadra ─────────────────────
    # Logica: se la squadra è "scarsa in difesa" → cerca bravi difensori
    "scarsa in difesa":     lambda: and_(
                                _is_defender(),
                                _pct_or_score("defending_pct", "defending_obj_score", 65, 58)
                            ),
    "problemi difensivi":   lambda: and_(
                                _is_defender(),
                                _pct_or_score("defending_pct", "defending_obj_score", 65, 58)
                            ),
    "debole in difesa":     lambda: and_(
                                _is_defender(),
                                _pct_or_score("defending_pct", "defending_obj_score", 65, 58)
                            ),
    "vulnerabile":          lambda: and_(
                                _is_defender(),
                                _pct_or_score("defending_pct", "defending_obj_score", 65, 58)
                            ),
    "poca copertura":       lambda: and_(
                                M.position.in_(['CB', 'DM', 'Centre-Back', 'Defensive Midfield']),
                                _pct_or_score("defending_pct", "defending_obj_score", 65, 58)
                            ),

    # ── Testa / duelli aerei ──────────────────────────────────────
    # La frase "scarsa efficacia di testa su calcio da fermo" → cerca giocatori bravi di testa
    "scarsa efficacia di testa su calcio da fermo": lambda: M.heading_score >= 65,
    "scarsa efficacia di testa":                    lambda: M.heading_score >= 62,
    "bravo di testa":                               lambda: M.heading_score >= 60,
    "forte fisicamente":                            lambda: M.heading_score >= 55,
    "bravo nei duelli":                             lambda: M.heading_score >= 60,
    "efficace di testa":                            lambda: M.heading_score >= 65,
    "forte di testa":                               lambda: M.heading_score >= 65,
    "duelli aerei":                                 lambda: M.aerial_duels_won_pct >= 60,
    "bravo sui calci da fermo":                     lambda: M.heading_score >= 62,
    "calci da fermo":                               lambda: M.heading_score >= 60,
    "palle inattive":                               lambda: M.heading_score >= 60,
    "corner":                                       lambda: M.heading_score >= 58,
    "colpo di testa":                               lambda: M.heading_score >= 62,

    # ── Build-up / costruzione ────────────────────────────────────
    "fa salire la squadra": lambda: _pct_or_score("buildup_pct",    "buildup_obj_score", 65, 55),
    "bravo in costruzione": lambda: _pct_or_score("buildup_pct",    "buildup_obj_score", 60, 50),
    "scarso in costruzione":lambda: _pct_or_score("buildup_pct",    "buildup_obj_score", 65, 55),
    "difficoltà in uscita": lambda: _pct_or_score("buildup_pct",    "buildup_obj_score", 60, 50),
    "difficoltà in costruzione": lambda: _pct_or_score("buildup_pct", "buildup_obj_score", 60, 50),

    # ── xG / xA diretti ───────────────────────────────────────────
    "alto xg":              lambda: M.xg_per90    >= 0.35,
    "alto xa":              lambda: M.xa_per90    >= 0.25,
    "npxg alto":            lambda: M.npxg_per90  >= 0.30,
    "xg chain":             lambda: M.xgchain_per90 >= 0.50,

    # ── Piede ─────────────────────────────────────────────────────
    "mancino":              lambda: M.preferred_foot == "Left",
    "destro":               lambda: M.preferred_foot == "Right",

    # ── Posizione ─────────────────────────────────────────────────
    "centravanti":          lambda: M.position.in_(["ST", "CF", "Centre-Forward", "Striker"]),
    "prima punta":          lambda: M.position.in_(["ST", "CF", "SS"]),
    "seconda punta":        lambda: M.position.in_(["SS", "ST"]),
    "trequartista":         lambda: M.position.in_(["AM", "CAM", "Attacking Midfield"]),
    "ala":                  lambda: M.position.in_(["LW", "RW", "Left Winger", "Right Winger"]),
    "ala sinistra":         lambda: M.position.in_(["LW", "Left Winger"]),
    "ala destra":           lambda: M.position.in_(["RW", "Right Winger"]),
    "centrocampista":       lambda: M.position.in_(["CM", "DM", "AM", "CAM", "LM", "RM",
                                                    "Central Midfield", "Defensive Midfield",
                                                    "Attacking Midfield", "Midfield"]),
    "mediano":              lambda: M.position.in_(["DM", "CM", "CDM", "Defensive Midfield"]),
    "portiere":             lambda: M.position.in_(["GK", "Goalkeeper"]),
    "attaccante":           lambda: M.position.in_(["ST", "CF", "SS", "LW", "RW",
                                                    "Centre-Forward", "Left Winger", "Right Winger"]),

    # ── Età ───────────────────────────────────────────────────────
    "giovane":              lambda: M.age <= 23,
    "under 21":             lambda: M.age <= 21,
    "under 23":             lambda: M.age <= 23,
    "under 25":             lambda: M.age <= 25,
    "esperto":              lambda: M.age >= 30,
    "veterano":             lambda: M.age >= 33,

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
    """
    Costruisce le condizioni SQLAlchemy dalla query testuale.
    Le frasi più lunghe hanno priorità (ordinate per lunghezza DESC).
    """
    if not text:
        return []
    text_lower = text.lower()
    conditions = []
    matched_ranges = []  # evita sovrapposizioni per frasi già matchate

    for kw in sorted(SEMANTIC_MAP.keys(), key=len, reverse=True):
        idx = text_lower.find(kw)
        if idx == -1:
            continue
        # Controlla che questa keyword non sia già coperta da una più lunga
        overlaps = any(start <= idx and idx + len(kw) <= end for start, end in matched_ranges)
        if overlaps:
            continue
        conditions.append(SEMANTIC_MAP[kw]())
        matched_ranges.append((idx, idx + len(kw)))

    return conditions


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
    text: str | None = None,
    position: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    nationality: str | None = None,
    limit: int = 20,
) -> list:
    """
    Ricerca giocatori combinando:
      - analisi semantica del testo libero (SEMANTIC_MAP)
      - filtri espliciti: position, min_age, max_age, nationality

    text è OPZIONALE: se assente, usa solo i filtri espliciti.
    """
    conditions = build_conditions(text) if text else []

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