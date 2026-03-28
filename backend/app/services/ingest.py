"""
services/ingest.py
------------------
Orchestratore ingestion — delega a ogni sorgente specifica.

Sorgenti disponibili:
  kaggle        → CSV Kaggle FIFA 22/23 (gratis, 18k giocatori)
  api           → API-Football v3 (live, richiede API_FOOTBALL_KEY)
  statsbomb     → StatsBomb Open Data (xG/xA event-level, gratis)
  fbref         → FBref scraping (xG/xA alternativo + avanzato, gratis)
  understat     → Understat.com (xG/xA stagione corrente, gratis)
  football-data → Football-Data.org (rose campionato, richiede FOOTBALL_DATA_KEY)
  all           → Esegue tutte le sorgenti in sequenza

Uso da terminale (dentro container):
  python -m app.services.ingest --source kaggle --file /app/data/players_22.csv --limit 5000
  python -m app.services.ingest --source api --league 135 --season 2024
  python -m app.services.ingest --source statsbomb --comp 12 --season-id 27 --max-matches 100
  python -m app.services.ingest --source fbref --fbref-league serie_a --fbref-season 2024-2025
  python -m app.services.ingest --source understat --understat-league serie_a --understat-season 2024
  python -m app.services.ingest --source football-data --fd-comp SA --season 2024
  python -m app.services.ingest --source all --file /app/data/players_22.csv --season 2024
"""

import argparse
import asyncio
import os

from app.database import SessionLocal
from app.services.sources.kaggle_source import import_from_kaggle_csv
from app.services.sources.api_football_source import fetch_from_api_football
from app.services.sources.statsbomb_source import fetch_from_statsbomb
from app.services.sources.fbref_source import fetch_from_fbref, scrape_standard_stats
from app.services.sources.understat_source import fetch_from_understat
from app.services.sources.football_data_source import sync_player_clubs


async def run_all(
    kaggle_file: str | None = None,
    kaggle_limit: int = 2000,
    api_league: int = 135,
    season: int = 2024,
    statsbomb_comp: int = 12,
    statsbomb_season_id: int = 27,
    statsbomb_max_matches: int = 50,
    fbref_league: str = "serie_a",
    fbref_season: str = "2023-2024",
    understat_league: str = "serie_a",
    understat_season: int = 2024,
    football_data_comp: str = "SA",
) -> dict:
    """
    Esegue tutte le sorgenti in sequenza.
    Le sorgenti che richiedono API key vengono saltate se la chiave manca.
    Ritorna un dict {sorgente: risultato}.
    """
    results = {}
    db = SessionLocal()

    try:
        # ── 1. Kaggle ──────────────────────────────────────────────
        if kaggle_file and os.path.exists(kaggle_file):
            print("\n[1/6] ▶ Kaggle CSV...")
            n = import_from_kaggle_csv(db, kaggle_file, limit=kaggle_limit)
            results["kaggle"] = {"status": "ok", "imported": n}
        else:
            reason = "file non specificato" if not kaggle_file else f"file non trovato: {kaggle_file}"
            results["kaggle"] = {"status": "skipped", "reason": reason}
            print(f"\n[1/6] ⏭ Kaggle saltato — {reason}")

        # ── 2. API-Football ────────────────────────────────────────
        if os.getenv("API_FOOTBALL_KEY"):
            print(f"\n[2/6] ▶ API-Football (lega {api_league}, stagione {season})...")
            try:
                n = await fetch_from_api_football(db, api_league, season)
                results["api_football"] = {"status": "ok", "imported": n}
            except Exception as e:
                results["api_football"] = {"status": "error", "error": str(e)}
                print(f"  ✗ API-Football: {e}")
        else:
            results["api_football"] = {"status": "skipped", "reason": "API_FOOTBALL_KEY non impostata"}
            print("\n[2/6] ⏭ API-Football saltato — API_FOOTBALL_KEY mancante")

        # ── 3. StatsBomb ───────────────────────────────────────────
        print(f"\n[3/6] ▶ StatsBomb (comp {statsbomb_comp}, season_id {statsbomb_season_id})...")
        try:
            sb_result = await fetch_from_statsbomb(
                db, statsbomb_comp, statsbomb_season_id, statsbomb_max_matches
            )
            results["statsbomb"] = {"status": "ok", **sb_result}
        except Exception as e:
            results["statsbomb"] = {"status": "error", "error": str(e)}
            print(f"  ✗ StatsBomb: {e}")

        # ── 4. FBref ───────────────────────────────────────────────
        print(f"\n[4/6] ▶ FBref ({fbref_league} {fbref_season})...")
        try:
            fbref_result = await fetch_from_fbref(db, fbref_league, fbref_season)
            results["fbref"] = {"status": "ok", **fbref_result}
        except Exception as e:
            results["fbref"] = {"status": "error", "error": str(e)}
            print(f"  ✗ FBref: {e}")

        # ── 5. Understat ───────────────────────────────────────────
        print(f"\n[5/6] ▶ Understat ({understat_league} {understat_season}/{understat_season+1})...")
        try:
            us_result = await fetch_from_understat(db, understat_league, understat_season)
            results["understat"] = {"status": "ok", **us_result}
        except Exception as e:
            results["understat"] = {"status": "error", "error": str(e)}
            print(f"  ✗ Understat: {e}")

        # ── 6. Football-Data.org ───────────────────────────────────
        if os.getenv("FOOTBALL_DATA_KEY"):
            print(f"\n[6/6] ▶ Football-Data.org (comp {football_data_comp}, stagione {season})...")
            try:
                fd_result = await sync_player_clubs(db, football_data_comp, season)
                results["football_data"] = {"status": "ok", **fd_result}
            except Exception as e:
                results["football_data"] = {"status": "error", "error": str(e)}
                print(f"  ✗ Football-Data: {e}")
        else:
            results["football_data"] = {"status": "skipped", "reason": "FOOTBALL_DATA_KEY non impostata"}
            print("\n[6/6] ⏭ Football-Data.org saltato — FOOTBALL_DATA_KEY mancante")

    finally:
        db.close()

    print("\n✅ Import completo!")
    return results


