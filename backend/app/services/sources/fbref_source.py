"""
sources/fbref_source.py
-----------------------
Scraping statistiche avanzate da FBref (https://fbref.com).
Alternativa gratuita a StatsBomb per xG/xA — dati stagione corrente.

Cosa scarica:
  - Standard Stats: xG, xA, npxG, gol, assist, minuti, partite
  - Progressive carries, progressive passes
  - Arricchisce ScoutingPlayer con tutti i campi della migration

Requisiti (requirements.txt):
  cloudscraper>=1.2.71
  beautifulsoup4>=4.12
  pandas>=2.0
  lxml>=4.9

FIX 403:
  cloudscraper bypassa il JS-challenge Cloudflare di FBref.
  Se continui a ricevere 403 aumenta delay_seconds (>=15) oppure
  usa una rete residenziale (non VPS/datacenter).

Campionati supportati:
  serie_a, premier_league, la_liga, bundesliga, ligue_1,
  champions_league, eredivisie, primeira_liga
"""

import time
from datetime import datetime
from io import StringIO

from sqlalchemy.orm import Session

from app.services.player_matcher import find_player_in_db
from app.models.models import ScoutingPlayer

# Dipendenze opzionali
_DEPS_OK      = False
_CLOUDSCRAPER = False

try:
    from bs4 import BeautifulSoup, Comment
    import pandas as pd
    _DEPS_OK = True
except ImportError:
    pass

try:
    import cloudscraper as _cs_mod
    _CLOUDSCRAPER = True
except ImportError:
    pass

if _DEPS_OK and not _CLOUDSCRAPER:
    try:
        import requests as _req_mod
    except ImportError:
        _DEPS_OK = False

FBREF_LEAGUES = {
    "serie_a":          {"id": 11, "slug": "Serie-A"},
    "premier_league":   {"id": 9,  "slug": "Premier-League"},
    "la_liga":          {"id": 12, "slug": "La-Liga"},
    "bundesliga":       {"id": 20, "slug": "Bundesliga"},
    "ligue_1":          {"id": 13, "slug": "Ligue-1"},
    "champions_league": {"id": 8,  "slug": "Champions-League"},
    "eredivisie":       {"id": 23, "slug": "Eredivisie"},
    "primeira_liga":    {"id": 32, "slug": "Primeira-Liga"},
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
    "Referer": "https://fbref.com/en/",
    "DNT": "1",
}


async def fetch_from_fbref(
    db: Session,
    league_key: str = "serie_a",
    season: str = "2023-2024",
    delay_seconds: float = 6.0,
    progress_cb=None,
    stop_event=None,
) -> dict:
    """
    Entry point async — compatibile con ingest.py (await fetch_from_fbref(...)).
    Delega all'implementazione sincrona scrape_standard_stats.
    """
    return scrape_standard_stats(
        db=db,
        league_key=league_key,
        season=season,
        delay_seconds=delay_seconds,
        stop_event=stop_event,
        progress_cb=progress_cb,
    )


