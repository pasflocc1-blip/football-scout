"""
sources/fbref_source.py  — v3.0
---------------------------------
STRATEGIA ANTI-403 (Docker/VPS):

FBref usa Cloudflare e blocca sistematicamente le richieste da IP
datacenter/Docker. Ci sono tre approcci, in ordine di affidabilità:

  APPROCCIO A — CSV Upload (CONSIGLIATO, 100% affidabile)
    1. Vai su fbref.com con il browser
    2. Apri la pagina statistiche della lega
    3. Clicca "Share & Export" → "Get table as CSV"
    4. Incolla il CSV nell'endpoint POST /ingest/fbref/csv
    → Nessun problema di rete, funziona sempre

  APPROCCIO B — Scraping con Playwright (affidabile, richiede installazione)
    Usa un browser headless reale che bypassa Cloudflare.
    Installa: pip install playwright && playwright install chromium

  APPROCCIO C — cloudscraper + retry (parzialmente affidabile)
    Funziona talvolta da reti residenziali, quasi mai da Docker/VPS.
"""

import time
import io
from datetime import datetime
from io import StringIO

from sqlalchemy.orm import Session

from app.services.player_matcher import find_player_in_db
from app.models.models import ScoutingPlayer

# ── Dipendenze opzionali ────────────────────────────────────────────
_DEPS_OK      = False
_CLOUDSCRAPER = False
_PLAYWRIGHT   = False

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

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT = True
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


# ═══════════════════════════════════════════════════════════════════
# APPROCCIO A — Import da CSV (100% affidabile, consigliato)
# ═══════════════════════════════════════════════════════════════════

def import_from_csv_text(db: Session, csv_text: str, league_key: str = "serie_a", progress_cb=None) -> dict:
    """
    Importa le statistiche FBref da testo CSV copiato direttamente dalla pagina FBref.

    Come ottenere il CSV:
      1. Vai su https://fbref.com/en/comps/11/stats/Serie-A-Stats
      2. Clicca "Share & Export" (sotto la tabella) → "Get table as CSV"
      3. Copia tutto il testo
      4. Incollalo in DataIngestion.vue → sezione FBref CSV

    Il CSV di FBref ha alcune righe di commento (iniziano con #) da ignorare.
    """
    if not _DEPS_OK:
        raise ImportError("pandas non installato — aggiungi 'pandas>=2.0' a requirements.txt")

    import pandas as pd
    import re

    # --- PULIZIA DEL CSV (Fondamentale per il tuo file) ---
    # 1. Rimuoviamo le virgolette esterne che incapsulano le righe
    lines = csv_text.strip().split('\n')
    clean_lines = []
    for line in lines:
        l = line.strip()
        if l.startswith('"') and l.endswith('"'):
            l = l[1:-1]  # Rimuove il primo e l'ultimo carattere
        clean_lines.append(l)

    # Rimuove righe commento FBref (iniziano con #)
    lines = [l for l in csv_text.splitlines() if not l.startswith("#") and l.strip()]
    if not lines:
        raise ValueError("CSV vuoto o non valido")

    clean_csv = "\n".join(lines)

    # 3. FIX CRUCIALE: Rimuoviamo le virgole usate come separatori delle migliaia (es. "1,500" -> "1500")
    # Questo evita l'errore "Expected 25 fields, saw 26"
    csv_text = re.sub(r'(\d),(\d{3})', r'\1\2', csv_text)

    try:
        df = pd.read_csv(StringIO(clean_csv))
    except Exception as e:
        raise ValueError(f"Errore nel parsing del CSV: {e}")

    # Rimuoviamo righe di intestazione ripetute (comuni in FBref)
    if 'Player' in df.columns:
        df = df[df['Player'] != 'Player']
    else:
        raise ValueError(f"Colonna 'Player' non trovata. Colonne attuali: {list(df.columns)}")

    print(f"  -> FBref CSV: {len(df)} righe, colonne: {list(df.columns[:10])}")

    return _process_fbref_df(db, df, league_key, source="csv", progress_cb=None)


