"""
sources/fbref_source.py  — v4.0
---------------------------------
NOVITÀ v4.0:
  - FIX colonna progressive_passes (PrgP): ora richiede esplicitamente la tabella
    "Passing" di FBref (che contiene PrgP), non solo la tabella Standard Stats.
  - La tabella Standard Stats NON contiene PrgP. La colonna si trova in:
      → fbref.com → lega → "Passing" stats (table id="stats_passing")
  - Aggiunta funzione import_from_multi_csv() per importare più tabelle insieme.
  - Aggiornata logica _process_fbref_df() con mappatura colonne ampliata.

STRATEGIA ANTI-403 (Docker/VPS):
  APPROCCIO A — CSV Upload MULTI-TABELLA (CONSIGLIATO, 100% affidabile)
    1. Vai su fbref.com con il browser
    2. Standard Stats: Share & Export → Get table as CSV  (gls, ast, xg, min, mp)
    3. Passing Stats:  Share & Export → Get table as CSV  (PrgP ← colonna mancante!)
    4. Incolla ENTRAMBI nell'endpoint POST /ingest/fbref/csv
    → La tabella Passing è fondamentale per avere progressive_passes (PrgP)

  APPROCCIO B — Playwright (affidabile, richiede installazione)
    Ora scarica ENTRAMBE le tabelle (Standard + Passing) in un'unica sessione.

  APPROCCIO C — cloudscraper/requests (parzialmente affidabile)
    Spesso fallisce con 403 da Docker/VPS.
"""

import time
import io
import re
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

# Tabelle FBref che ci interessano e i loro ID HTML
FBREF_TABLES = {
    "standard": "stats_standard",
    "passing":  "stats_passing",   # ← contiene PrgP!
    "shooting": "stats_shooting",
    "misc":     "stats_misc",
    "keeper":   "stats_keeper",
    "playing_time": "stats_playing_time",
}


# ═══════════════════════════════════════════════════════════════════
# APPROCCIO A — Import da CSV (100% affidabile, MULTI-TABELLA)
# ═══════════════════════════════════════════════════════════════════

def import_from_csv_text(
    db: Session,
    csv_text: str,
    league_key: str = "serie_a",
    progress_cb=None
) -> dict:
    """
    Importa le statistiche FBref da testo CSV (singola tabella Standard Stats).

    PER AVERE PrgP (Progressive Passes) devi usare import_from_multi_csv()
    con sia la tabella Standard sia la tabella Passing.

    Come ottenere il CSV Passing:
      1. https://fbref.com/en/comps/11/passing/Serie-A-Stats
      2. Clicca "Share & Export" → "Get table as CSV"
      3. Incolla in DataIngestion.vue → sezione FBref CSV
    """
    if not _DEPS_OK:
        raise ImportError("pandas non installato — aggiungi 'pandas>=2.0' a requirements.txt")

    df = _parse_fbref_csv(csv_text)
    print(f"  -> FBref CSV: {len(df)} righe, colonne: {list(df.columns[:10])}")
    return _process_fbref_df(db, df, league_key, source="csv", progress_cb=progress_cb)


