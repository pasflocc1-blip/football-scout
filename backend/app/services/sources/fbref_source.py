"""
sources/fbref_source.py
-----------------------
Scraping statistiche avanzate da FBref (https://fbref.com).
Alternativa gratuita a StatsBomb per xG e xA.

Cosa scarica:
  - Standard Stats per stagione/campionato (gol, assist, xG, xAG, min)
  - Arricchisce i ScoutingPlayer esistenti con xg_per90 e xa_per90

Requisiti (da aggiungere a requirements.txt):
  requests>=2.31
  beautifulsoup4>=4.12
  pandas>=2.0
  lxml>=4.9
  cloudscraper>=1.2.71      ← NUOVO: bypass protezione Cloudflare/bot

FIX 403 Forbidden:
  FBref usa Cloudflare e rilevamento bot avanzato.
  Il modulo ora usa cloudscraper come client HTTP principale.
  Installare con:  pip install cloudscraper

  Se cloudscraper non è disponibile, si fa fallback a requests standard
  con headers realistici (può ancora ricevere 403 saltuariamente).

Attenzione:
  FBref applica rate limiting. Usa delay_seconds (default 6s) tra richieste.
  Scraping per uso personale/ricerca è tollerato; non abusare.

Campionati supportati:
  serie_a, premier_league, la_liga, bundesliga, ligue_1, champions_league
"""

import time
from io import StringIO
from sqlalchemy.orm import Session
from app.services.player_matcher import find_player_in_db
from app.models.models import ScoutingPlayer

# ── Dipendenze opzionali ──────────────────────────────────────────
_DEPS_OK       = False
_CLOUDSCRAPER  = False

try:
    from bs4 import BeautifulSoup
    import pandas as pd
    _DEPS_OK = True
except ImportError:
    pass

try:
    import cloudscraper
    _CLOUDSCRAPER = True
except ImportError:
    pass

if _DEPS_OK and not _CLOUDSCRAPER:
    try:
        import requests
    except ImportError:
        _DEPS_OK = False


# ── Configurazione campionati ─────────────────────────────────────
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

# Headers browser realistici (fallback senza cloudscraper)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language":  "en-US,en;q=0.9,it;q=0.8",
    "Accept-Encoding":  "gzip, deflate, br",
    "Connection":       "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":   "document",
    "Sec-Fetch-Mode":   "navigate",
    "Sec-Fetch-Site":   "none",
    "Sec-Fetch-User":   "?1",
    "Cache-Control":    "max-age=0",
    "Referer":          "https://fbref.com/en/",
    "DNT":              "1",
}


def _get_session():
    """
    Ritorna un session HTTP che bypassa il bot-detection di FBref.
    Priorità: cloudscraper > requests standard.
    """
    if _CLOUDSCRAPER:
        # cloudscraper gestisce automaticamente i challenge Cloudflare
        return cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )

    # Fallback: requests con headers manuali
    import requests as req
    session = req.Session()
    session.headers.update(_HEADERS)
    return session


def scrape_standard_stats(
    db: Session,
    league_key: str = "serie_a",
    season: str = "2023-2024",
    delay_seconds: float = 6.0,
    stop_event=None,   # threading.Event per cancellazione
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
            "Aggiungi a requirements.txt e reinstalla:\n"
            "  beautifulsoup4>=4.12\n"
            "  pandas>=2.0\n"
            "  lxml>=4.9\n"
            "  cloudscraper>=1.2.71    ← consigliato per evitare 403\n\n"
            "Installazione rapida:\n"
            "  pip install beautifulsoup4 pandas lxml cloudscraper"
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

    method = "cloudscraper" if _CLOUDSCRAPER else "requests (senza cloudscraper)"
    print(f"  → FBref [{method}]: scarico {url}")

    # Controlla cancellazione prima del delay (che e il punto piu lungo)
    if stop_event and stop_event.is_set():
        print("  FBref: interruzione richiesta prima del download.")
        return {"players_found_on_site": 0, "players_enriched_in_db": 0, "league": league_key, "season": season}
    time.sleep(delay_seconds)  # rispetta il rate limit di FBref

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
            f"  2. Aumenta delay_seconds (es. 10)\n"
            f"  3. FBref potrebbe bloccare richieste da IP datacenter/VPS;\n"
            f"     prova da una rete residenziale.\n"
            f"  4. Attendi qualche ora se sei stato bloccato per rate-limit.\n\n"
            f"Errore originale: {e}"
        ) from e

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
            "FBref potrebbe aver cambiato struttura della pagina.\n"
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
            per90 = 90.0 / mins
            xg_per90 = round(xg_val * per90, 4) if xg_val is not None else None
            xa_per90 = round(xa_val * per90, 4) if xa_val is not None else None
        else:
            xg_per90 = xg_val
            xa_per90 = xa_val

            # Estraiamo la squadra (fondamentale per non confondere i giocatori)
        squad_name = row.get("Squad", "") if "Squad" in df.columns else ""

        # Match intelligente nel DB
        player = find_player_in_db(db, name, squad_name)

        if player:
            # Sovrascriviamo i vecchi proxy con i VERI xG e xA
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