# ── Entry point CLI ───────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importa dati calciatori nel DB")
    parser.add_argument(
        "--source",
        choices=["kaggle", "api", "statsbomb", "fbref", "understat", "football-data", "all"],
        required=True,
    )
    # Kaggle
    parser.add_argument("--file", help="Path CSV Kaggle nel container")
    parser.add_argument("--limit", type=int, default=2000)
    # API-Football
    parser.add_argument("--league", type=int, default=135, help="135=Serie A, 39=PL, 140=La Liga")
    parser.add_argument("--season", type=int, default=2024)
    # StatsBomb
    parser.add_argument("--comp", type=int, default=12, help="Competition ID StatsBomb")
    parser.add_argument("--season-id", type=int, default=27, dest="season_id")
    parser.add_argument("--max-matches", type=int, default=50, dest="max_matches")
    # FBref
    parser.add_argument("--fbref-league", default="serie_a", dest="fbref_league",
                        choices=list(["serie_a", "premier_league", "la_liga",
                                      "bundesliga", "ligue_1", "champions_league",
                                      "eredivisie", "primeira_liga"]))
    parser.add_argument("--fbref-season", default="2024-2025", dest="fbref_season")
    # Understat
    parser.add_argument("--understat-league", default="serie_a", dest="understat_league",
                        choices=["serie_a", "premier_league", "la_liga",
                                 "bundesliga", "ligue_1", "rfpl"])
    parser.add_argument("--understat-season", type=int, default=2024, dest="understat_season",
                        help="Anno di inizio stagione (es. 2024 per 2024/25)")
    # Football-Data.org
    parser.add_argument("--fd-comp", default="SA", dest="fd_comp",
                        help="SA=Serie A, PL=Premier League, PD=La Liga, BL1=Bundesliga")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.source == "kaggle":
            csv_path = args.file or "data/players_22.csv"
            print(f"Importazione da Kaggle: {csv_path}")
            n = import_from_kaggle_csv(db, csv_path, limit=args.limit)
            print(f"✅ Importati {n} giocatori da Kaggle")

        elif args.source == "api":
            print(f"API-Football — lega {args.league}, stagione {args.season}")
            n = asyncio.run(fetch_from_api_football(db, args.league, args.season))
            print(f"✅ Importati {n} giocatori da API-Football")

        elif args.source == "statsbomb":
            print(f"StatsBomb — comp {args.comp}, season_id {args.season_id}")
            result = asyncio.run(
                fetch_from_statsbomb(db, args.comp, args.season_id, args.max_matches)
            )
            print(f"✅ StatsBomb: {result}")

        elif args.source == "fbref":
            print(f"FBref — {args.fbref_league} {args.fbref_season}")
            result = scrape_standard_stats(db, args.fbref_league, args.fbref_season)
            print(f"✅ FBref: {result}")

        elif args.source == "understat":
            print(f"Understat — {args.understat_league} {args.understat_season}/{args.understat_season+1}")
            result = asyncio.run(
                fetch_from_understat(db, args.understat_league, args.understat_season)
            )
            print(f"✅ Understat: {result}")

        elif args.source == "football-data":
            print(f"Football-Data.org — comp {args.fd_comp}, stagione {args.season}")
            result = asyncio.run(sync_player_clubs(db, args.fd_comp, args.season))
            print(f"✅ Football-Data: {result}")

        elif args.source == "all":
            print("Esecuzione di tutte le sorgenti...")
            result = asyncio.run(run_all(
                kaggle_file=args.file,
                kaggle_limit=args.limit,
                api_league=args.league,
                season=args.season,
                statsbomb_comp=args.comp,
                statsbomb_season_id=args.season_id,
                statsbomb_max_matches=args.max_matches,
                fbref_league=args.fbref_league,
                fbref_season=args.fbref_season,
                understat_league=args.understat_league,
                understat_season=args.understat_season,
                football_data_comp=args.fd_comp,
            ))
            print(f"✅ Risultati: {result}")

    finally:
        db.close()