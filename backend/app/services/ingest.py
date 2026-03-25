"""
services/ingest.py
------------------
Due modalità di ingestion:

1. KAGGLE (sviluppo / prototipo)
   - Scarica il dataset FIFA da Kaggle (CSV)
   - Non richiede API key esterne
   - Ottimo per iniziare a sviluppare senza costi

2. API-FOOTBALL (produzione)
   - Dati live aggiornati
   - Richiede API key (free tier: 100 req/giorno)

Uso da terminale (dentro il container):
    docker compose exec backend python -m app.services.ingest --source kaggle --file /data/players.csv
    docker compose exec backend python -m app.services.ingest --source api --league 135 --season 2024
"""

import os
import csv
import httpx
import argparse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import ScoutingPlayer
from app.services.scoring import compute_scores

from dotenv import load_dotenv

# path assoluto del file corrente
current_file = os.path.abspath(__file__)

# risali fino alla root del progetto (football-scout)
project_root = os.path.abspath(os.path.join(current_file, "../../../.."))
env_path = os.path.join(project_root, ".env")

print("Cerco .env in:", env_path)  # DEBUG

load_dotenv(env_path)
print("API KEY:", os.getenv("API_FOOTBALL_KEY"))  # DEBUG

# ── Mappatura colonne CSV Kaggle FIFA → nostro modello ────────────
# Adatta i nomi colonna a seconda della versione del dataset scaricato
KAGGLE_COLUMN_MAP = {
    # colonna CSV          →  campo modello
    "short_name":            "name",
    "player_positions":      "position",   # es. "ST, CF" → prendiamo il primo
    "club_name":             "club",
    "nationality_name":      "nationality",
    "age":                   "age",
    "preferred_foot":        "preferred_foot",
    "pace":                  "pace",
    "shooting":              "shooting",
    "passing":               "passing",
    "dribbling":             "dribbling",
    "defending":             "defending",
    "physic":                "physical",   # 'physic' nel CSV Kaggle
    "attacking_heading_accuracy": "aerial_duels_won_pct",  # proxy
}


