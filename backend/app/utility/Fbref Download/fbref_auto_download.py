#!/usr/bin/env python3
"""
fbref_auto_download.py
======================
Script Python standalone per scaricare automaticamente le statistiche
FBref senza aprire il browser manualmente.

Usa Playwright (browser Chromium headless) che bypassa Cloudflare
perché simula un browser reale con fingerprint autentico.

UTILIZZO:
  # Dalla tua macchina Mac (NON dal container Docker):
  pip install playwright
  playwright install chromium

  # Scarica Serie A 2024-2025
  python fbref_auto_download.py --league serie_a --season 2024-2025

  # Scarica e carica direttamente nel backend
  python fbref_auto_download.py --league serie_a --season 2024-2025 --upload

  # Scarica Premier League
  python fbref_auto_download.py --league premier_league --season 2024-2025

LEGHE SUPPORTATE:
  serie_a, premier_league, la_liga, bundesliga, ligue_1,
  champions_league, eredivisie, primeira_liga

OUTPUT:
  File CSV salvati nella cartella ./fbref_output/
  Pronti per essere caricati via POST /ingest/fbref/csv-upload
"""

import argparse
import time
import os
import sys
from pathlib import Path

# ── Mappa leghe ─────────────────────────────────────────────────────
LEAGUES = {
    "serie_a":          {"id": 11, "slug": "Serie-A",        "name": "Serie A"},
    "premier_league":   {"id": 9,  "slug": "Premier-League", "name": "Premier League"},
    "la_liga":          {"id": 12, "slug": "La-Liga",         "name": "La Liga"},
    "bundesliga":       {"id": 20, "slug": "Bundesliga",      "name": "Bundesliga"},
    "ligue_1":          {"id": 13, "slug": "Ligue-1",         "name": "Ligue 1"},
    "champions_league": {"id": 8,  "slug": "Champions-League","name": "Champions League"},
    "eredivisie":       {"id": 23, "slug": "Eredivisie",      "name": "Eredivisie"},
    "primeira_liga":    {"id": 32, "slug": "Primeira-Liga",   "name": "Primeira Liga"},
}

# Tabelle da estrarre (in ordine di importanza)
TABLES = [
    ("stats_standard",   "Standard Stats — xG, xA, gol, assist, minuti"),
    ("stats_shooting",   "Shooting — tiri, tiri in porta"),
    ("stats_passing",    "Passing — passaggi chiave, progressivi"),
    ("stats_defense",    "Defense — tackle, pressioni, intercetti"),
    ("stats_possession", "Possession — conduzioni progressive, tocchi area"),
]