def import_from_csv_file(db: Session, filepath: str, league_key: str = "serie_a") -> dict:
    """
    Importa da file CSV salvato localmente.
    Utile se si monta il file nel container via volume Docker.
    """
    if not _DEPS_OK:
        raise ImportError("pandas non installato")

    import pandas as pd

    # Gestisce sia CSV standard che CSV con commenti FBref
    with open(filepath, encoding="utf-8", errors="replace") as f:
        lines = [l for l in f if not l.startswith("#")]

    df = pd.read_csv(StringIO("".join(lines)))
    print(f"  -> FBref file CSV: {len(df)} righe da '{filepath}'")

    return _process_fbref_df(db, df, league_key, source="csv_file")


# ═══════════════════════════════════════════════════════════════════
# APPROCCIO B — Playwright (browser headless reale)
# ═══════════════════════════════════════════════════════════════════

def scrape_with_playwright(
    db: Session,
    league_key: str = "serie_a",
    season: str = "2024-2025",
    stop_event=None,
    progress_cb=None,
) -> dict:
    """
    Usa Playwright (browser Chromium headless) per scaricare FBref.
    Bypassa Cloudflare perché usa un browser reale.

    Installazione nel container (aggiungi a Dockerfile o esegui nel backend):
        pip install playwright
        playwright install chromium --with-deps
    """
    if not _PLAYWRIGHT:
        raise ImportError(
            "Playwright non installato.\n"
            "Nel container backend esegui:\n"
            "  pip install playwright\n"
            "  playwright install chromium --with-deps\n"
            "Oppure aggiungi queste righe al Dockerfile del backend."
        )

    if not _DEPS_OK:
        raise ImportError("pandas e beautifulsoup4 non installati")

    league = FBREF_LEAGUES.get(league_key)
    if not league:
        raise ValueError(f"Lega non supportata: {league_key}")

    url = (
        f"https://fbref.com/en/comps/{league['id']}"
        f"/{season}/stats/{season}-{league['slug']}-Stats"
    )
    print(f"  -> FBref Playwright: {url}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="it-IT",
        )
        page = context.new_page()

        # Blocca risorse inutili per velocizzare
        page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda r: r.abort())

        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(3)  # attende rendering JS

        html = page.content()
        browser.close()

    import pandas as pd
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="stats_standard")
    if table is None:
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            csoup = BeautifulSoup(comment, "lxml")
            table = csoup.find("table", id="stats_standard")
            if table:
                break

    if table is None:
        raise RuntimeError(f"Tabella stats_standard non trovata su {url}")

    df = pd.read_html(StringIO(str(table)), header=[0, 1])[0]
    df = _flatten_multiindex(df)

    print(f"  -> FBref Playwright: {len(df)} giocatori")
    return _process_fbref_df(db, df, league_key, source="playwright", season=season)


# ═══════════════════════════════════════════════════════════════════
# APPROCCIO C — cloudscraper/requests (fallback, spesso 403 da Docker)
# ═══════════════════════════════════════════════════════════════════

