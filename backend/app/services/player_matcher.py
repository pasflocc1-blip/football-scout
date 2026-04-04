"""
app/services/player_matcher.py
-------------------------------
Matching intelligente tra nomi da sorgenti diverse.

Strategia a cascata:
  A. Data di nascita identica               → match certo
  B. Nome esatto (accent/case insensitive)  → match certo
  C. Variante abbreviata + cognome coincide → "R. Leão" ↔ "Rafael Leão"
  D. Alias noti (es. "Mbappe-Lottin" → "Mbappé")
  E. Fuzzy token_sort_ratio ≥ soglia (85 con club, 88 senza)

Rispetto alle versioni precedenti:
  - Aggiunto ALIASES per nomi con trattino/soprannomi
  - _last_name_variants confronta su varianti, non solo sul nome originale
  - Normalizzazione con e senza trattino per nomi composti
  - Lookup su lista cached (1 query DB per import massivo)
"""

from sqlalchemy.orm import Session
from unidecode import unidecode
from thefuzz import fuzz
from app.models.models import ScoutingPlayer
from datetime import date
from typing import Optional, List

# ── Alias nomi noti ────────────────────────────────────────────────
# Chiave: nome sorgente normalizzato (understat/statsbomb)
# Valore: varianti da cercare nel DB
ALIASES: dict = {
    "kylian mbappe-lottin":    ["kylian mbappe", "mbappe"],
    "kylian mbappe lottin":    ["kylian mbappe", "mbappe"],
    "alisson becker":          ["alisson"],
    "alexis mac allister":     ["mac allister", "alexis mac allister"],
    "raul":                    ["raul jimenez", "raul"],
    "rui patricio":            ["rui patricio"],
}

_PARTICLES = {"van","de","dos","da","di","del","della","le","la",
              "von","el","al","ben","bin","jr","ii","iii"}


def _norm(s: str) -> str:
    return unidecode(s).lower().strip()


def _last_name_variants(name: str) -> set:
    """Tutte le possibili forme del cognome, incluse varianti da ALIASES."""
    n      = _norm(name)
    n_dash = n.replace("-", " ")
    lasts  = set()
    for variant in [n, n_dash]:
        parts = [t for t in variant.split() if t not in _PARTICLES]
        if parts:
            lasts.add(parts[-1])
    for src, targets in ALIASES.items():
        if n == src or n_dash == src:
            for t in targets:
                parts = [x for x in _norm(t).split() if x not in _PARTICLES]
                if parts:
                    lasts.add(parts[-1])
    return lasts


def _abbrev_variants(name: str) -> set:
    """
    Varianti abbreviate + alias.
    "Kylian Mbappe-Lottin" → {... "kylian mbappe", "mbappe", "k. mbappe", ...}
    "Rafael Leão"          → {"rafael leao", "r. leao", "leao"}
    """
    n      = _norm(name)
    n_dash = n.replace("-", " ")
    variants = {n, n_dash}

    parts = n_dash.split()
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        variants.add(f"{first[0]}. {last}")
        variants.add(f"{first[0]}.{last}")
        variants.add(last)
        if "-" in n:
            last_orig = n.split()[-1]
            variants.add(f"{first[0]}. {last_orig}")
            variants.add(last_orig)

    for src, targets in ALIASES.items():
        if n == src or n_dash == src:
            for t in targets:
                variants.add(_norm(t))

    return variants


def find_player_in_db(db, name: str, club: str = '', season: str = None):
    """
    Trova un giocatore nel DB per nome (e opzionalmente club e stagione).

    Con season_club aggiunto a ScoutingPlayer, filtriamo anche per stagione
    se specificata — evita di restituire lo stesso giocatore di stagioni diverse.

    Priorità ricerca:
      1. Nome esatto + club esatto + season  (match perfetto)
      2. Nome esatto + club esatto
      3. Nome ILIKE + club parziale
      4. Nome ILIKE solo
    """
    from app.models.models import ScoutingPlayer

    name_clean = name.strip()
    club_clean = club.strip() if club else ''

    # 1. Match esatto con season
    if season:
        q = db.query(ScoutingPlayer).filter(
            ScoutingPlayer.name == name_clean,
            ScoutingPlayer.season_club == season,
        )
        if club_clean:
            q = q.filter(ScoutingPlayer.club.ilike(f'%{club_clean}%'))
        p = q.first()
        if p:
            return p

    # 2. Nome esatto + club esatto (stagione più recente)
    if club_clean:
        p = db.query(ScoutingPlayer).filter(
            ScoutingPlayer.name == name_clean,
            ScoutingPlayer.club.ilike(f'%{club_clean}%'),
        ).order_by(ScoutingPlayer.last_updated_sofascore.desc()).first()
        if p:
            return p

    # 3. Nome esatto (qualsiasi club) — stagione più recente
    p = db.query(ScoutingPlayer).filter(
        ScoutingPlayer.name == name_clean,
    ).order_by(ScoutingPlayer.last_updated_sofascore.desc()).first()
    if p:
        return p

    # 4. ILIKE fallback
    q = db.query(ScoutingPlayer).filter(
        ScoutingPlayer.name.ilike(f'%{name_clean}%'),
    )
    if club_clean:
        q = q.filter(ScoutingPlayer.club.ilike(f'%{club_clean}%'))
    return q.order_by(ScoutingPlayer.last_updated_sofascore.desc()).first()


def find_player_in_list(
        name: str,
        club: str,
        player_list: List[ScoutingPlayer],
        birth_date: Optional[date] = None
) -> Optional[ScoutingPlayer]:

    normalized_name = _norm(name)
    normalized_club = _norm(club) if club else ""

    if normalized_club:
        candidates = [
            p for p in player_list
            if p.club and _norm(p.club) == normalized_club
        ]
        if not candidates:
            candidates = player_list
            normalized_club = ""
    else:
        candidates = player_list

    threshold    = 85 if normalized_club else 88
    best_match   = None
    highest_score = 0
    name_variants = _abbrev_variants(name)
    name_lasts    = _last_name_variants(name)

    for player in candidates:
        # A. Data di nascita
        if birth_date and player.birth_date == birth_date:
            return player

        db_name = _norm(player.name)

        # B. Esatto
        if normalized_name == db_name:
            return player

        # C+D. Variante abbreviata / alias con cognome coincidente
        db_variants = _abbrev_variants(player.name)
        db_lasts    = _last_name_variants(player.name)
        inter = name_variants & db_variants - {normalized_name, db_name}
        if inter and bool(name_lasts & db_lasts):
            return player

        # E. Fuzzy con bonus cognome
        score = fuzz.token_sort_ratio(normalized_name, db_name)
        if name_lasts & db_lasts:
            score = min(score + 8, 100)
        if score > highest_score:
            highest_score = score
            best_match = player

    return best_match if highest_score >= threshold else None


def get_all_players_cached(db: Session) -> List[ScoutingPlayer]:
    return db.query(ScoutingPlayer).all()


def find_player_in_cache(
        name: str,
        club: str,
        all_players: List[ScoutingPlayer],
        birth_date: Optional[date] = None
) -> Optional[ScoutingPlayer]:
    return find_player_in_list(name, club, all_players, birth_date)