"""
sources/understat_source.py — Fase 1 pipeline oggettivo
-------------------------------------------------------
Miglioramenti rispetto alla versione precedente:
  - Usa find_player_in_list su lista pre-caricata (1 query DB invece di N)
  - Passa il club di Understat al matcher → migliora abbinamenti
  - Il nuovo player_matcher gestisce "R. Leão" ↔ "Rafael Leão"
  - Salva tutte le statistiche raw stagionali
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer
from app.services.player_matcher import (
    get_all_players_cached,
    find_player_in_list,
    find_player_in_db,
)

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
    import aiohttp
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

    if not _HAS_UNDERSTAT:
        raise RuntimeError(
            "Libreria 'understat' non installata.\n"
            "Aggiungi a requirements.txt: understat, aiohttp"
        )

    league_slug = LEAGUE_MAP.get(league_key)
    if not league_slug:
        raise ValueError(
            f"league_key='{league_key}' non riconosciuta. "
            f"Validi: {list(LEAGUE_MAP)}"
        )

    print(f"  Understat: scarico {league_slug} {season}/{season+1}…")

    async with aiohttp.ClientSession() as session_http:
        understat = _UnderstatLib(session_http)
        try:
            raw_players = await understat.get_league_players(league_slug, season)
        except Exception as e:
            raise RuntimeError(
                f"Errore Understat ({league_slug} {season}): {e}"
            ) from e

    print(f"  Understat: {len(raw_players)} giocatori ricevuti")

    # Carica tutti i giocatori UNA VOLTA SOLA invece di fare
    # una query separata per ogni giocatore (molto più veloce)
    all_players = get_all_players_cached(db)
    print(f"  Understat: {len(all_players)} giocatori nel DB da abbinare")

    enriched  = 0
    not_found = 0
    skipped   = 0
    total     = len(raw_players)

    for idx, p in enumerate(raw_players):
        if stop_event and stop_event.is_set():
            print(f"  Understat: interruzione al giocatore {idx}/{total}")
            break

        understat_id = str(p.get("id", ""))
        player_name  = p.get("player_name", "")
        club         = p.get("team_title", "")   # es. "AC Milan"
        minutes      = int(p.get("time", 0) or 0)

        if not player_name:
            skipped += 1
            continue

        # Valori raw stagione
        xg_raw       = float(p.get("xG",        0) or 0)
        xa_raw       = float(p.get("xA",        0) or 0)
        npxg_raw     = float(p.get("npxG",      0) or 0)
        goals        = int(p.get("goals",       0) or 0)
        assists      = int(p.get("assists",     0) or 0)
        shots        = int(p.get("shots",       0) or 0)
        key_pass     = int(p.get("key_passes",  0) or 0)
        games        = int(p.get("games",       0) or 0)
        xgchain_raw  = float(p.get("xGChain",   0) or 0)
        xgbuild_raw  = float(p.get("xGBuildup", 0) or 0)

        # Per90
        safe_min      = max(minutes, 1)
        per90         = 90.0 / safe_min
        xg_per90      = round(xg_raw      * per90, 4)
        xa_per90      = round(xa_raw      * per90, 4)
        npxg_per90    = round(npxg_raw    * per90, 4)
        xgchain_per90 = round(xgchain_raw * per90, 4)
        xgbuild_per90 = round(xgbuild_raw * per90, 4)

        # Match deterministico per understat_id → fuzzy+iniziale su lista cached
        player_obj = _find_by_understat_id_in_list(all_players, understat_id)
        if player_obj is None:
            # Passa il club: Understat usa nomi completi ("AC Milan"),
            # il matcher farà abbinamento anche con abbreviazioni ("R. Leão")
            player_obj = find_player_in_list(
                player_name, club, all_players
            )

        if player_obj is None:
            if idx < 20 or idx % 50 == 0:  # log solo i primi + ogni 50
                print(f"  Understat: '{player_name}' ({club}) — non trovato")
            not_found += 1
            continue

        # Aggiorna
        player_obj.understat_id      = understat_id
        player_obj.xg_per90          = xg_per90
        player_obj.xa_per90          = xa_per90
        player_obj.npxg_per90        = npxg_per90
        player_obj.xgchain_per90     = xgchain_per90
        player_obj.xgbuildup_per90   = xgbuild_per90
        player_obj.goals_season      = goals
        player_obj.assists_season    = assists
        player_obj.minutes_season    = minutes
        player_obj.shots_season      = shots
        player_obj.key_passes_season = key_pass
        player_obj.games_season      = games
        player_obj.last_updated_understat = datetime.utcnow()

        enriched += 1

        if progress_cb and idx % 20 == 0:
            progress_cb(idx + 1, total)

    db.commit()
    print(
        f"  Understat: {enriched} arricchiti, "
        f"{not_found} non abbinati, {skipped} saltati"
    )
    if not_found > enriched:
        print(
            f"  Understat: ATTENZIONE — più non abbinati che abbinati. "
            f"Il DB potrebbe avere nomi in formato abbreviato (es. 'R. Leão'). "
            f"Assicurarsi di aver importato Football-Data prima di Understat."
        )

    return {
        "players_fetched":     total,
        "players_enriched":    enriched,
        "players_not_matched": not_found,
        "players_skipped":     skipped,
    }


def _find_by_understat_id_in_list(
    all_players: list,
    understat_id: str,
) -> Optional[ScoutingPlayer]:
    """Lookup su lista in-memory per understat_id — O(n) ma evita query DB."""
    for p in all_players:
        uid = getattr(p, "understat_id", None)
        if uid and uid == understat_id:
            return p
    return None


def list_understat_leagues() -> list[dict]:
    import datetime
    current_year = datetime.date.today().year
    return [
        {
            "league_key":         k,
            "understat_slug":     v,
            "seasons_available":  [str(y) for y in range(2014, current_year + 1)],
        }
        for k, v in LEAGUE_MAP.items()
    ]