"""
sources/understat_source.py
----------------------------
Dati xG/xA aggiornati dalla stagione in corso via understat.com
https://understat.com  — completamente gratuito, nessuna API key.

Cosa fornisce:
  - xG, xA, npxG (non-penalty xG), goals, assists, shots, key_passes
  - Minuti giocati, partite giocate
  - Calcolo automatico dei valori per90
  - Salvataggio understat_id nel DB per match deterministico futuro

Competizioni disponibili:
  "Serie_A"   → Serie A
  "EPL"       → Premier League
  "La_liga"   → La Liga
  "Bundesliga"→ Bundesliga
  "Ligue_1"   → Ligue 1
  "RFPL"      → Russian Premier League

Season: anno di inizio stagione (es. 2024 per 2024/25).

Dipendenze:
  pip install understat aiohttp

Struttura analoga a statsbomb_source.py — si aggancia al
player_matcher esistente. Se il giocatore non è nel DB viene
saltato (Understat è un enricher, non un importer di rose).

Rispetto a StatsBomb:
  ✓ Dati della stagione corrente (non storici)
  ✓ Nessun limite di partite da processare
  ✓ npxG, key_passes inclusi
  ✓ Salva understat_id → i match futuri sono 100% deterministici
"""

import asyncio
import aiohttp

from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer
from app.services.player_matcher import find_player_in_db

# ── Mappa competizioni: chiave UI → slug Understat ────────────────
LEAGUE_MAP = {
    "serie_a":        "Serie_A",
    "premier_league": "EPL",
    "la_liga":        "La_liga",
    "bundesliga":     "Bundesliga",
    "ligue_1":        "Ligue_1",
    "rfpl":           "RFPL",
}

try:
    from understat import Understat as _UnderstatLib
    _HAS_UNDERSTAT = True
except ImportError:
    _HAS_UNDERSTAT = False


