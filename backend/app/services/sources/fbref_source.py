"""
sources/fbref_source.py
-----------------------
Scraping statistiche avanzate da FBref (https://fbref.com).
Alternativa gratuita a StatsBomb per xG e xA.

Cosa scarica:
  - Standard Stats per stagione/campionato (gol, assist, xG, xAG, min)
  - Arricchisce i ScoutingPlayer esistenti con xg_per90 e xa_per90

Requisiti (da aggiungere a requirements.txt se non presenti):
  requests>=2.31
  beautifulsoup4>=4.12
  pandas>=2.0
  lxml>=4.9

Attenzione:
  FBref applica rate limiting. Usa delay_seconds (default 4s) tra richieste.
  Scraping per uso personale/ricerca è tollerato; non abusare.

Campionati supportati:
  serie_a, premier_league, la_liga, bundesliga, ligue_1, champions_league
"""

import time
from io import StringIO
from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer

try:
    import requests
    from bs4 import BeautifulSoup
    import pandas as pd
    _DEPS_OK = True
except ImportError:
    _DEPS_OK = False


# FBref URL schema: /en/comps/{id}/{season}/stats/{season}-{slug}-Stats
FBREF_LEAGUES = {
    "serie_a":          {"id": 11,  "slug": "Serie-A"},
    "premier_league":   {"id": 9,   "slug": "Premier-League"},
    "la_liga":          {"id": 12,  "slug": "La-Liga"},
    "bundesliga":       {"id": 20,  "slug": "Bundesliga"},
    "ligue_1":          {"id": 13,  "slug": "Ligue-1"},
    "champions_league": {"id": 8,   "slug": "Champions-League"},
    "eredivisie":       {"id": 23,  "slug": "Eredivisie"},
    "primeira_liga":    {"id": 32,  "slug": "Primeira-Liga"},
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://fbref.com/",
}


def scrape_standard_stats(
    db: Session,
    league_key: str = "serie_a",
    season: str = "2023-2024",
    delay_seconds: float = 4.0,
) -> dict:
    """
    Scarica Standard Stats da FBref e aggiorna xg_per90/xa_per90 nel DB.

    Args:
        league_key:     chiave in FBREF_LEAGUES (es. "serie_a")
        season:         formato "YYYY-YYYY" (es. "2023-2024")
        delay_seconds:  pausa prima della richiesta HTTP (rispetta rate limit)

    Ritorna:
        dict con players_found_on_site, players_enriched_in_db, league, season
    """
    if not _DEPS_OK:
        raise ImportError(
            "Dipendenze FBref non installate.\n"
            "Aggiungi a requirements.txt:\n"
            "  requests>=2.31\n"
            "  beautifulsoup4>=4.12\n"
            "  pandas>=2.0\n"
            "  lxml>=4.9"
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
    print(f"  → FBref: scarico {url}")

    time.sleep(delay_seconds)  # rispetta il rate limit

    resp = requests.get(url, headers=_HEADERS, timeout=25)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # FBref a volte embeds la tabella in un commento HTML
    table = soup.find("table", id="stats_standard")
    if table is None:
        from bs4 import Comment
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            csoup = BeautifulSoup(comment, "lxml")
            table = csoup.find("table", id="stats_standard")
            if table:
                break

    if table is None:
        raise RuntimeError(
            "Tabella 'stats_standard' non trovata su FBref.\n"
            "FBref potrebbe aver cambiato struttura o ti sta bloccando (rate limit).\n"
            f"URL tentato: {url}"
        )

    # FBref usa MultiIndex nei header (due righe)
    df = pd.read_html(StringIO(str(table)), header=[0, 1])[0]

    # Appiattisci MultiIndex colonne
    df.columns = [
        f"{a}_{b}" if "Unnamed" not in str(a) else str(b)
        for a, b in df.columns
    ]

    # Rimuovi le righe di separazione interne (ripetono l'header)
    player_col = _find_col(df, ["Player"])
    if player_col:
        df = df[df[player_col].astype(str).str.strip() != "Player"].copy()
        df = df[df[player_col].notna()].copy()

    print(f"  → FBref: {len(df)} giocatori trovati")

    enriched = 0

    for _, row in df.iterrows():
        name = str(row.get(player_col or "Player", "")).strip()
        if not name or name in ("nan", "Player"):
            continue

        # Cerca colonne xG e xA (FBref cambia naming tra stagioni)
        xg_val = _first_float(row, [
            "Expected_xG", "xG", "Expected_npxG", "Per 90 Minutes_xG",
        ])
        xa_val = _first_float(row, [
            "Expected_xAG", "xAG", "Expected_xA", "Per 90 Minutes_xAG",
        ])
        mins = _first_float(row, [
            "Playing Time_Min", "Min", "Playing Time_MP", "90s",
        ])

        if xg_val is None and xa_val is None:
            continue

        # Calcola per90
        if mins and mins > 0:
            per90    = 90 / mins
            xg_per90 = round(xg_val * per90, 4) if xg_val is not None else None
            xa_per90 = round(xa_val * per90, 4) if xa_val is not None else None
        else:
            # Nessun dato minuti → valori già normalizzati su FBref
            xg_per90 = xg_val
            xa_per90 = xa_val

        # Match nel DB per nome (case-insensitive, partial)
        player = (
            db.query(ScoutingPlayer)
            .filter(ScoutingPlayer.name.ilike(f"%{name}%"))
            .first()
        )
        if player:
            if xg_per90 is not None:
                player.xg_per90 = xg_per90
            if xa_per90 is not None:
                player.xa_per90 = xa_per90
            enriched += 1

    db.commit()
    print(f"  → FBref: {enriched} giocatori arricchiti nel DB")

    return {
        "players_found_on_site":   len(df),
        "players_enriched_in_db":  enriched,
        "league":                  league_key,
        "season":                  season,
        "url":                     url,
    }


# ── Helpers ──────────────────────────────────────────────────────

def _find_col(df, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _first_float(row, candidates: list[str]) -> float | None:
    for col in candidates:
        if col in row.index:
            try:
                f = float(row[col])
                if f == f:  # NaN check
                    return f
            except (ValueError, TypeError):
                continue
    return None