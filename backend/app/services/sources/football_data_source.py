"""
sources/football_data_source.py
--------------------------------
Client per Football-Data.org API v4.

FIX "0 club aggiornati":
  Il problema era che find_player_in_db non trovava i giocatori perche:
  1. Il DB potrebbe essere vuoto (Kaggle non ancora importato)
  2. I nomi Football-Data ("Kylian Mbappe") non matchano Kaggle ("K. Mbappe")
  
  SOLUZIONE: sync_player_clubs ora:
  a) Prova il match intelligente come prima
  b) Se NON trovato, inserisce il giocatore nel DB come nuovo ScoutingPlayer
     (con solo name + club + nationality, gli altri campi si aggiorneranno
      con API-Football o Kaggle in seguito)
  c) Aggiorna SEMPRE il campo club se trova un player gia esistente

NOVITA':
  - stop_event: threading.Event per cancellazione dal router
"""

import os
import asyncio
import threading
import httpx
from sqlalchemy.orm import Session

from app.services.player_matcher import find_player_in_db
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
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/competitions", headers=_headers())
        resp.raise_for_status()
        data = resp.json()
    return sorted(
        [{"id": c["id"], "code": c.get("code",""), "name": c["name"],
          "country": c.get("area",{}).get("name",""), "plan": c.get("plan","")}
         for c in data.get("competitions", [])],
        key=lambda x: x["name"],
    )


async def fetch_teams(competition_code: str, season: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/competitions/{competition_code}/teams",
            headers=_headers(), params={"season": season},
        )
        resp.raise_for_status()
        data = resp.json()
    return [{"id": t["id"], "name": t["name"], "short": t.get("shortName",""),
             "tla": t.get("tla",""), "crest": t.get("crest",""),
             "founded": t.get("founded"), "venue": t.get("venue","")}
            for t in data.get("teams", [])]


async def fetch_standings(competition_code: str, season: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/competitions/{competition_code}/standings",
            headers=_headers(), params={"season": season},
        )
        resp.raise_for_status()
        data = resp.json()
    result = []
    for standing in data.get("standings", []):
        if standing.get("type") == "TOTAL":
            for entry in standing.get("table", []):
                result.append({
                    "position": entry["position"], "team": entry["team"]["name"],
                    "played": entry["playedGames"], "won": entry["won"],
                    "draw": entry["draw"], "lost": entry["lost"],
                    "goals_for": entry["goalsFor"], "goals_against": entry["goalsAgainst"],
                    "goal_diff": entry["goalDifference"], "points": entry["points"],
                })
    return result


async def sync_player_clubs(
    db: Session,
    competition_code: str,
    season: int,
    progress_cb=None,
    stop_event: threading.Event = None,
) -> dict:
    """
    Scarica la rosa di ogni squadra e per ogni giocatore:
      1. Cerca nel DB tramite find_player_in_db (match fuzzy nome+club)
      2. Se trovato  → aggiorna .club
      3. Se NON trovato → inserisce nuovo ScoutingPlayer con i dati base disponibili
         (name, club, nationality, position) cosi il giocatore e tracciabile in seguito

    Ritorna dict con teams_processed, players_updated, players_inserted, competition, season
    """
    headers = _headers()
    updated = 0
    inserted = 0
    teams_processed = 0

    async with httpx.AsyncClient(timeout=20) as client:
        # Lista squadre
        teams_resp = await client.get(
            f"{BASE_URL}/competitions/{competition_code}/teams",
            headers=headers, params={"season": season},
        )
        teams_resp.raise_for_status()
        teams = teams_resp.json().get("teams", [])
        print(f"  → Football-Data: {len(teams)} squadre trovate")

        for team in teams:
            # Controlla cancellazione prima di ogni squadra
            if stop_event and stop_event.is_set():
                print("  ⏹ Football-Data: interruzione richiesta, mi fermo.")
                break

            team_name = team["name"]
            team_id   = team["id"]
            teams_processed += 1

            try:
                # Rate limit free tier: 10 req/min
                await asyncio.sleep(6)

                # Controlla cancellazione anche durante il sleep
                if stop_event and stop_event.is_set():
                    print("  ⏹ Football-Data: interruzione durante sleep.")
                    break

                squad_resp = await client.get(
                    f"{BASE_URL}/teams/{team_id}", headers=headers,
                )
                squad_resp.raise_for_status()
                squad_data = squad_resp.json()
                squad      = squad_data.get("squad", [])

                team_updated  = 0
                team_inserted = 0

                for member in squad:
                    player_name = member.get("name", "")
                    if not player_name:
                        continue

                    # 1. Tenta match nel DB
                    player = find_player_in_db(db, player_name, team_name)

                    if player:
                        # Aggiorna club (e nazionalita se mancante)
                        player.club = team_name
                        if not player.nationality and member.get("nationality"):
                            player.nationality = member["nationality"]
                        updated += 1
                        team_updated += 1
                    else:
                        # 2. Non trovato → inserisci come nuovo player
                        #    Mappa la posizione Football-Data → nostra convenzione
                        pos_raw = member.get("position", "")
                        position = _map_position(pos_raw)

                        new_player = ScoutingPlayer(
                            name        = player_name,
                            club        = team_name,
                            nationality = member.get("nationality"),
                            position    = position,
                            age         = _calc_age(member.get("dateOfBirth")),
                            # Tutti gli attributi numerici restano None/0
                            # verranno riempiti da API-Football o Kaggle
                        )
                        db.add(new_player)
                        inserted += 1
                        team_inserted += 1

                print(
                    f"  → Football-Data: {teams_processed}/{len(teams)} {team_name} "
                    f"({len(squad)} giocatori | "
                    f"aggiornati: {team_updated} | inseriti: {team_inserted})"
                )

            except httpx.HTTPStatusError as e:
                print(f"  ⚠ Errore {team_name}: HTTP {e.response.status_code}")
                continue
            except Exception as e:
                print(f"  ⚠ Errore {team_name}: {e}")
                continue

            if progress_cb:
                progress_cb(teams_processed, len(teams))

            # Commit ogni 5 squadre per non perdere troppo in caso di stop
            if teams_processed % 5 == 0:
                db.commit()

    db.commit()
    total = updated + inserted
    print(
        f"  → Football-Data: completato — "
        f"{updated} club aggiornati, {inserted} nuovi giocatori inseriti "
        f"(totale modifiche: {total})"
    )

    return {
        "teams_processed":   teams_processed,
        "players_updated":   updated,
        "players_inserted":  inserted,
        "players_total":     total,
        "competition":       competition_code,
        "season":            season,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _map_position(pos: str) -> str | None:
    """
    Mappa le posizioni Football-Data.org verso le nostre convenzioni.
    Football-Data usa: Goalkeeper, Defender, Midfielder, Offence
    """
    mapping = {
        "Goalkeeper": "GK",
        "Defender":   "CB",
        "Midfielder": "CM",
        "Offence":    "ST",
        "Forward":    "ST",
        "Attacker":   "ST",
    }
    return mapping.get(pos, pos if pos else None)


def _calc_age(date_of_birth: str | None) -> int | None:
    """Calcola l'eta dalla data di nascita ISO (YYYY-MM-DD)."""
    if not date_of_birth:
        return None
    try:
        from datetime import date
        born = date.fromisoformat(date_of_birth[:10])
        today = date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except Exception:
        return None