def import_from_multi_csv(
    db: Session,
    csv_standard: str,
    csv_passing: str,
    league_key: str = "serie_a",
    csv_shooting: str = None,
    csv_misc: str = None,
    progress_cb=None,
) -> dict:
    """
    ✅ METODO CONSIGLIATO — Importa da più tabelle CSV di FBref.

    Unisce Standard Stats + Passing Stats per avere la colonna PrgP
    (progressive_passes) che mancava nella versione precedente.

    Come usarlo:
      1. Standard Stats: https://fbref.com/en/comps/11/stats/Serie-A-Stats
         → Share & Export → Get table as CSV
      2. Passing Stats:  https://fbref.com/en/comps/11/passing/Serie-A-Stats
         → Share & Export → Get table as CSV
      3. Passa entrambi a questo endpoint.

    Args:
        csv_standard: testo CSV dalla tabella Standard Stats
        csv_passing:  testo CSV dalla tabella Passing Stats (contiene PrgP!)
        csv_shooting: (opzionale) testo CSV dalla tabella Shooting Stats
        csv_misc:     (opzionale) testo CSV dalla tabella Misc Stats
    """
    if not _DEPS_OK:
        raise ImportError("pandas non installato")

    df_std  = _parse_fbref_csv(csv_standard)
    df_pass = _parse_fbref_csv(csv_passing)

    # Colonne chiave di join
    join_keys = ["Player", "Squad"]
    # Verifica che le colonne di join esistano
    for key in join_keys:
        if key not in df_std.columns:
            raise ValueError(f"Colonna '{key}' non trovata nella tabella Standard. Colonne: {list(df_std.columns[:10])}")
        if key not in df_pass.columns:
            raise ValueError(f"Colonna '{key}' non trovata nella tabella Passing. Colonne: {list(df_pass.columns[:10])}")

    # Estrai solo PrgP dalla tabella Passing (+ chiavi di join)
    prgp_col = _find_col_in_df(df_pass, ["PrgP", "Prog", "Progression_PrgP"])
    prgc_col = _find_col_in_df(df_pass, ["PrgC", "Progression_PrgC"])

    pass_cols = join_keys.copy()
    if prgp_col:
        pass_cols.append(prgp_col)
    if prgc_col:
        pass_cols.append(prgc_col)

    df_pass_slim = df_pass[pass_cols].copy()
    # Rinomina per chiarezza prima del merge
    rename_map = {}
    if prgp_col and prgp_col != "PrgP":
        rename_map[prgp_col] = "PrgP"
    if prgc_col and prgc_col != "PrgC":
        rename_map[prgc_col] = "PrgC"
    if rename_map:
        df_pass_slim.rename(columns=rename_map, inplace=True)

    # Merge su Player + Squad (left join per mantenere tutti i giocatori da Standard)
    df_merged = df_std.merge(df_pass_slim, on=join_keys, how="left", suffixes=("", "_passing"))

    print(f"  -> FBref multi-CSV: {len(df_merged)} giocatori dopo merge")
    print(f"  -> PrgP trovati: {df_merged['PrgP'].notna().sum() if 'PrgP' in df_merged.columns else 0}")

    # Opzionale: merge con Shooting
    if csv_shooting:
        df_sh = _parse_fbref_csv(csv_shooting)
        sh_cols = [c for c in join_keys if c in df_sh.columns]
        extra_sh = [c for c in ["Sh", "SoT", "Dist", "G/Sh", "G/SoT"] if c in df_sh.columns]
        if sh_cols and extra_sh:
            df_sh_slim = df_sh[sh_cols + extra_sh].copy()
            df_merged = df_merged.merge(df_sh_slim, on=sh_cols, how="left", suffixes=("", "_shooting"))

    # Opzionale: merge con Misc
    if csv_misc:
        df_misc = _parse_fbref_csv(csv_misc)
        misc_cols = [c for c in join_keys if c in df_misc.columns]
        extra_misc = [c for c in ["Int", "TklW", "Fls", "Fld", "Crs", "Off"] if c in df_misc.columns]
        if misc_cols and extra_misc:
            df_misc_slim = df_misc[misc_cols + extra_misc].copy()
            df_merged = df_merged.merge(df_misc_slim, on=misc_cols, how="left", suffixes=("", "_misc"))

    return _process_fbref_df(db, df_merged, league_key, source="multi_csv", progress_cb=progress_cb)


def import_from_csv_file(db: Session, filepath: str, league_key: str = "serie_a") -> dict:
    """Importa da file CSV salvato localmente."""
    if not _DEPS_OK:
        raise ImportError("pandas non installato")

    import pandas as pd

    with open(filepath, encoding="utf-8", errors="replace") as f:
        lines = [l for l in f if not l.startswith("#")]

    df = pd.read_csv(StringIO("".join(lines)))
    print(f"  -> FBref file CSV: {len(df)} righe da '{filepath}'")
    return _process_fbref_df(db, df, league_key, source="csv_file")


# ═══════════════════════════════════════════════════════════════════
# APPROCCIO B — Playwright (browser headless reale, v4.0 multi-tabella)
# ═══════════════════════════════════════════════════════════════════

