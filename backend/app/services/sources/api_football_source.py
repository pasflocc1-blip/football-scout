"""
sources/api_football_source.py
-------------------------------
Scarica giocatori attivi da API-Football v3.
https://www.api-football.com/documentation-v3

Richiede: API_FOOTBALL_KEY nel .env
Free tier: 100 req/giorno, max 3 pagine per richiesta
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
from app.services.player_matcher import find_player_in_db
from app.models.models import ScoutingPlayer
from app.services.scoring import compute_scores
from app.services.pro_scouting import calculate_pro_attributes
from datetime import datetime # Necessario per convertire la data


# Piano Free: supporta al massimo le ultime stagioni disponibili.
# Aggiorna questi valori se il piano cambia.
_FREE_SEASON_MIN = 2022
_FREE_SEASON_MAX = 2025

# Piano Free: massimo 3 pagine per richiesta
_FREE_PAGE_LIMIT = 50

async def fetch_from_api_football(
    db: Session,
    league_id: int = None,
    season: int = 2023,
    team_id: int = None,
    progress_cb=None,
    stop_event=None,   # threading.Event per cancellazione
) -> int:
    # --- LOG DI PARTENZA ---
    print(f"DEBUG: Avvio importazione. League: {league_id}, Season: {season}, Team: {team_id}")

    params = {"season": season}
    
    # Logica di selezione parametro
    if team_id and int(team_id) > 0:
        params["team"] = team_id
        print(f"DEBUG: Filtro impostato su SQUADRA (ID: {team_id})")
    elif league_id:
        params["league"] = league_id
        print(f"DEBUG: Filtro impostato su LEGA (ID: {league_id})")
    else:
        print("ERROR: Nessun league_id o team_id fornito!")
        return 0

    imported = 0
    page = 1
    api_key = os.getenv("API_FOOTBALL_KEY")

    async with httpx.AsyncClient(timeout=30.0) as client:
        while page <= _FREE_PAGE_LIMIT:
            params["page"] = page
            
            print(f"DEBUG URL: https://v3.football.api-sports.io/players?{params}")

            response = await client.get(
                "https://v3.football.api-sports.io/players",
                params=params,
                headers={"x-apisports-key": api_key}
            )
            
            data = response.json()
            players_list = data.get("response", [])
            print(f"DEBUG REALE: Ricevuti {len(players_list)} giocatori nella pagina {page}")

            if not players_list:
                print(f"DEBUG: Pagina {page} vuota. Mi fermo.")
                break

            # Controlla cancellazione
            if stop_event and stop_event.is_set():
                print(f"DEBUG: Interruzione richiesta alla pagina {page}.")
                break

            for item in players_list:
                p_info = item["player"]
                p_stats = item["statistics"][0] if item["statistics"] else {}

                # --- GESTIONE DATA DI NASCITA ---
                # L'API restituisce "1987-06-24", lo convertiamo in oggetto date
                birth_date_obj = None
                raw_birth_date = p_info.get("birth", {}).get("date")
                if raw_birth_date:
                    try:
                        birth_date_obj = datetime.strptime(raw_birth_date, "%Y-%m-%d").date()
                    except ValueError:
                        birth_date_obj = None

                # Estrazione metriche per l'algoritmo
                raw_metrics = {
                    "minutes": p_stats.get("games", {}).get("minutes") or 0,
                    "goals": p_stats.get("goals", {}).get("total") or 0,
                    "assists": p_stats.get("goals", {}).get("assists") or 0,
                    "shots_on_target": p_stats.get("shots", {}).get("on") or 0,
                    "pass_accuracy": p_stats.get("passes", {}).get("accuracy") or 0,
                    "key_passes": p_stats.get("passes", {}).get("key") or 0,
                    "dribbles_success": p_stats.get("dribbles", {}).get("success") or 0,
                    "duels_won": p_stats.get("duels", {}).get("won") or 0,
                    "aerial_won": p_stats.get("duels", {}).get("total") or 0, 
                }

                # 1. Recuperiamo la posizione corretta dalle statistiche (es. "Attacker", "Midfielder")
                raw_position = p_stats.get("games", {}).get("position") or "Midfielder"

                # 2. Calcolo attributi PRO usando la posizione corretta
                pro_attrs = calculate_pro_attributes(raw_metrics, raw_position)

                # Mappatura su ScoutingPlayer
                player_dict = {
                    "api_football_id": p_info["id"],
                    "name": p_info["name"],
                    "birth_date": birth_date_obj, # Campo aggiunto
                    "age": p_info["age"],
                    "position": raw_position,
                    "club": p_stats.get("team", {}).get("name"),
                    "nationality": p_info.get("nationality"),
                    
                    # Voti 1-99 calcolati
                    "pace": pro_attrs["pace"],
                    "shooting": pro_attrs["shooting"],
                    "passing": pro_attrs["passing"],
                    "dribbling": pro_attrs["dribbling"],
                    "defending": pro_attrs["defending"],
                    "physical": pro_attrs["physical"],

                    # Stats reali
                    "progressive_passes": raw_metrics["key_passes"],
                    "aerial_duels_won_pct": float(p_stats.get("duels", {}).get("won") or 0),
                }

                # Upsert basato su api_football_id
                existing = db.query(ScoutingPlayer).filter(
                    ScoutingPlayer.api_football_id == p_info["id"]
                ).first()

                if existing:
                    for key, value in player_dict.items():
                        setattr(existing, key, value)
                else:
                    db.add(ScoutingPlayer(**player_dict))

                imported += 1

            total_pages = data.get("paging", {}).get("total", 1)
            if page >= total_pages or page >= _FREE_PAGE_LIMIT:
                break
            page += 1

    print(f"DEBUG: Importazione completata. Totale importati: {imported}")
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

def _int(val) -> int:
    """Converte un valore in intero, ritornando 0 se è nullo o invalido."""
    try:
        return int(float(val)) if val not in (None, "", "N/A") else 0
    except (ValueError, TypeError):
        return 0