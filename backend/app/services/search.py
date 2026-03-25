from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.models import ScoutingPlayer as M


# ── Mappa semantica: keyword → condizione SQLAlchemy ─────────────
# NON usiamo f-string (vulnerabili a SQL injection).
# Usiamo l'ORM che parametrizza automaticamente le query.
SEMANTIC_MAP: dict = {
    # Fisico
    "bravo di testa":       lambda: M.heading_score > 75,
    "forte fisicamente":    lambda: M.physical > 80,
    "veloce":               lambda: M.pace > 80,
    "resistente":           lambda: M.physical > 75,

    # Tecnica
    "bravo col pallone":    lambda: M.dribbling > 78,
    "ottimo passatore":     lambda: M.passing > 80,
    "tiratore":             lambda: M.shooting > 80,

    # Ruolo tattico
    "fa salire la squadra": lambda: M.build_up_score > 70,
    "difensore solido":     lambda: M.defensive_score > 75,
    "bravo in difesa":      lambda: M.defending > 78,

    # Piede
    "mancino":              lambda: M.preferred_foot == "Left",
    "destro":               lambda: M.preferred_foot == "Right",

    # Posizione
    "centravanti":          lambda: M.position == "ST",
    "trequartista":         lambda: M.position == "AM",
    "ala":                  lambda: M.position.in_(["LW", "RW"]),
    "terzino":              lambda: M.position.in_(["LB", "RB"]),
    "centrocampista":       lambda: M.position.in_(["CM", "DM", "AM"]),
    "difensore centrale":   lambda: M.position == "CB",
    "portiere":             lambda: M.position == "GK",

    # Età
    "giovane":              lambda: M.age <= 23,
    "under 21":             lambda: M.age <= 21,
    "under 25":             lambda: M.age <= 25,
    "esperto":              lambda: M.age >= 30,

    # xG / statistiche avanzate
    "realizzatore":         lambda: M.xg_per90 > 0.4,
    "assist man":           lambda: M.xa_per90 > 0.3,

    # Aggiunte
    "tecnico":        lambda: M.dribbling > 82,
    "forte in area":  lambda: M.shooting > 78,
    "under 23":       lambda: M.age <= 23,
    "italiano":       lambda: M.nationality.ilike("%italian%")
}


def build_conditions(text: str) -> list:
    """Converte testo libero in lista di condizioni SQLAlchemy."""
    text_lower = text.lower()
    conditions = []
    for keyword, condition_fn in SEMANTIC_MAP.items():
        if keyword in text_lower:
            conditions.append(condition_fn())
    return conditions


def search_players(
    db: Session,
    text: str,
    position: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    nationality: str | None = None,
    limit: int = 20,
) -> list:
    """
    Ricerca semantica + filtri strutturati opzionali.
    Tutti i parametri sono sicuri: usa ORM, nessuna f-string.
    """
    conditions = build_conditions(text)

    # Filtri strutturati aggiuntivi
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

    # Ordina per score complessivo decrescente
    return (
        query
        .order_by(
            (M.heading_score + M.build_up_score + M.defensive_score).desc()
        )
        .limit(limit)
        .all()
    )
