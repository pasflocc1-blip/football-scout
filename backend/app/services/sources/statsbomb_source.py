"""
sources/statsbomb_source.py — Fase 1 pipeline oggettivo
-------------------------------------------------------
Fix rispetto alla versione precedente:
  - Corretto bug: xg_val usata nel blocco Pass prima di essere definita
    (UnboundLocalError). Ora xg_val ha default 0.0 a inizio ciclo evento.
  - Salva xGChain/90 e xGBuildup/90
  - Aggiorna last_updated_statsbomb
"""

import httpx
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer
from app.services.player_matcher import find_player_in_db

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


async def list_competitions() -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{BASE_URL}/competitions.json")
        resp.raise_for_status()
        competitions = resp.json()
    return sorted(
        [{"competition_id": c["competition_id"], "season_id": c["season_id"],
          "name": c["competition_name"], "season": c["season_name"],
          "country": c["country_name"]} for c in competitions],
        key=lambda x: (x["name"], x["season"]),
    )


async def fetch_from_statsbomb(
    db: Session,
    competition_id: int,
    season_id: int,
    max_matches: int = 300,
    progress_cb=None,
    stop_event=None,
) -> dict:

    async with httpx.AsyncClient(timeout=30) as client:

        comp_resp = await client.get(f"{BASE_URL}/competitions.json")
        comp_resp.raise_for_status()
        competitions = comp_resp.json()

        valid = any(
            c["competition_id"] == competition_id and c["season_id"] == season_id
            for c in competitions
        )
        if not valid:
            available = [
                f"season_id={c['season_id']} ({c['season_name']})"
                for c in competitions if c["competition_id"] == competition_id
            ]
            raise ValueError(
                f"competition_id={competition_id} + season_id={season_id} non trovata.\n"
                f"Disponibili: {', '.join(available[:10])}"
            )

        matches_resp = await client.get(
            f"{BASE_URL}/matches/{competition_id}/{season_id}.json"
        )
        matches_resp.raise_for_status()
        matches = matches_resp.json()[:max_matches]
        now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        print(f"  StatsBomb: [{now_str}] - {len(matches)} partite da processare")

        player_stats: dict[str, dict] = {}

        for idx, match in enumerate(matches):
            if stop_event and stop_event.is_set():
                print(f"  StatsBomb: interruzione alla partita {idx+1}/{len(matches)}")
                break
            now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            print(f"  StatsBomb: [{now_str}] - Elaborazione partita {idx+1}/{len(matches)}")

            match_id = match["match_id"]

            try:
                ev_resp = await client.get(f"{BASE_URL}/events/{match_id}.json")
                ev_resp.raise_for_status()
                events = ev_resp.json()
            except Exception as e:
                now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                print(f"  StatsBomb: [{now_str}] - Skip partita {match_id}: {e}")
                continue

            for ev in events:
                player = ev.get("player", {})
                pid    = str(player.get("id", ""))
                pname  = player.get("name", "")
                if not pid:
                    continue

                if pid not in player_stats:
                    player_stats[pid] = {
                        "name":       pname,
                        "xg":         0.0,
                        "xa":         0.0,
                        "npxg":       0.0,
                        "xgchain":    0.0,
                        "xgbuildup":  0.0,
                        "minutes":    0,
                        "shots":      0,
                        "key_passes": 0,
                    }

                ev_type = ev.get("type", {}).get("name", "")

                # FIX: xg_val inizializzata a 0 per ogni evento
                # così è sempre definita indipendentemente dall'ordine degli eventi
                xg_val = 0.0

                if ev_type == "Shot":
                    shot_data = ev.get("shot", {})
                    xg_val    = float(shot_data.get("statsbomb_xg", 0) or 0)
                    is_penalty = shot_data.get("technique", {}).get("name") == "Penalty"

                    player_stats[pid]["xg"]      += xg_val
                    player_stats[pid]["npxg"]    += 0.0 if is_penalty else xg_val
                    player_stats[pid]["xgchain"] += xg_val
                    player_stats[pid]["shots"]   += 1

                elif ev_type == "Pass":
                    pass_ev = ev.get("pass", {})
                    if pass_ev.get("goal_assist") or pass_ev.get("shot_assist"):
                        player_stats[pid]["xa"]         += 1
                        player_stats[pid]["key_passes"] += 1
                        # xGBuildup proxy: ogni assist conta 0.5 come contributo
                        # al build-up (non abbiamo il valore xG del tiro qui)
                        player_stats[pid]["xgbuildup"]  += 0.5

            # Lineups → minuti
            try:
                lu_resp = await client.get(f"{BASE_URL}/lineups/{match_id}.json")
                lu_resp.raise_for_status()
                lineups = lu_resp.json()
                for team_lineup in lineups:
                    for pl in team_lineup.get("lineup", []):
                        pid = str(pl.get("player_id", ""))
                        if pid in player_stats:
                            player_stats[pid]["minutes"] += 90
            except Exception:
                pass

            if progress_cb and idx % 5 == 0:
                progress_cb(idx + 1, len(matches))

        now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        print(f"  StatsBomb: [{now_str}] - Statistiche aggregate per {len(player_stats)} giocatori")

        enriched  = 0
        not_found = 0

        for pid, stats in player_stats.items():
            minutes  = max(stats["minutes"], 1)
            per90    = 90 / minutes

            xg_per90      = round(stats["xg"]       * per90, 4)
            xa_per90      = round(stats["xa"]        * per90, 4)
            npxg_per90    = round(stats["npxg"]      * per90, 4)
            xgchain_per90 = round(stats["xgchain"]   * per90, 4)
            xgbuild_per90 = round(stats["xgbuildup"] * per90, 4)

            player = find_player_in_db(db, stats["name"], "")
            if not player:
                not_found += 1
                continue

            player.xg_per90        = xg_per90
            player.xa_per90        = xa_per90
            player.npxg_per90      = npxg_per90
            player.xgchain_per90   = xgchain_per90
            player.xgbuildup_per90 = xgbuild_per90
            player.last_updated_statsbomb = datetime.utcnow()
            enriched += 1

        db.commit()
        print(f"  StatsBomb: {enriched} arricchiti, {not_found} non abbinati")

        return {
            "matches_processed":   len(matches),
            "players_with_stats":  len(player_stats),
            "players_enriched":    enriched,
            "players_not_matched": not_found,
        }