def import_from_kaggle_csv(db: Session, filepath: str, limit: int = 2000) -> int:
    """
    Importa giocatori da un CSV Kaggle FIFA.

    Scarica il dataset da:
    https://www.kaggle.com/datasets/stefanoleone992/fifa-22-complete-player-dataset
    File da usare: players_22.csv (o players_23.csv)

    Ritorna il numero di record importati.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File non trovato: {filepath}\n"
                                f"Scarica da Kaggle e copialo in: {filepath}")

    imported = 0
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            if i >= limit:
                break

            # Posizione: prende solo il primo ruolo (es. "ST, CF" → "ST")
            raw_pos = row.get("player_positions", "")
            position = raw_pos.split(",")[0].strip() if raw_pos else None

            player_data = {
                "external_id":    f"kaggle_{row.get('sofifa_id', i)}",
                "name":           row.get("short_name", f"Player_{i}"),
                "position":       position,
                "club":           row.get("club_name"),
                "nationality":    row.get("nationality_name"),
                "age":            _int(row.get("age")),
                "preferred_foot": row.get("preferred_foot"),
                "pace":           _int(row.get("pace")),
                "shooting":       _int(row.get("shooting")),
                "passing":        _int(row.get("passing")),
                "dribbling":      _int(row.get("dribbling")),
                "defending":      _int(row.get("defending")),
                "physical":       _int(row.get("physic")),
                "aerial_duels_won_pct": _float(row.get("attacking_heading_accuracy")),
            }

            # Upsert: aggiorna se esiste, inserisce se no
            existing = db.query(ScoutingPlayer).filter_by(
                external_id=player_data["external_id"]
            ).first()

            if existing:
                for k, v in player_data.items():
                    setattr(existing, k, v)
                p = existing
            else:
                p = ScoutingPlayer(**player_data)
                db.add(p)
                db.flush()  # ottieni l'id prima del commit

            # Calcola gli score compositi
            scores = compute_scores(p)
            for k, v in scores.items():
                setattr(p, k, v)

            imported += 1

            # Commit a batch di 200 per non saturare la memoria
            if imported % 200 == 0:
                db.commit()
                print(f"  → {imported} giocatori importati...")

    db.commit()
    return imported


async def fetch_from_api_football(db: Session, league_id: int, season: int) -> int:
    """
    Scarica i giocatori attivi da API-Football.
    Richiede FOOTBALL_DATA_KEY nel file .env

    https://api-football.com/documentation-v3#tag/Players/operation/get-players
    """
    print("API KEY:", os.getenv("API_FOOTBALL_KEY"))

    api_key = os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        raise ValueError("API_FOOTBALL_KEY non impostata nel file .env")

    imported = 0
    page = 1

    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            response = await client.get(
                "https://v3.football.api-sports.io/players",
                headers={"x-apisports-key": api_key},
                params={"league": league_id, "season": season, "page": page},
            )
            response.raise_for_status()
            data = response.json()

            players = data.get("response", [])
            if not players:
                break

            for entry in players:
                p_data  = entry.get("player", {})
                stats   = entry.get("statistics", [{}])[0]
                team    = stats.get("team", {})
                games   = stats.get("games", {})
                goals   = stats.get("goals", {})
                passes  = stats.get("passes", {})
                duels   = stats.get("duels", {})

                external_id = f"apif_{p_data.get('id')}"

                # Duelli aerei: percentuale vinti
                aerial_total = duels.get("total") or 0
                aerial_won   = duels.get("won")   or 0
                aerial_pct   = (aerial_won / aerial_total * 100) if aerial_total else None

                player_data = {
                    "external_id":           external_id,
                    "name":                  p_data.get("name"),
                    "position":              _map_position(games.get("position")),
                    "club":                  team.get("name"),
                    "nationality":           p_data.get("nationality"),
                    "age":                   p_data.get("age"),
                    "preferred_foot":        None,   # non disponibile in API-Football
                    "aerial_duels_won_pct":  aerial_pct,
                    "xg_per90":              _float(goals.get("total")),   # proxy
                    "xa_per90":              _float(passes.get("key")),    # proxy
                }

                existing = db.query(ScoutingPlayer).filter_by(
                    external_id=external_id
                ).first()

                if existing:
                    for k, v in player_data.items():
                        if v is not None:
                            setattr(existing, k, v)
                    p = existing
                else:
                    p = ScoutingPlayer(**player_data)
                    db.add(p)
                    db.flush()

                scores = compute_scores(p)
                for k, v in scores.items():
                    setattr(p, k, v)

                imported += 1

            # Paginazione
            total_pages = data.get("paging", {}).get("total", 1)
            if page >= total_pages:
                break
            page += 1
            print(f"  → Pagina {page}/{total_pages} — {imported} giocatori...")

    db.commit()
    return imported


# ── Helper privati ────────────────────────────────────────────────

def _int(val) -> int | None:
    try:
        return int(float(val)) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _map_position(api_pos: str | None) -> str | None:
    """Converte le posizioni di API-Football nel nostro schema."""
    mapping = {
        "Goalkeeper":     "GK",
        "Defender":       "CB",
        "Midfielder":     "CM",
        "Attacker":       "ST",
    }
    return mapping.get(api_pos)


# ── Entry point CLI ───────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importa giocatori nel DB")
    parser.add_argument("--source", choices=["kaggle", "api"], required=True)
    parser.add_argument("--file",   help="Path CSV Kaggle (es. /data/players_22.csv)")
    parser.add_argument("--league", type=int, default=135, help="ID lega API-Football (135=Serie A)")
    parser.add_argument("--season", type=int, default=2024)
    parser.add_argument("--limit",  type=int, default=2000, help="Max giocatori da importare")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.source == "kaggle":
            csv_path = args.file or "D:\Progetti\football-scout\data\players_22.csv"
            print(f"Importazione da Kaggle CSV: {csv_path}")
            n = import_from_kaggle_csv(db, csv_path, limit=args.limit)
            print(f"✅ Importati {n} giocatori dal dataset FIFA/Kaggle")

        elif args.source == "api":
            import asyncio
            print(f"Importazione da API-Football (lega {args.league}, stagione {args.season})")
            n = asyncio.run(fetch_from_api_football(db, args.league, args.season))
            print(f"✅ Importati {n} giocatori da API-Football")
    finally:
        db.close()