def scrape_standard_stats(
    db: Session,
    league_key: str = "serie_a",
    season: str = "2023-2024",
    delay_seconds: float = 6.0,
    stop_event=None,
    progress_cb=None,
) -> dict:
    """
    Implementazione sincrona — scarica Standard Stats da FBref.
    Chiamata sia dall'async wrapper che dal CLI di ingest.py.
    """
    if not _DEPS_OK:
        raise ImportError(
            "Dipendenze FBref non installate.\n"
            "Aggiungi a requirements.txt:\n"
            "  cloudscraper>=1.2.71\n"
            "  beautifulsoup4>=4.12\n"
            "  pandas>=2.0\n"
            "  lxml>=4.9\n"
            "Poi riavvia il container."
        )

    if league_key not in FBREF_LEAGUES:
        raise ValueError(
            f"Campionato '{league_key}' non supportato.\n"
            f"Disponibili: {list(FBREF_LEAGUES.keys())}"
        )

    league = FBREF_LEAGUES[league_key]
    url = (
        f"https://fbref.com/en/comps/{league['id']}"
        f"/{season}/stats/{season}-{league['slug']}-Stats"
    )

    method = "cloudscraper" if _CLOUDSCRAPER else "requests (fallback)"
    print(f"  -> FBref [{method}]: {url}")

    if stop_event and stop_event.is_set():
        return _empty_result(league_key, season, url)

    time.sleep(delay_seconds)

    session = _get_session()
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        status = getattr(getattr(e, "response", None), "status_code", "?")
        raise RuntimeError(
            f"Errore HTTP {status} su FBref.\n"
            f"URL: {url}\n\n"
            f"Soluzioni:\n"
            f"  1. Installa cloudscraper:  pip install cloudscraper\n"
            f"  2. Aumenta delay_seconds (es. 10-15)\n"
            f"  3. FBref blocca richieste da IP datacenter/VPS;\n"
            f"     prova da una rete residenziale.\n"
            f"  4. Attendi qualche ora se sei stato bloccato.\n\n"
            f"Errore originale: {e}"
        ) from e

    soup = BeautifulSoup(resp.text, "lxml")

    table = soup.find("table", id="stats_standard")
    if table is None:
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            csoup = BeautifulSoup(comment, "lxml")
            table = csoup.find("table", id="stats_standard")
            if table:
                break

    if table is None:
        raise RuntimeError(
            "Tabella 'stats_standard' non trovata su FBref.\n"
            f"URL tentato: {url}"
        )

    df = pd.read_html(StringIO(str(table)), header=[0, 1])[0]

    # Appiattimento MultiIndex robusto
    flat_cols = []
    seen = {}
    for top, bot in df.columns:
        top_s = str(top).strip()
        bot_s = str(bot).strip()
        if "Unnamed" in top_s or top_s == bot_s:
            col = bot_s
        else:
            col = f"{top_s}_{bot_s}"
        if col in seen:
            seen[col] += 1
            col = f"{col}_{seen[col]}"
        else:
            seen[col] = 0
        flat_cols.append(col)
    df.columns = flat_cols

    player_col = _find_col(df, ["Player", "player"])
    if player_col:
        df = df[df[player_col].astype(str).str.strip().str.lower() != "player"].copy()
        df = df[df[player_col].notna()].copy()

    squad_col = _find_col(df, ["Squad", "squad"])

    print(f"  -> FBref: {len(df)} giocatori trovati nel dataset")

    enriched  = 0
    not_found = 0
    total     = len(df)

    for idx, (_, row) in enumerate(df.iterrows()):
        if stop_event and stop_event.is_set():
            print(f"  FBref: interruzione al giocatore {idx}/{total}")
            break

        name = str(row.get(player_col or "Player", "")).strip()
        if not name or name.lower() in ("nan", "player", ""):
            continue

        club = str(row.get(squad_col or "Squad", "")).strip() if squad_col else ""

        mins = _first_float(row, [
            "Playing Time_Min", "Min", "Playing Time_Mn", "90s", "Playing Time_90s",
        ])
        # "90s" su FBref = numero di 90 minuti, non minuti diretti
        if mins is not None and mins < 100:
            mins = mins * 90

        safe_min = max(int(mins or 0), 1)
        per90    = 90.0 / safe_min

        xg_abs   = _first_float(row, ["Expected_xG", "xG", "Per 90 Minutes_xG"])
        xa_abs   = _first_float(row, ["Expected_xAG", "xAG", "Expected_xA", "Per 90 Minutes_xAG"])
        npxg_abs = _first_float(row, ["Expected_npxG", "npxG"])

        goals_abs    = _first_int(row, ["Performance_Gls", "Gls", "Goals"])
        assists_abs  = _first_int(row, ["Performance_Ast", "Ast", "Assists"])
        shots_abs    = _first_int(row, ["Performance_Sh",  "Sh",  "Shots"])
        games_abs    = _first_int(row, ["Playing Time_MP",  "MP",  "Matches"])
        prog_p_abs   = _first_int(row, ["PrgP", "Progression_PrgP"])
        prog_c_abs   = _first_int(row, ["PrgC", "Progression_PrgC"])
        key_pass_abs = _first_int(row, ["KP", "Key_Passes", "Passing_KP"])

        xg_per90   = round(xg_abs   * per90, 4) if xg_abs   is not None else None
        xa_per90   = round(xa_abs   * per90, 4) if xa_abs   is not None else None
        npxg_per90 = round(npxg_abs * per90, 4) if npxg_abs is not None else None

        if xg_per90 is None and xa_per90 is None:
            continue

        player_obj = find_player_in_db(db, name, club)
        if player_obj is None:
            not_found += 1
            continue

        if xg_per90 is not None:
            player_obj.xg_per90 = xg_per90
        if xa_per90 is not None:
            player_obj.xa_per90 = xa_per90

        if npxg_per90 is not None and hasattr(player_obj, "npxg_per90"):
            player_obj.npxg_per90 = npxg_per90
        if prog_p_abs is not None and hasattr(player_obj, "progressive_passes"):
            player_obj.progressive_passes = prog_p_abs
        if prog_c_abs is not None and hasattr(player_obj, "progressive_carries"):
            player_obj.progressive_carries = prog_c_abs
        if key_pass_abs is not None and hasattr(player_obj, "key_passes_season"):
            player_obj.key_passes_season = key_pass_abs
        if goals_abs is not None and hasattr(player_obj, "goals_season"):
            player_obj.goals_season = goals_abs
        if assists_abs is not None and hasattr(player_obj, "assists_season"):
            player_obj.assists_season = assists_abs
        if safe_min > 1 and hasattr(player_obj, "minutes_season"):
            player_obj.minutes_season = safe_min
        if shots_abs is not None and hasattr(player_obj, "shots_season"):
            player_obj.shots_season = shots_abs
        if games_abs is not None and hasattr(player_obj, "games_season"):
            player_obj.games_season = games_abs
        if hasattr(player_obj, "last_updated_fbref"):
            player_obj.last_updated_fbref = datetime.utcnow()

        enriched += 1
        print(
            f"  -> FBref: '{name}' ({club}) — "
            f"xG/90={xg_per90} xA/90={xa_per90} npxG/90={npxg_per90} "
            f"PrgP={prog_p_abs} {safe_min}min"
        )

        if progress_cb and idx % 20 == 0:
            progress_cb(idx + 1, total)

    db.commit()
    print(f"  -> FBref: {enriched} arricchiti, {not_found} non abbinati")

    return {
        "players_found_on_site":  total,
        "players_enriched_in_db": enriched,
        "players_not_matched":    not_found,
        "league":                 league_key,
        "season":                 season,
        "url":                    url,
    }


def _get_session():
    if _CLOUDSCRAPER:
        return _cs_mod.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    import requests as _req
    s = _req.Session()
    s.headers.update(_HEADERS)
    return s


def _find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _first_float(row, candidates):
    for col in candidates:
        if col in row.index:
            try:
                val = row[col]
                f = float(str(val).replace(",", ""))
                if f == f:
                    return f
            except (ValueError, TypeError):
                continue
    return None


def _first_int(row, candidates):
    f = _first_float(row, candidates)
    return int(f) if f is not None else None


def _empty_result(league_key, season, url=""):
    return {
        "players_found_on_site":  0,
        "players_enriched_in_db": 0,
        "players_not_matched":    0,
        "league":                 league_key,
        "season":                 season,
        "url":                    url,
    }