def scrape_with_playwright(
    db: Session,
    league_key: str = "serie_a",
    season: str = "2024-2025",
    stop_event=None,
    progress_cb=None,
) -> dict:
    """
    Usa Playwright per scaricare ENTRAMBE le tabelle Standard e Passing.
    Ora restituisce anche progressive_passes (PrgP).

    Installazione:
        pip install playwright && playwright install chromium --with-deps
    """
    if not _PLAYWRIGHT:
        raise ImportError(
            "Playwright non installato.\n"
            "Esegui: pip install playwright && playwright install chromium --with-deps"
        )
    if not _DEPS_OK:
        raise ImportError("pandas e beautifulsoup4 non installati")

    league = FBREF_LEAGUES.get(league_key)
    if not league:
        raise ValueError(f"Lega non supportata: {league_key}")

    # URL tabella Standard Stats
    url_standard = (
        f"https://fbref.com/en/comps/{league['id']}"
        f"/{season}/stats/{season}-{league['slug']}-Stats"
    )
    # URL tabella Passing Stats (contiene PrgP)
    url_passing = (
        f"https://fbref.com/en/comps/{league['id']}"
        f"/{season}/passing/{season}-{league['slug']}-Stats"
    )

    dfs = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="it-IT",
        )
        page = context.new_page()
        page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda r: r.abort())

        for table_key, url, table_id in [
            ("standard", url_standard, "stats_standard"),
            ("passing",  url_passing,  "stats_passing"),
        ]:
            if stop_event and stop_event.is_set():
                break

            print(f"  -> FBref Playwright [{table_key}]: {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(3)

            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            table = soup.find("table", id=table_id)
            if table is None:
                for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                    csoup = BeautifulSoup(comment, "lxml")
                    table = csoup.find("table", id=table_id)
                    if table:
                        break

            if table is None:
                print(f"  -> ATTENZIONE: tabella {table_id} non trovata su {url}")
                continue

            df = pd.read_html(StringIO(str(table)), header=[0, 1])[0]
            df = _flatten_multiindex(df)
            dfs[table_key] = df
            print(f"  -> {table_key}: {len(df)} righe, colonne: {list(df.columns[:8])}")

            time.sleep(2)  # pausa cortesia tra le richieste

        browser.close()

    if "standard" not in dfs:
        raise RuntimeError("Tabella Standard Stats non trovata — impossibile procedere")

    df_final = dfs["standard"]

    # Merge con Passing per avere PrgP
    if "passing" in dfs:
        df_pass = dfs["passing"]
        prgp_col = _find_col_in_df(df_pass, ["PrgP", "Prog_PrgP", "Progression_PrgP"])
        prgc_col = _find_col_in_df(df_pass, ["PrgC", "Prog_PrgC", "Progression_PrgC"])
        join_keys = [c for c in ["Player", "Squad"] if c in df_pass.columns and c in df_final.columns]

        if join_keys:
            pass_cols = join_keys.copy()
            if prgp_col:
                pass_cols.append(prgp_col)
            if prgc_col:
                pass_cols.append(prgc_col)
            df_pass_slim = df_pass[pass_cols].copy()
            df_final = df_final.merge(df_pass_slim, on=join_keys, how="left", suffixes=("", "_passing"))
            print(f"  -> Merge Standard+Passing OK — PrgP: {df_final[prgp_col].notna().sum() if prgp_col else 0}")

    return _process_fbref_df(db, df_final, league_key, source="playwright", season=season)


# ═══════════════════════════════════════════════════════════════════
# APPROCCIO C — cloudscraper/requests (fallback)
# ═══════════════════════════════════════════════════════════════════

async def fetch_from_fbref(
    db: Session,
    league_key: str = "serie_a",
    season: str = "2024-2025",
    delay_seconds: float = 8.0,
    progress_cb=None,
    stop_event=None,
) -> dict:
    """Entry point async — compatibile con ingest.py."""
    if _PLAYWRIGHT:
        print("  -> FBref: uso Playwright (browser headless)")
        return scrape_with_playwright(
            db=db, league_key=league_key, season=season,
            stop_event=stop_event, progress_cb=progress_cb,
        )
    return scrape_standard_stats(
        db=db, league_key=league_key, season=season,
        delay_seconds=delay_seconds, stop_event=stop_event, progress_cb=progress_cb,
    )


def scrape_standard_stats(
    db: Session,
    league_key: str = "serie_a",
    season: str = "2024-2025",
    delay_seconds: float = 8.0,
    stop_event=None,
    progress_cb=None,
) -> dict:
    """Scraping via cloudscraper/requests. NOTA: spesso 403 da Docker."""
    if not _DEPS_OK:
        raise ImportError("Dipendenze FBref non installate.")

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

    if stop_event and stop_event.is_set():
        return _empty_result(league_key, season, url)

    time.sleep(delay_seconds)

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
            f"SOLUZIONE CONSIGLIATA:\n"
            f"  1. Standard: {url}\n"
            f"     Share & Export → Get table as CSV\n"
            f"  2. Passing: {url.replace('/stats/', '/passing/')}\n"
            f"     Share & Export → Get table as CSV\n"
            f"  3. Usa import_from_multi_csv() con entrambi i CSV\n\n"
            f"Errore originale: {last_error}"
        )

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
    v4.0: mappatura colonne ampliata per supportare tabella Passing (PrgP).
    """
    import pandas as pd

    player_col = _find_col_in_df(df, ["Player", "player", "Giocatore"])
    if player_col:
        df = df[df[player_col].astype(str).str.strip().str.lower() != "player"].copy()
        df = df[df[player_col].notna()].copy()
        df = df[df[player_col].astype(str).str.strip() != ""].copy()

    squad_col = _find_col_in_df(df, ["Squad", "squad", "Squadra", "Tm"])

    print(f"  -> FBref ({source}): elaborazione {len(df)} giocatori")
    print(f"  -> Colonne disponibili: {list(df.columns[:20])}")

    # Log colonne di progressione trovate (debug)
    prgp_found = _find_col_in_df(df, ["PrgP", "Progression_PrgP", "Prog_PrgP"])
    prgc_found = _find_col_in_df(df, ["PrgC", "Progression_PrgC", "Prog_PrgC"])
    prgr_found = _find_col_in_df(df, ["PrgR", "Progression_PrgR"])
    print(f"  -> Colonne progressione: PrgP={prgp_found}, PrgC={prgc_found}, PrgR={prgr_found}")

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

        mins_raw = _first_float(row, [
            "Playing Time_Min", "Min", "Playing Time_Mn", "MP", "Playing Time_MP",
        ])
        mins_90s = _first_float(row, ["90s", "Playing Time_90s"])

        if mins_raw is not None and mins_raw >= 10:
            safe_min = max(int(mins_raw), 1)
        elif mins_90s is not None and mins_90s >= 0.1:
            safe_min = max(int(mins_90s * 90), 1)
        else:
            safe_min = 1

        per90 = 90.0 / safe_min

        xg_abs   = _first_float(row, ["Expected_xG", "xG", "xG_Expected"])
        xa_abs   = _first_float(row, ["Expected_xAG", "xAG", "Expected_xA", "xA", "xAG_Expected"])
        npxg_abs = _first_float(row, ["Expected_npxG", "npxG", "npxG_Expected"])

        goals_abs    = _first_int(row, ["Performance_Gls", "Gls", "Goals", "G"])
        assists_abs  = _first_int(row, ["Performance_Ast", "Ast", "Assists", "A"])
        shots_abs    = _first_int(row, ["Performance_Sh", "Sh", "Shots"])
        games_abs    = _first_int(row, ["Playing Time_MP", "MP", "Matches", "G_1"])
        # ✅ v4.0: mappatura PrgP ampliata per tabella Passing
        prog_p_abs   = _first_int(row, [
            "PrgP",                   # Colonna diretta tabella Passing
            "Progression_PrgP",       # MultiIndex flattened scraping
            "Prog_PrgP",              # Variante
            "Progressive Passes",     # Nome esteso
        ])
        prog_c_abs   = _first_int(row, [
            "PrgC",
            "Progression_PrgC",
            "Prog_PrgC",
            "Progressive Carries",
        ])
        prog_r_abs   = _first_int(row, [
            "PrgR",
            "Progression_PrgR",
            "Progressive Passes Rec",
        ])
        key_pass_abs = _first_int(row, ["KP", "Key Passes", "Passing_KP"])
        age_raw      = _first_int(row, ["Age", "age"])

        pos_raw = str(row.get("Pos", row.get("pos", row.get("Position", "")))).strip()
        position = _normalize_position(pos_raw) if pos_raw and pos_raw.lower() not in ("nan", "") else None

        xg_per90   = round(xg_abs   * per90, 4) if xg_abs   is not None else None
        xa_per90   = round(xa_abs   * per90, 4) if xa_abs   is not None else None
        npxg_per90 = round(npxg_abs * per90, 4) if npxg_abs is not None else None

        if xg_per90 is None and xa_per90 is None and prog_p_abs is None and goals_abs is None:
            continue

        player_obj = find_player_in_db(db, name, club)
        if player_obj is None:
            player_obj = find_player_in_db(db, name, "")

        if player_obj is None:
            not_found += 1
            continue

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

def _parse_fbref_csv(csv_text: str) -> "pd.DataFrame":
    """
    Pulisce e parsifica un CSV di FBref.
    Gestisce: righe commento (#), header ripetuti, virgole migliaia.
    """
    import pandas as pd

    # Rimuovi righe commento FBref
    lines = [l for l in csv_text.splitlines() if not l.startswith("#") and l.strip()]
    if not lines:
        raise ValueError("CSV vuoto o non valido")

    # Fix virgole come separatori delle migliaia (es. "1,500" → "1500")
    clean = re.sub(r'(\d),(\d{3})', r'\1\2', "\n".join(lines))

    try:
        df = pd.read_csv(StringIO(clean))
    except Exception as e:
        raise ValueError(f"Errore nel parsing del CSV: {e}")

    # Rimuovi righe header ripetute (FBref le inserisce ogni N righe)
    if "Player" in df.columns:
        df = df[df["Player"].astype(str).str.strip() != "Player"].copy()
    elif "player" in df.columns:
        df = df[df["player"].astype(str).str.strip() != "player"].copy()

    df = df.reset_index(drop=True)
    return df


def _flatten_multiindex(df) -> "pd.DataFrame":
    """Appiattisce il MultiIndex delle colonne FBref in nomi flat."""
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
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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


def _find_col_in_df(df, candidates):
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