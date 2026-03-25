"""
sources/football_data_source.py
--------------------------------
Client per Football-Data.org API v4.
https://www.football-data.org/documentation/quickstart

Cosa fornisce:
  - Lista competizioni disponibili
  - Squadre per competizione/stagione
  - Classifica/standings
  - Rosa squadre → aggiorna il campo 'club' nei ScoutingPlayer

Free tier: 10 req/min, dati principali delle leghe top

Richiede: FOOTBALL_DATA_KEY nel .env
Registrazione: https://www.football-data.org/client/register

Codici competizione principali:
  SA   → Serie A
  PL   → Premier League
  PD   → La Liga (Primera Division)
  BL1  → Bundesliga
  FL1  → Ligue 1
  CL   → UEFA Champions League
  EC   → European Championship
  WC   → FIFA World Cup
"""

import os
import asyncio
import httpx
from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer

BASE_URL = "https://api.football-data.org/v4"

COMPETITION_CODES = {
    "serie_a":          "SA",
    "premier_league":   "PL",
    "la_liga":          "PD",
    "bundesliga":       "BL1",
    "ligue_1":          "FL1",
    "champions_league": "CL",
    "eredivisie":       "DED",
    "primeira_liga":    "PPL",
    "championship":     "ELC",
    "world_cup":        "WC",
    "euro":             "EC",
}


def _headers() -> dict:
    api_key = os.getenv("FOOTBALL_DATA_KEY")
    if not api_key:
        raise ValueError(
            "FOOTBALL_DATA_KEY non impostata nel .env\n"
            "Registrati su https://www.football-data.org/client/register"
        )
    return {"X-Auth-Token": api_key}


async def fetch_competitions() -> list[dict]:
    """Lista competizioni disponibili nel piano attivo."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/competitions", headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    return sorted(
        [
            {
                "id":      c["id"],
                "code":    c.get("code", ""),
                "name":    c["name"],
                "country": c.get("area", {}).get("name", ""),
                "plan":    c.get("plan", ""),
            }
            for c in data.get("competitions", [])
        ],
        key=lambda x: x["name"],
    )


async def fetch_teams(competition_code: str, season: int) -> list[dict]:
    """Squadre di una competizione per una stagione."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/competitions/{competition_code}/teams",
            headers=_headers(),
            params={"season": season},
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "id":      t["id"],
            "name":    t["name"],
            "short":   t.get("shortName", ""),
            "tla":     t.get("tla", ""),
            "crest":   t.get("crest", ""),
            "founded": t.get("founded"),
            "venue":   t.get("venue", ""),
        }
        for t in data.get("teams", [])
    ]


async def fetch_standings(competition_code: str, season: int) -> list[dict]:
    """Classifica di una competizione (tipo TOTAL)."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/competitions/{competition_code}/standings",
            headers=_headers(),
            params={"season": season},
        )
        resp.raise_for_status()
        data = resp.json()

    result = []
    for standing in data.get("standings", []):
        if standing.get("type") == "TOTAL":
            for entry in standing.get("table", []):
                result.append({
                    "position":      entry["position"],
                    "team":          entry["team"]["name"],
                    "played":        entry["playedGames"],
                    "won":           entry["won"],
                    "draw":          entry["draw"],
                    "lost":          entry["lost"],
                    "goals_for":     entry["goalsFor"],
                    "goals_against": entry["goalsAgainst"],
                    "goal_diff":     entry["goalDifference"],
                    "points":        entry["points"],
                })
    return result


async def sync_player_clubs(
    db: Session,
    competition_code: str,
    season: int,
    progress_cb=None,
) -> dict:
    """
    Scarica la rosa di ogni squadra della competizione e aggiorna
    il campo 'club' nei ScoutingPlayer corrispondenti nel DB.

    Utile per mantenere aggiornata l'affiliazione di club dei giocatori.

    Nota: il free tier limita a 10 req/min → usa asyncio.sleep tra squadre.
    """
    headers = _headers()
    updated = 0
    teams_processed = 0

    async with httpx.AsyncClient(timeout=20) as client:
        # Lista squadre
        teams_resp = await client.get(
            f"{BASE_URL}/competitions/{competition_code}/teams",
            headers=headers,
            params={"season": season},
        )
        teams_resp.raise_for_status()
        teams = teams_resp.json().get("teams", [])
        print(f"  → Football-Data: {len(teams)} squadre trovate")

        for team in teams:
            team_name = team["name"]
            team_id   = team["id"]
            teams_processed += 1

            try:
                # Rispetta rate limit free tier (10 req/min)
                await asyncio.sleep(6)

                squad_resp = await client.get(
                    f"{BASE_URL}/teams/{team_id}",
                    headers=headers,
                )
                squad_resp.raise_for_status()
                squad = squad_resp.json().get("squad", [])

                for member in squad:
                    player_name = member.get("name", "")
                    if not player_name:
                        continue

                    player = (
                        db.query(ScoutingPlayer)
                        .filter(ScoutingPlayer.name.ilike(f"%{player_name}%"))
                        .first()
                    )
                    if player:
                        player.club = team_name
                        updated += 1

                print(f"  → Football-Data: {team_name} ({len(squad)} giocatori)")

            except httpx.HTTPStatusError as e:
                print(f"  ⚠ Errore {team_name}: HTTP {e.response.status_code}")
                continue

            if progress_cb:
                progress_cb(teams_processed, len(teams))

    db.commit()
    print(f"  → Football-Data: {updated} giocatori aggiornati")

    return {
        "teams_processed":  teams_processed,
        "players_updated":  updated,
        "competition":      competition_code,
        "season":           season,
    }