async def fetch_from_understat(
    db: Session,
    league_key: str,
    season: int,
    progress_cb=None,
    stop_event=None,
) -> dict:
    """
    Scarica i dati di tutti i giocatori di una lega/stagione da
    Understat e arricchisce i record ScoutingPlayer nel DB.

    Args:
        league_key:  chiave normalizzata (es. "serie_a", "premier_league")
        season:      anno di inizio stagione (es. 2024 per 2024/25)
        progress_cb: callable(current, total) opzionale per il polling UI
        stop_event:  threading.Event per cancellazione

    Returns:
        dict con players_fetched, players_enriched, players_not_matched
    """
    if not _HAS_UNDERSTAT:
        raise RuntimeError(
            "Libreria 'understat' non installata. "
            "Aggiungi 'understat' e 'aiohttp' a requirements.txt "
            "e riavvia il container."
        )

    league_slug = LEAGUE_MAP.get(league_key)
    if not league_slug:
        available = ", ".join(LEAGUE_MAP.keys())
        raise ValueError(
            f"league_key='{league_key}' non riconosciuta. "
            f"Valori validi: {available}"
        )

    print(f"  → Understat: scarico giocatori {league_slug} {season}/{season+1}…")

    # ── 1. Fetch dati via libreria understat (asincrona) ─────────
    async with aiohttp.ClientSession() as session_http:
        understat = _UnderstatLib(session_http)
        try:
            raw_players = await understat.get_league_players(
                league_slug, season
            )
        except Exception as e:
            raise RuntimeError(
                f"Errore nel recupero dati Understat "
                f"({league_slug} {season}): {e}"
            ) from e

    print(f"  → Understat: {len(raw_players)} giocatori ricevuti")

    # ── 2. Arricchisci nel DB ────────────────────────────────────
    enriched   = 0
    not_found  = 0
    skipped    = 0

    total = len(raw_players)
    for idx, p in enumerate(raw_players):
        if stop_event and stop_event.is_set():
            print(f"  Understat: interruzione al giocatore {idx}/{total}")
            break

        # Campi restituiti da understat.get_league_players:
        # id, player_name, games, time, goals, xG, assists, xA,
        # shots, key_passes, yellow_cards, red_cards, position,
        # team_title, npg, npxG, xGChain, xGBuildup
        understat_id  = str(p.get("id", ""))
        player_name   = p.get("player_name", "")
        club          = p.get("team_title", "")
        minutes       = int(p.get("time", 0) or 0)

        if not player_name:
            skipped += 1
            continue

        # Valori raw
        xg_raw   = float(p.get("xG",   0) or 0)
        xa_raw   = float(p.get("xA",   0) or 0)
        npxg_raw = float(p.get("npxG", 0) or 0)
        goals    = int(p.get("goals",   0) or 0)
        assists  = int(p.get("assists", 0) or 0)
        shots    = int(p.get("shots",   0) or 0)
        kp       = int(p.get("key_passes", 0) or 0)
        games    = int(p.get("games",   0) or 0)

        # Per90 (minimo 1 minuto per evitare divisione per zero)
        safe_min = max(minutes, 1)
        per90    = 90.0 / safe_min
        xg_per90   = round(xg_raw   * per90, 4)
        xa_per90   = round(xa_raw   * per90, 4)
        npxg_per90 = round(npxg_raw * per90, 4)

        # ── Match per understat_id (deterministico se già salvato) ──
        player_obj = _find_by_understat_id(db, understat_id)

        if player_obj is None:
            player_name = player_name.strip().lower()
            club = club.strip().lower()
            # Fallback: fuzzy match su nome + club (player_matcher)
            player_obj = find_player_in_db(db, player_name, club)

        if player_obj is None:
            print(
                f"  → Understat: '{player_name}' ({club}) — non trovato nel DB"
            )
            not_found += 1
            continue

        # ── Aggiorna i campi ─────────────────────────────────────
        player_obj.xg_per90    = xg_per90
        player_obj.xa_per90    = xa_per90
        # npxg_per90 e understat_id sono campi nuovi (vedi migration)
        if hasattr(player_obj, "npxg_per90"):
            player_obj.npxg_per90 = npxg_per90
        if hasattr(player_obj, "understat_id"):
            player_obj.understat_id = understat_id
        # Campi aggiuntivi se presenti nel modello
        if hasattr(player_obj, "goals_season"):
            player_obj.goals_season   = goals
        if hasattr(player_obj, "assists_season"):
            player_obj.assists_season = assists
        if hasattr(player_obj, "minutes_season"):
            player_obj.minutes_season = minutes
        if hasattr(player_obj, "shots_season"):
            player_obj.shots_season   = shots

        enriched += 1
        print(
            f"  → Understat: '{player_name}' arricchito — "
            f"xG/90={xg_per90} xA/90={xa_per90} npxG/90={npxg_per90} "
            f"({minutes}′ in {games} partite)"
        )

        if progress_cb and idx % 20 == 0:
            progress_cb(idx + 1, total)

    db.commit()

    print(
        f"  → Understat: {enriched} arricchiti, "
        f"{not_found} non abbinati, {skipped} saltati"
    )

    return {
        "players_fetched":     total,
        "players_enriched":    enriched,
        "players_not_matched": not_found,
        "players_skipped":     skipped,
    }


# ── Helper: match deterministico via understat_id ────────────────

def _find_by_understat_id(
    db: Session,
    understat_id: str,
) -> "ScoutingPlayer | None":
    """
    Cerca un giocatore per understat_id salvato in precedenza.
    Ritorna None se la colonna non esiste nel modello (migration non ancora applicata).
    """
    try:
        return (
            db.query(ScoutingPlayer)
            .filter(ScoutingPlayer.understat_id == understat_id)
            .first()
        )
    except Exception:
        return None


# ── Utility: lista campionati disponibili ────────────────────────

def list_understat_leagues() -> list[dict]:
    """Ritorna la lista di competizioni/anni supportati da Understat."""
    import datetime
    current_year = datetime.date.today().year
    seasons = list(range(2014, current_year + 1))

    return [
        {
            "league_key":  k,
            "understat_slug": v,
            "seasons_available": [str(y) for y in seasons],
        }
        for k, v in LEAGUE_MAP.items()
    ]