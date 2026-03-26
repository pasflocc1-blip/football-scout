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
    """
    if not name or not club:
        return None

    # Normalizziamo nome e club in entrata (rimuove accenti e mette minuscolo)
    normalized_name = unidecode(name).lower().strip()
    normalized_club = unidecode(club).lower().strip()

    # 1. Recuperiamo tutti i giocatori associati a quel club nel nostro DB
    # Nota: per sicurezza facciamo un matching elastico anche sul club se necessario,
    # ma per performance filtriamo lato Python se i nomi dei club non matchano perfettamente.
    all_players = db.query(ScoutingPlayer).all()
    club_players = [
        p for p in all_players
        if p.club and unidecode(p.club).lower().strip() == normalized_club
    ]

    best_match = None
    highest_score = 0

    for player in club_players:
        # A. Match Sicuro: Stessa Data di Nascita
        if birth_date and player.birth_date == birth_date:
            return player

        db_name = unidecode(player.name).lower().strip()
        db_known_as = unidecode(player.known_as).lower().strip() if player.known_as else ""

        # B. Match Esatto (su nome o pseudonimo)
        if normalized_name == db_name or normalized_name == db_known_as:
            return player

        # C. Fuzzy Matching (Somiglianza)
        # thefuzz calcola un punteggio da 0 a 100 ignorando l'ordine delle parole
        score = max(
            fuzz.token_sort_ratio(normalized_name, db_name),
            fuzz.token_sort_ratio(normalized_name, db_known_as) if db_known_as else 0
        )

        if score > highest_score:
            highest_score = score
            best_match = player

    # D. Soglia di sicurezza: se i nomi sono simili almeno all'85%, assumiamo siano la stessa persona
    if highest_score >= 85:
        return best_match

    return None