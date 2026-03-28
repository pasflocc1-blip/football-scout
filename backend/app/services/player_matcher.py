from sqlalchemy.orm import Session
from unidecode import unidecode
from thefuzz import fuzz
from app.models.models import ScoutingPlayer
from datetime import date
from typing import Optional, List

def get_all_players_cached(db: Session) -> List[ScoutingPlayer]:
    """Ritorna tutti i giocatori, utile per il caricamento iniziale."""
    return db.query(ScoutingPlayer).all()


def find_player_in_cache(
        name: str,
        club: str,
        all_players: List[ScoutingPlayer],
        birth_date: Optional[date] = None
) -> Optional[ScoutingPlayer]:
    """
    Versione ultra-veloce che lavora su una lista già caricata in memoria.
    """
    if not name:
        return None

    normalized_name = unidecode(name).lower().strip()
    normalized_club = unidecode(club).lower().strip() if club else ""

    # Filtro rapido per club
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
        if birth_date and player.birth_date == birth_date:
            return player

        db_name = unidecode(player.name).lower().strip()
        if normalized_name == db_name:
            return player

        score = fuzz.token_sort_ratio(normalized_name, db_name)
        if score > highest_score:
            highest_score = score
            best_match = player

    if highest_score > 85:
        return best_match

    return None

def find_player_in_db(
        db: Session,
        name: str,
        club: str,
        birth_date: Optional[date] = None
) -> Optional[ScoutingPlayer]:
    """
    Ripristinata per compatibilità con il resto del sistema.
    Esegue la ricerca classica interrogando il DB.
    """
    if not name:
        return None

    all_players = db.query(ScoutingPlayer).all()
    return find_player_in_list(name, club, all_players, birth_date)


def find_player_in_list(
        name: str,
        club: str,
        player_list: List[ScoutingPlayer],
        birth_date: Optional[date] = None
) -> Optional[ScoutingPlayer]:
    """
    Logica di matching (usata sia dalla cache che dalla ricerca standard).
    """
    normalized_name = unidecode(name).lower().strip()
    normalized_club = unidecode(club).lower().strip() if club else ""

    if normalized_club:
        candidates = [
            p for p in player_list
            if p.club and unidecode(p.club).lower().strip() == normalized_club
        ]
    else:
        candidates = player_list

    best_match = None
    highest_score = 0

    for player in candidates:
        if birth_date and player.birth_date == birth_date:
            return player

        db_name = unidecode(player.name).lower().strip()
        if normalized_name == db_name:
            return player

        score = fuzz.token_sort_ratio(normalized_name, db_name)
        if score > highest_score:
            highest_score = score
            best_match = player

    return best_match if highest_score > 85 else None