def download_fbref_tables(
    league_key: str,
    season: str,
    output_dir: str = "./fbref_output",
    headless: bool = True,
) -> list[dict]:
    """
    Scarica le tabelle statistiche da FBref usando Playwright.
    Ritorna lista di dict {table, filepath, rows}.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright non installato.")
        print("   Esegui: pip install playwright && playwright install chromium")
        sys.exit(1)

    league = LEAGUES.get(league_key)
    if not league:
        print(f"❌ Lega '{league_key}' non supportata. Disponibili: {list(LEAGUES)}")
        sys.exit(1)

    # URL pagina statistiche Standard
    base_url = (
        f"https://fbref.com/en/comps/{league['id']}"
        f"/{season}/stats/{season}-{league['slug']}-Stats"
    )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []

    print(f"\n{'='*60}")
    print(f"  FBref Auto Downloader")
    print(f"  Lega:    {league['name']}")
    print(f"  Stagione: {season}")
    print(f"  URL:     {base_url}")
    print(f"{'='*60}\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
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
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ico,mp4,webm}",
            lambda route: route.abort()
        )

        print(f"  📡 Caricamento pagina...")
        page.goto(base_url, wait_until="networkidle", timeout=60000)
        time.sleep(3)  # attende rendering JS di FBref

        # ── Usa il bottone "Share & Export → Get table as CSV" di FBref ──
        # Questo è il metodo più robusto perché usa la stessa funzione di FBref
        for table_id, table_desc in TABLES:
            print(f"\n  📊 Tabella: {table_desc}")

            # Cerca il link "Get table as CSV" specifico per questa tabella
            csv_link_selector = f"#{table_id} + div .table_controls a[tip*='CSV'], " \
                                 f"#{table_id}_link, " \
                                 f"[data-table='{table_id}'] .table_controls a"

            # Approccio diretto: usa JavaScript per estrarre la tabella
            csv_content = page.evaluate(f"""
                () => {{
                    // Trova la tabella (anche se in commento HTML)
                    let table = document.getElementById('{table_id}');

                    if (!table) {{
                        // FBref a volte nasconde le tabelle in commenti
                        const walker = document.createTreeWalker(
                            document.body,
                            NodeFilter.SHOW_COMMENT
                        );
                        let node;
                        while ((node = walker.nextNode())) {{
                            const tmp = document.createElement('div');
                            tmp.innerHTML = node.nodeValue;
                            const found = tmp.getElementById('{table_id}');
                            if (found) {{ table = found; break; }}
                        }}
                    }}

                    if (!table) return null;

                    const rows = Array.from(table.querySelectorAll('tr'));
                    const csvLines = rows
                        .filter(row => {{
                            const cls = row.className || '';
                            return !cls.includes('over_header') && !cls.includes('spacer');
                        }})
                        .map(row => {{
                            const cells = Array.from(row.querySelectorAll('th, td'));
                            return cells.map(cell => {{
                                let text = cell.innerText
                                    .replace(/\\n/g, ' ')
                                    .replace(/\\r/g, '')
                                    .trim();
                                if (text.includes(',') || text.includes('"')) {{
                                    text = '"' + text.replace(/"/g, '""') + '"';
                                }}
                                return text;
                            }}).join(',');
                        }})
                        .filter(line => line.replace(/,/g, '').trim().length > 0);

                    return csvLines.join('\\n');
                }}
            """)

            if not csv_content:
                print(f"    ⬜ Non trovata (la pagina potrebbe non includerla)")
                continue

            row_count = len(csv_content.split('\n')) - 1
            if row_count < 2:
                print(f"    ⚠️  Trovata ma vuota ({row_count} righe)")
                continue

            # Salva file
            filename = f"fbref_{table_id.replace('stats_','')}_{league['slug']}_{season}.csv"
            filepath = output_path / filename

            # Aggiungi BOM UTF-8 per compatibilità Excel
            with open(filepath, 'w', encoding='utf-8-sig') as f:
                f.write(csv_content)

            results.append({
                "table":    table_id,
                "filepath": str(filepath),
                "rows":     row_count,
                "filename": filename,
            })
            print(f"    ✅ {row_count} giocatori → {filepath}")

        browser.close()

    return results


def upload_to_backend(filepath: str, league_key: str, backend_url: str) -> bool:
    """Carica il CSV nel backend via POST /ingest/fbref/csv-upload."""
    try:
        import requests
    except ImportError:
        print("❌ requests non installato. Esegui: pip install requests")
        return False

    endpoint = f"{backend_url}/ingest/fbref/csv-upload"
    print(f"\n  📤 Upload verso {endpoint}...")

    with open(filepath, 'rb') as f:
        resp = requests.post(
            endpoint,
            files={"file": (os.path.basename(filepath), f, "text/csv")},
            params={"league_key": league_key},
            timeout=120,
        )

    if resp.status_code == 200:
        data = resp.json()
        print(f"  ✅ Upload completato: {data.get('message', 'OK')}")
        print(f"     Arricchiti: {data.get('players_enriched_in_db', '?')}")
        print(f"     Non abbinati: {data.get('players_not_matched', '?')}")
        return True
    else:
        print(f"  ❌ Upload fallito: HTTP {resp.status_code}")
        print(f"     {resp.text[:200]}")
        return False


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scarica automaticamente le statistiche FBref con Playwright"
    )
    parser.add_argument(
        "--league", "-l",
        default="serie_a",
        choices=list(LEAGUES.keys()),
        help="Chiave della lega (default: serie_a)"
    )
    parser.add_argument(
        "--season", "-s",
        default="2024-2025",
        help="Stagione nel formato YYYY-YYYY (default: 2024-2025)"
    )
    parser.add_argument(
        "--output", "-o",
        default="./fbref_output",
        help="Cartella di output (default: ./fbref_output)"
    )
    parser.add_argument(
        "--upload", "-u",
        action="store_true",
        help="Carica automaticamente nel backend dopo il download"
    )
    parser.add_argument(
        "--backend",
        default="http://localhost:8000",
        help="URL del backend Football Scout (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Apri il browser visibile (utile per debug)"
    )
    parser.add_argument(
        "--all-leagues",
        action="store_true",
        help="Scarica tutte le leghe supportate"
    )

    args = parser.parse_args()

    leagues_to_process = list(LEAGUES.keys()) if args.all_leagues else [args.league]

    all_results = []
    for league_key in leagues_to_process:
        print(f"\n{'#'*60}")
        print(f"  Elaborazione: {LEAGUES[league_key]['name']}")
        print(f"{'#'*60}")

        results = download_fbref_tables(
            league_key=league_key,
            season=args.season,
            output_dir=args.output,
            headless=not args.no_headless,
        )

        all_results.extend(results)

        if args.upload and results:
            # Carica prima la tabella standard (la più importante)
            standard = next(
                (r for r in results if "standard" in r["table"]),
                results[0] if results else None
            )
            if standard:
                upload_to_backend(standard["filepath"], league_key, args.backend)

    # ── Riepilogo finale ────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  RIEPILOGO DOWNLOAD")
    print(f"{'='*60}")
    if all_results:
        for r in all_results:
            print(f"  ✅ {r['filename']}: {r['rows']} giocatori")
        print(f"\n  File salvati in: {args.output}/")
        print(f"\n  Per caricarli nel backend:")
        print(f"  1. Apri http://localhost:5173 → Gestione Dati → FBref CSV")
        print(f"  2. Oppure usa: python {__file__} --upload")
        print(f"\n  Oppure via curl:")
        for r in all_results:
            if "standard" in r["table"]:
                # Definiamo le stringhe PRIMA per evitare backslash nelle f-string
                fpath = r["filepath"]
                l_key = args.league
                print("  curl -X POST " + args.backend + "/ingest/fbref/csv-upload \\")
                print("       -F 'file=@" + fpath + "' \\")
                print("       -F 'league_key=" + l_key + "'")

                # print(f"  curl -X POST {args.backend}/ingest/fbref/csv-upload \\")
                # print(f"       -F 'file=@{r[\"filepath\"]}' \\")
                # print(f"       -F 'league_key={args.league}'")
    else:
        print("  ⚠️  Nessun file scaricato.")
        print("  Controlla che Playwright sia installato e la pagina FBref sia accessibile.")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()