async def fetch_from_fbref(
    db: Session,
    league_key: str = "serie_a",
    season: str = "2024-2025",
    delay_seconds: float = 8.0,
    progress_cb=None,
    stop_event=None,
) -> dict:
    """
    Entry point async — compatibile con ingest.py.
    Tenta prima con Playwright (se disponibile), poi cloudscraper.
    """
    # Prova Playwright prima — molto più affidabile da Docker
    if _PLAYWRIGHT:
        print("  -> FBref: uso Playwright (browser headless)")
        return scrape_with_playwright(
            db=db,
            league_key=league_key,
            season=season,
            stop_event=stop_event,
            progress_cb=progress_cb,
        )

    # Fallback: cloudscraper/requests
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
    season: str = "2024-2025",
    delay_seconds: float = 8.0,
    stop_event=None,
    progress_cb=None,
) -> dict:
    """
    Scraping via cloudscraper/requests.
    NOTA: spesso fallisce con 403 da Docker/VPS. Usa import_from_csv_text() invece.
    """
    if not _DEPS_OK:
        raise ImportError(
            "Dipendenze FBref non installate.\n"
            "Aggiungi a requirements.txt:\n"
            "  cloudscraper>=1.2.71\n"
            "  beautifulsoup4>=4.12\n"
            "  pandas>=2.0\n"
            "  lxml>=4.9"
        )

    league = FBREF_LEAGUES.get(league_key)
    if not league:
        raise ValueError(f"Campionato '{league_key}' non supportato.")

    url = (
        f"https://fbref.com/en/comps/{league['id']}"
        f"/{season}/stats/{season}-{league['slug']}-Stats"
    )

    method = "cloudscraper" if _CLOUDSCRAPER else "requests"
    print(f"  -> FBref [{method}]: {url}")
    print(f"  -> ATTENZIONE: da Docker questo metodo spesso fallisce con 403.")
    print(f"     Usa invece: POST /ingest/fbref/csv con il CSV copiato da fbref.com")

    if stop_event and stop_event.is_set():
        return _empty_result(league_key, season, url)

    time.sleep(delay_seconds)

    # Tenta con più User-Agent diversi
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]

    last_error = None
    for attempt, ua in enumerate(user_agents, 1):
        try:
            session = _get_session(ua)
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            break
        except Exception as e:
            last_error = e
            status = getattr(getattr(e, "response", None), "status_code", "?")
            print(f"  -> Tentativo {attempt}/{len(user_agents)} fallito: HTTP {status}")
            if attempt < len(user_agents):
                time.sleep(delay_seconds * 2)
    else:
        raise RuntimeError(
            f"Tutti i tentativi falliti (403 Forbidden).\n\n"
            f"SOLUZIONE CONSIGLIATA — Importa da CSV:\n"
            f"  1. Apri nel browser: {url}\n"
            f"  2. Scorri fino alla tabella Standard Stats\n"
            f"  3. Clicca 'Share & Export' → 'Get table as CSV'\n"
            f"  4. Copia il testo\n"
            f"  5. In Football Scout → Gestione Dati → FBref CSV → incolla e clicca Importa\n\n"
            f"Errore originale: {last_error}"
        )

    from bs4 import BeautifulSoup, Comment
    import pandas as pd

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", id="stats_standard")
    if table is None:
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            csoup = BeautifulSoup(comment, "lxml")
            table = csoup.find("table", id="stats_standard")
            if table:
                break

    if table is None:
        raise RuntimeError(f"Tabella stats_standard non trovata su {url}")

    df = pd.read_html(StringIO(str(table)), header=[0, 1])[0]
    df = _flatten_multiindex(df)

    print(f"  -> FBref: {len(df)} giocatori nel dataset")
    return _process_fbref_df(db, df, league_key, source="scraping", season=season)


# ═══════════════════════════════════════════════════════════════════
# CORE — Elaborazione DataFrame (comune a tutti gli approcci)
# ═══════════════════════════════════════════════════════════════════

