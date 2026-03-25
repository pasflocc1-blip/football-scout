"""
sources/api_football_source.py
-------------------------------
Scarica giocatori attivi da API-Football v3.
https://www.api-football.com/documentation-v3

Richiede: API_FOOTBALL_KEY nel .env
Free tier: 100 req/giorno
Copertura: giocatori attivi, squadre reali, statistiche live

Leghe principali:
  135 → Serie A
  39  → Premier League
  140 → La Liga
  78  → Bundesliga
  61  → Ligue 1
"""

import os
import httpx
from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer
from app.services.scoring import compute_scores


async def fetch_from_api_football(
    db: Session,
    league_id: int,
    season: int,
    progress_cb=None,
) -> int:
    """
    Scarica tutti i giocatori di una lega/stagione da API-Football.
    Gestisce la paginazione automaticamente.

    Ritorna il numero di record importati/aggiornati.

    Raises:
        ValueError: se API_FOOTBALL_KEY non è impostata.
        httpx.HTTPStatusError: su errori HTTP dall'API.
    """
    api_key = os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        raise ValueError(
            "API_FOOTBALL_KEY non impostata nel file .env\n"
            "Registrati su https://dashboard.api-football.com/register"
        )

    imported = 0
    page = 1

    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            response = await client.get(
                "https://v3.football.api-sports.io/players",
                headers={"x-apisports-key": api_key},
                params={"league": league_id, "season": season, "page": page},
            )
            response.raise_for_status()
            data = response.json()

            # Controlla errori API-Football (ritornano 200 con corpo errore)
            errors = data.get("errors", {})
            if errors:
                raise ValueError(f"Errore API-Football: {errors}")

            players = data.get("response", [])
            if not players:
                break

            for entry in players:
                p_data = entry.get("player", {})
                stats  = entry.get("statistics", [{}])[0]
                team   = stats.get("team", {})
                games  = stats.get("games", {})
                goals  = stats.get("goals", {})
                passes = stats.get("passes", {})
                duels  = stats.get("duels", {})

                external_id = f"apif_{p_data.get('id')}"

                aerial_total = duels.get("total") or 0
                aerial_won   = duels.get("won") or 0
                aerial_pct   = (aerial_won / aerial_total * 100) if aerial_total else None

                player_data = {
                    "external_id":          external_id,
                    "name":                 p_data.get("name"),
                    "position":             _map_position(games.get("position")),
                    "club":                 team.get("name"),
                    "nationality":          p_data.get("nationality"),
                    "age":                  p_data.get("age"),
                    "preferred_foot":       None,  # non disponibile in API-Football
                    "aerial_duels_won_pct": aerial_pct,
                    "xg_per90":             _float(goals.get("total")),  # proxy
                    "xa_per90":             _float(passes.get("key")),   # proxy
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

            total_pages = data.get("paging", {}).get("total", 1)
            msg = f"  → API-Football: pagina {page}/{total_pages} — {imported} giocatori"
            print(msg)
            if progress_cb:
                progress_cb(imported)

            if page >= total_pages:
                break
            page += 1

    db.commit()
    return imported


# ── Helpers ──────────────────────────────────────────────────────

def _float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _map_position(api_pos: str | None) -> str | None:
    mapping = {
        "Goalkeeper": "GK",
        "Defender":   "CB",
        "Midfielder": "CM",
        "Attacker":   "ST",
    }
    return mapping.get(api_pos)