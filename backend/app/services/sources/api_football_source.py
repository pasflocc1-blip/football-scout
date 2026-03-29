"""
sources/api_football_source.py — Fase 1 pipeline oggettivo
-----------------------------------------------------------
CAMBIO RISPETTO ALLA VERSIONE PRECEDENTE:
  - Rimossa la chiamata a calculate_pro_attributes() (stima FIFA soggettiva)
  - Salva le statistiche raw: gol, assist, minuti, tiri, duelli, passaggi
  - Questi dati alimenteranno recalculate_objective_scores() (Fase 3)

Richiede: API_FOOTBALL_KEY nel .env
Free tier: 100 req/giorno, max 3 pagine per endpoint
"""

import os
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer
from app.services.player_matcher import find_player_in_db
from app.services.scoring import compute_scores

_FREE_PAGE_LIMIT = 50

# Mappa posizione API-Football → codice FIFA standard
_POSITION_MAP = {
    "Goalkeeper": "GK",
    "Defender":   "CB",
    "Midfielder": "CM",
    "Attacker":   "ST",
}


async def fetch_from_api_football(
    db: Session,
    league_id: int = None,
    season: int = 2024,
    team_id: int = None,
    progress_cb=None,
    stop_event=None,
) -> int:

    params = {"season": season}
    if team_id and int(team_id) > 0:
        params["team"] = team_id
        print(f"  API-Football: filtro SQUADRA id={team_id}")
    elif league_id:
        params["league"] = league_id
        print(f"  API-Football: filtro LEGA id={league_id} stagione={season}")
    else:
        print("  API-Football: ERROR — nessun league_id o team_id")
        return 0

    imported = 0
    page = 1
    api_key = os.getenv("API_FOOTBALL_KEY")

    async with httpx.AsyncClient(timeout=30.0) as client:
        while page <= _FREE_PAGE_LIMIT:
            params["page"] = page

            response = await client.get(
                "https://v3.football.api-sports.io/players",
                params=params,
                headers={"x-apisports-key": api_key},
            )
            data = response.json()
            players_list = data.get("response", [])
            print(f"  API-Football: pagina {page} → {len(players_list)} giocatori")

            if not players_list:
                break
            if stop_event and stop_event.is_set():
                print(f"  API-Football: interruzione alla pagina {page}")
                break

            for item in players_list:
                p_info  = item["player"]
                p_stats = item["statistics"][0] if item["statistics"] else {}

                # ── Anagrafica ────────────────────────────────────
                birth_date_obj = None
                raw_bd = p_info.get("birth", {}).get("date")
                if raw_bd:
                    try:
                        birth_date_obj = datetime.strptime(raw_bd, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                api_pos  = p_stats.get("games", {}).get("position") or "Midfielder"
                position = _POSITION_MAP.get(api_pos, "CM")

                # ── Statistiche raw (NO più stima FIFA) ───────────
                goals    = _int(p_stats.get("goals", {}).get("total"))
                assists  = _int(p_stats.get("goals", {}).get("assists"))
                minutes  = _int(p_stats.get("games", {}).get("minutes"))
                games    = _int(p_stats.get("games", {}).get("appearences"))  # sic API typo
                shots_tot= _int(p_stats.get("shots", {}).get("total"))
                shots_sot= _int(p_stats.get("shots", {}).get("on"))
                key_pass = _int(p_stats.get("passes", {}).get("key"))
                pass_acc = _float(p_stats.get("passes", {}).get("accuracy"))  # percentuale
                drib_suc = _int(p_stats.get("dribbles", {}).get("success"))
                duels_tot= _int(p_stats.get("duels", {}).get("total"))
                duels_won= _int(p_stats.get("duels", {}).get("won"))
                duels_pct= round(duels_won / duels_tot * 100, 1) if duels_tot else None
                aerial_pct = _float(p_stats.get("duels", {}).get("won"))  # API non separa aerei

                player_dict = {
                    "api_football_id":       p_info["id"],
                    "name":                  p_info["name"],
                    "birth_date":            birth_date_obj,
                    "age":                   p_info.get("age"),
                    "position":              position,
                    "club":                  p_stats.get("team", {}).get("name"),
                    "nationality":           p_info.get("nationality"),
                    # Statistiche raw stagione
                    "goals_season":          goals,
                    "assists_season":        assists,
                    "minutes_season":        minutes,
                    "games_season":          games,
                    "shots_season":          shots_tot,
                    "shots_on_target_season":shots_sot,
                    "key_passes_season":     key_pass,
                    "pass_accuracy_pct":     pass_acc,
                    "duels_total_season":    duels_tot,
                    "duels_won_season":      duels_won,
                    "duels_won_pct":         duels_pct,
                    "last_updated_api_football": datetime.utcnow(),
                }

                # Upsert su api_football_id
                existing = db.query(ScoutingPlayer).filter(
                    ScoutingPlayer.api_football_id == p_info["id"]
                ).first()

                if existing:
                    for k, v in player_dict.items():
                        setattr(existing, k, v)
                else:
                    db.add(ScoutingPlayer(**player_dict))

                imported += 1

            total_pages = data.get("paging", {}).get("total", 1)
            if page >= total_pages or page >= _FREE_PAGE_LIMIT:
                break
            page += 1

            if progress_cb:
                progress_cb(imported, None)

    db.commit()
    print(f"  API-Football: {imported} giocatori importati (stat raw)")
    return imported


def _float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _int(val) -> int:
    try:
        return int(float(val)) if val not in (None, "", "N/A") else 0
    except (ValueError, TypeError):
        return 0