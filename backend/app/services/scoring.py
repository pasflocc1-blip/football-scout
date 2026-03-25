"""
services/scoring.py
-------------------
Calcola i punteggi compositi per ogni giocatore a partire dalle stat base.
Questi score vengono salvati nel DB e usati dalla ricerca semantica.

Come aggiungere un nuovo score:
1. Aggiungi la formula in compute_scores()
2. Aggiorna il modello ScoutingPlayer (models.py)
3. Aggiorna il SEMANTIC_MAP in search.py
4. Riesegui: POST /scouting/recalculate
"""

from app.models.models import ScoutingPlayer


def _safe(val, default: float = 0.0) -> float:
    """Restituisce il valore se non è None, altrimenti il default."""
    return float(val) if val is not None else default


def compute_scores(p: ScoutingPlayer) -> dict:
    """
    Calcola heading_score, build_up_score, defensive_score
    a partire dalle stat base del giocatore.

    Ritorna un dizionario con i valori calcolati (0–100).
    """

    # ── Heading Score ────────────────────────────────────────────
    # Misura la pericolosità aerea: dominio nei duelli + fisico
    heading_score = (
        _safe(p.aerial_duels_won_pct) * 0.60 +
        _safe(p.physical) * 0.40
    )

    # ── Build-Up Score ───────────────────────────────────────────
    # Misura la capacità di far salire la squadra:
    # controllo palla + passaggi + fisico
    build_up_score = (
        _safe(p.dribbling) * 0.35 +
        _safe(p.passing)   * 0.45 +
        _safe(p.physical)  * 0.20
    )

    # ── Defensive Score ──────────────────────────────────────────
    # Misura l'efficacia difensiva: pressing + contrasto + fisico
    defensive_score = (
        _safe(p.defending) * 0.60 +
        _safe(p.physical)  * 0.25 +
        _safe(p.pace)      * 0.15
    )

    # Clamp a 100
    return {
        "heading_score":   min(round(heading_score,   1), 100.0),
        "build_up_score":  min(round(build_up_score,  1), 100.0),
        "defensive_score": min(round(defensive_score, 1), 100.0),
    }


def recalculate_all(db) -> int:
    """
    Ricalcola i punteggi per tutti i giocatori nel DB.
    Ritorna il numero di giocatori aggiornati.
    """
    players = db.query(ScoutingPlayer).all()
    updated = 0
    for p in players:
        scores = compute_scores(p)
        for key, val in scores.items():
            setattr(p, key, val)
        updated += 1

    db.commit()
    return updated