def _process_fbref_df(
    db: Session,
    df,
    league_key: str,
    source: str = "csv",
    season: str = "",
    progress_cb=None
) -> dict:
    """
    Elabora un DataFrame FBref (da qualsiasi fonte) e aggiorna il DB.
    Gestisce sia il formato MultiIndex (scraping) che il formato flat (CSV export).
    """
    import pandas as pd

    # Pulizia righe header duplicate (FBref le inserisce ogni N righe)
    player_col = _find_col(df, ["Player", "player", "Giocatore"])
    if player_col:
        df = df[df[player_col].astype(str).str.strip().str.lower() != "player"].copy()
        df = df[df[player_col].notna()].copy()
        df = df[df[player_col].astype(str).str.strip() != ""].copy()

    squad_col = _find_col(df, ["Squad", "squad", "Squadra", "Tm"])

    print(f"  -> FBref ({source}): elaborazione {len(df)} giocatori")
    print(f"  -> Colonne disponibili: {list(df.columns[:15])}")

    enriched  = 0
    not_found = 0
    total     = len(df)

    for idx, (_, row) in enumerate(df.iterrows()):
        name = str(row.get(player_col or "Player", "")).strip()
        if not name or name.lower() in ("nan", "player", ""):
            continue

        club = ""
        if squad_col and squad_col in row.index:
            club = str(row.get(squad_col, "")).strip()
            if club.lower() in ("nan", ""):
                club = ""

        # Minuti — FBref può esprimere in minuti (Min) o 90s (90s)
        mins_raw = _first_float(row, [
            "Playing Time_Min", "Min", "Playing Time_Mn",
            "MP", "Playing Time_MP",
        ])
        mins_90s = _first_float(row, ["90s", "Playing Time_90s"])

        if mins_raw is not None and mins_raw >= 10:
            safe_min = max(int(mins_raw), 1)
        elif mins_90s is not None and mins_90s >= 0.1:
            safe_min = max(int(mins_90s * 90), 1)
        else:
            safe_min = 1

        per90 = 90.0 / safe_min

        # xG, xA, npxG — possono essere assoluti o già per-90 nel CSV
        xg_abs   = _first_float(row, ["Expected_xG", "xG", "xG_Expected"])
        xa_abs   = _first_float(row, ["Expected_xAG", "xAG", "Expected_xA", "xA", "xAG_Expected"])
        npxg_abs = _first_float(row, ["Expected_npxG", "npxG", "npxG_Expected"])

        # Statistiche assolute
        goals_abs    = _first_int(row, ["Performance_Gls", "Gls", "Goals", "G"])
        assists_abs  = _first_int(row, ["Performance_Ast", "Ast", "Assists", "A"])
        shots_abs    = _first_int(row, ["Performance_Sh", "Sh", "Shots"])
        games_abs    = _first_int(row, ["Playing Time_MP", "MP", "Matches", "G_1"])
        prog_p_abs   = _first_int(row, ["Progression_PrgP", "PrgP", "Prog_PrgP"])
        prog_c_abs   = _first_int(row, ["Progression_PrgC", "PrgC", "Prog_PrgC"])
        prog_r_abs   = _first_int(row, ["Progression_PrgR", "PrgR"])
        key_pass_abs = _first_int(row, ["KP", "Key Passes", "Passing_KP"])
        age_raw      = _first_int(row, ["Age", "age"])

        # Posizione — normalizzata verso i codici standard
        pos_raw = str(row.get("Pos", row.get("pos", row.get("Position", "")))).strip()
        position = _normalize_position(pos_raw) if pos_raw and pos_raw.lower() not in ("nan", "") else None

        # Conversione a per-90
        xg_per90   = round(xg_abs   * per90, 4) if xg_abs   is not None else None
        xa_per90   = round(xa_abs   * per90, 4) if xa_abs   is not None else None
        npxg_per90 = round(npxg_abs * per90, 4) if npxg_abs is not None else None

        # Se non ci sono dati xG e nemmeno progressioni, salta
        if xg_per90 is None and xa_per90 is None and prog_p_abs is None and goals_abs is None:
            continue

        player_obj = find_player_in_db(db, name, club)
        if player_obj is None:
            # Prova a trovarlo senza il club (in caso di trasferimento)
            player_obj = find_player_in_db(db, name, "")

        if player_obj is None:
            not_found += 1
            continue

        # Aggiorna solo i campi con valori validi
        if xg_per90   is not None: player_obj.xg_per90   = xg_per90
        if xa_per90   is not None: player_obj.xa_per90   = xa_per90
        if npxg_per90 is not None and hasattr(player_obj, "npxg_per90"):
            player_obj.npxg_per90 = npxg_per90
        if prog_p_abs is not None and hasattr(player_obj, "progressive_passes"):
            player_obj.progressive_passes = prog_p_abs
        if prog_c_abs is not None and hasattr(player_obj, "progressive_carries"):
            player_obj.progressive_carries = prog_c_abs
        if prog_r_abs is not None and hasattr(player_obj, "progressive_passes_received"):
            player_obj.progressive_passes_received = prog_r_abs
        if key_pass_abs is not None and hasattr(player_obj, "key_passes_season"):
            player_obj.key_passes_season = key_pass_abs
        if goals_abs  is not None and hasattr(player_obj, "goals_season"):
            player_obj.goals_season = goals_abs
        if assists_abs is not None and hasattr(player_obj, "assists_season"):
            player_obj.assists_season = assists_abs
        if safe_min > 1 and hasattr(player_obj, "minutes_season"):
            player_obj.minutes_season = safe_min
        if shots_abs  is not None and hasattr(player_obj, "shots_season"):
            player_obj.shots_season = shots_abs
        if games_abs  is not None and hasattr(player_obj, "games_season"):
            player_obj.games_season = games_abs
        # Aggiorna posizione solo se il player non l'ha già in formato standard
        if position and hasattr(player_obj, "position"):
            if not player_obj.position or len(player_obj.position) > 3:
                player_obj.position = position
        if hasattr(player_obj, "last_updated_fbref"):
            player_obj.last_updated_fbref = datetime.utcnow()

        enriched += 1

        if idx % 50 == 0:
            print(f"  -> FBref: elaborati {idx}/{total} ({enriched} arricchiti, {not_found} non trovati)")
            db.commit()

        if progress_cb and idx % 20 == 0:
            progress_cb(idx + 1, total)

    db.commit()
    print(f"  -> FBref ({source}): completato — {enriched} arricchiti, {not_found} non abbinati su {total}")

    return {
        "players_found_on_site":  total,
        "players_enriched_in_db": enriched,
        "players_not_matched":    not_found,
        "league":                 league_key,
        "season":                 season,
        "source":                 source,
    }


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _flatten_multiindex(df) -> "pd.DataFrame":
    """Appiattisce il MultiIndex delle colonne di FBref in nomi flat."""
    flat_cols = []
    seen = {}
    for col in df.columns:
        if isinstance(col, tuple):
            top, bot = str(col[0]).strip(), str(col[1]).strip()
            name = bot if "Unnamed" in top or top == bot else f"{top}_{bot}"
        else:
            name = str(col).strip()
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        flat_cols.append(name)
    df.columns = flat_cols
    return df


def _normalize_position(raw: str) -> str | None:
    """Normalizza le posizioni FBref verso i codici standard."""
    if not raw:
        return None
    # FBref usa formati tipo "MF,FW" o "DF" — prende il primo
    first = raw.split(",")[0].strip().upper()
    MAP = {
        "GK": "GK", "DF": "CB", "MF": "CM", "FW": "ST",
        "CB": "CB", "LB": "LB", "RB": "RB", "LWB": "LWB", "RWB": "RWB",
        "DM": "DM", "CM": "CM", "AM": "AM", "LM": "LM", "RM": "RM",
        "LW": "LW", "RW": "RW", "SS": "SS", "ST": "ST", "CF": "CF",
        "CDM": "DM", "CAM": "AM",
    }
    return MAP.get(first, first if len(first) <= 3 else None)


def _get_session(user_agent: str = None):
    ua = user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.google.com/",
    }
    if _CLOUDSCRAPER:
        s = _cs_mod.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        s.headers.update(headers)
        return s
    import requests
    s = requests.Session()
    s.headers.update(headers)
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
                if val is None:
                    continue
                f = float(str(val).replace(",", "").strip())
                if f == f:  # not NaN
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