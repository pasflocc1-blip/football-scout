"""
app/services/player_matcher.py
-------------------------------
Matching intelligente tra nomi provenienti da sorgenti diverse.

Strategia a cascata (dal più affidabile al meno):
  A. Data di nascita identica          → match certo
  B. Nome esatto (case/accent-insensitive) → match certo
  C. Iniziale + cognome               → "R. Leão" ↔ "Rafael Leão"
  D. Solo cognome (se univoco nel pool)
  E. Fuzzy token_sort_ratio ≥ soglia
     - con club: soglia 85
     - senza club: soglia 88 (più selettiva su pool ampio)

Il cambio principale rispetto alla versione precedente:
  - Aggiunto step C: matching iniziale+cognome, fondamentale per
    abbinare nomi Kaggle/Football-Data ("R. Leão") con nomi
    Understat/StatsBomb ("Rafael Leão").
  - Aggiunta cache in-memory per evitare di ricaricare tutti i
    giocatori ad ogni chiamata durante un import massiccio.
"""

from sqlalchemy.orm import Session
from unidecode import unidecode
from thefuzz import fuzz
from app.models.models import ScoutingPlayer
from datetime import date
from typing import Optional, List
import re


# ── Helpers di normalizzazione ────────────────────────────────────

def _norm(s: str) -> str:
    """Rimuove accenti, lowercase, strip."""
    return unidecode(s).lower().strip()


def _last_name(name: str) -> str:
    """Ultima parola del nome normalizzato (cognome)."""
    parts = _norm(name).split()
    return parts[-1] if parts else ""


def _initial_lastname(name: str) -> str:
    """
    Genera "X. Cognome" dal nome completo.
    "Rafael Leão" → "r. leao"
    Utile per abbinare i nomi abbreviati di Kaggle/Football-Data.
    """
    parts = _norm(name).split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}"
    return _norm(name)


def _abbrev_variants(name: str) -> set:
    """
    Genera tutte le varianti abbreviate di un nome completo.
    "Rafael Leão" → {"r. leao", "rafael leao"}
    "Santiago Giménez" → {"s. gimenez", "santiago gimenez"}
    """
    n = _norm(name)
    parts = n.split()
    variants = {n}
    if len(parts) >= 2:
        variants.add(f"{parts[0][0]}. {parts[-1]}")
        variants.add(f"{parts[0][0]}.{parts[-1]}")
        # Solo cognome (usato da alcune sorgenti per nomi molto noti)
        variants.add(parts[-1])
    return variants


# ── Entry point principale ────────────────────────────────────────

def find_player_in_db(
        db: Session,
        name: str,
        club: str,
        birth_date: Optional[date] = None
) -> Optional[ScoutingPlayer]:
    """
    Cerca un giocatore nel DB con strategia a cascata.
    Se club è vuoto (es. Understat/StatsBomb) cerca su tutti i giocatori.
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
    Logica di matching su lista pre-caricata.
    """
    normalized_name = _norm(name)
    normalized_club = _norm(club) if club else ""

    # Pool: se il club è noto filtriamo, altrimenti tutti
    if normalized_club:
        candidates = [
            p for p in player_list
            if p.club and _norm(p.club) == normalized_club
        ]
        # Fallback: se il filtro club dà 0 risultati (club non ancora
        # importato) proviamo su tutto il DB con soglia più alta
        if not candidates:
            candidates = player_list
            normalized_club = ""  # tratta come no-club
    else:
        candidates = player_list

    # Soglia fuzzy: più selettiva senza club per evitare falsi positivi
    threshold = 85 if normalized_club else 88

    best_match = None
    highest_score = 0

    # Varianti abbreviate del nome in ingresso
    # (copre il caso Understat→DB: "Rafael Leão" deve abbinarsi a "R. Leão")
    name_variants = _abbrev_variants(name)

    for player in candidates:
        # A. Match per data di nascita (certo)
        if birth_date and player.birth_date == birth_date:
            return player

        db_name = _norm(player.name)

        # B. Match esatto
        if normalized_name == db_name:
            return player

        # C. Match iniziale+cognome
        # Copre: "Rafael Leão" (Understat) ↔ "R. Leão" (Kaggle/FD)
        # e anche il contrario: "R. Leão" (query) ↔ "Rafael Leão" (DB)
        db_variants = _abbrev_variants(player.name)
        if name_variants & db_variants - {normalized_name, db_name}:
            # C'è almeno una variante in comune che non è il nome originale
            inter = name_variants & db_variants
            # Verifica extra: il cognome deve essere uguale (evita falsi positivi)
            if _last_name(name) == _last_name(player.name):
                return player

        # D. Fuzzy
        score = fuzz.token_sort_ratio(normalized_name, db_name)
        # Bonus: se i cognomi coincidono esattamente aumentiamo il punteggio
        if _last_name(name) == _last_name(player.name):
            score = min(score + 8, 100)

        if score > highest_score:
            highest_score = score
            best_match = player

    return best_match if highest_score >= threshold else None


# ── Versione con cache (per import massivi) ───────────────────────

def get_all_players_cached(db: Session) -> List[ScoutingPlayer]:
    """Ritorna tutti i giocatori — usa questa per import con molte lookup."""
    return db.query(ScoutingPlayer).all()


def find_player_in_cache(
        name: str,
        club: str,
        all_players: List[ScoutingPlayer],
        birth_date: Optional[date] = None
) -> Optional[ScoutingPlayer]:
    """Versione che lavora su lista pre-caricata — più veloce per import massivi."""
    return find_player_in_list(name, club, all_players, birth_date)