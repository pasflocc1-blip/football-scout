from sqlalchemy.orm import Session
from unidecode import unidecode
from thefuzz import fuzz
from app.models.models import ScoutingPlayer
from datetime import date
from typing import Optional


def find_player_in_db(
        db: Session,
        name: str,
        club: str,
        birth_date: Optional[date] = None
) -> Optional[ScoutingPlayer]:
    """
    Cerca un giocatore nel DB risolvendo i conflitti di nomi.
    Ritorna l'oggetto ScoutingPlayer se trovato, altrimenti None.

    Se club è vuoto (es. StatsBomb non fornisce il club), esegue un
    matching solo per nome su tutti i giocatori nel DB.
    """
    if not name:
        return None

    normalized_name = unidecode(name).lower().strip()
    normalized_club = unidecode(club).lower().strip() if club else ""

    all_players = db.query(ScoutingPlayer).all()

    # ── Selezione pool di candidati ──────────────────────────────
    # Se il club è noto, filtriamo per club; altrimenti cerchiamo su tutti.
    if normalized_club:
        candidates = [
            p for p in all_players
            if p.club and unidecode(p.club).lower().strip() == normalized_club
        ]
    else:
        candidates = all_players

    best_match = None
    highest_score = 0

    for player in candidates:
        # A. Match Sicuro: Stessa Data di Nascita
        if birth_date and player.birth_date == birth_date:
            return player

        db_name = unidecode(player.name).lower().strip()

        # B. Match Esatto (su nome)
        if normalized_name == db_name:
            return player

        # C. Fuzzy Matching
        score = fuzz.token_sort_ratio(normalized_name, db_name)

        if score > highest_score:
            highest_score = score
            best_match = player

    # D. Soglia di sicurezza
    # Quando cerchiamo per club usiamo 85%; senza club alziamo a 92%
    # per evitare falsi positivi su un pool più ampio.
    threshold = 85 if normalized_club else 92
    if highest_score >= threshold:
        return best_match

    return None