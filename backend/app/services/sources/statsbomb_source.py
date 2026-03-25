"""
sources/statsbomb_source.py
----------------------------
Dati event-level gratuiti da StatsBomb Open Data.
https://github.com/statsbomb/open-data

Cosa fornisce:
  - xG per tiro (statsbomb_xg)
  - xA tramite key pass / shot assist
  - Minuti giocati (da lineup)
  - Aggregazione per90 di xG e xA

Funzionamento:
  1. Scarica competitions.json per validare comp_id/season_id
  2. Scarica matches/{comp_id}/{season_id}.json
  3. Per ogni partita: scarica events/{match_id}.json e lineups/{match_id}.json
  4. Aggrega xG, xA, minuti per giocatore
  5. Arricchisce i ScoutingPlayer esistenti nel DB (match per nome)

Competizioni open data disponibili (esempi):
  competition_id=12  → Serie A
  competition_id=2   → Premier League  (UEFA Champions League era)
  competition_id=16  → Champions League
  competition_id=11  → La Liga
  competition_id=9   → Bundesliga
  competition_id=7   → Ligue 1

Usa list_competitions() per vedere tutte le combinazioni disponibili.
"""

import httpx
from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


async def list_competitions() -> list[dict]:
    """
    Ritorna la lista completa di competizioni/stagioni disponibili
    nello StatsBomb Open Data.
    """
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{BASE_URL}/competitions.json")
        resp.raise_for_status()
        competitions = resp.json()

    return sorted(
        [
            {
                "competition_id": c["competition_id"],
                "season_id":      c["season_id"],
                "name":           c["competition_name"],
                "season":         c["season_name"],
                "country":        c["country_name"],
            }
            for c in competitions
        ],
        key=lambda x: (x["name"], x["season"]),
    )


async def fetch_from_statsbomb(
    db: Session,
    competition_id: int,
    season_id: int,
    max_matches: int = 50,
    progress_cb=None,
) -> dict:
    """
    Scarica event data StatsBomb e arricchisce i giocatori nel DB con xG/xA.

    Args:
        competition_id: ID competizione StatsBomb (es. 12 per Serie A)
        season_id:      ID stagione StatsBomb (es. 27 per 2015/16)
        max_matches:    limite partite da processare (evita rate limit GitHub)

    Ritorna:
        dict con matches_processed, players_with_stats, players_enriched
    """
    async with httpx.AsyncClient(timeout=30) as client:

        # ── 1. Valida combinazione comp/season ──
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
                for c in competitions
                if c["competition_id"] == competition_id
            ]
            raise ValueError(
                f"competition_id={competition_id} + season_id={season_id} non trovata "
                f"in StatsBomb open data.\n"
                f"Stagioni disponibili per competition_id={competition_id}:\n"
                + "\n".join(available[:15])
            )

        # ── 2. Lista partite ──
        matches_resp = await client.get(
            f"{BASE_URL}/matches/{competition_id}/{season_id}.json"
        )
        matches_resp.raise_for_status()
        matches = matches_resp.json()[:max_matches]
        print(f"  → StatsBomb: {len(matches)} partite da processare...")

        # ── 3. Aggrega stats per giocatore ──
        # player_id → {name, xg, xa, minutes, shots, key_passes}
        player_stats: dict[str, dict] = {}

        for idx, match in enumerate(matches):
            match_id = match["match_id"]

            # Events
            try:
                ev_resp = await client.get(f"{BASE_URL}/events/{match_id}.json")
                ev_resp.raise_for_status()
                events = ev_resp.json()
            except Exception as e:
                print(f"  ⚠ Salto partita {match_id}: {e}")
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
                        "minutes":    0,
                        "shots":      0,
                        "key_passes": 0,
                    }

                ev_type = ev.get("type", {}).get("name", "")

                if ev_type == "Shot":
                    xg_val = ev.get("shot", {}).get("statsbomb_xg", 0) or 0
                    player_stats[pid]["xg"] += xg_val
                    player_stats[pid]["shots"] += 1

                elif ev_type == "Pass":
                    pass_ev = ev.get("pass", {})
                    if pass_ev.get("goal_assist") or pass_ev.get("shot_assist"):
                        player_stats[pid]["xa"] += 1
                        player_stats[pid]["key_passes"] += 1

            # Lineups → minuti approssimati
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

        print(f"  → StatsBomb: stats aggregate per {len(player_stats)} giocatori")

        # ── 4. Arricchisci nel DB ──
        enriched = 0
        for pid, stats in player_stats.items():
            minutes = stats["minutes"] or 90
            per90   = 90 / minutes

            xg_per90 = round(stats["xg"] * per90, 4)
            xa_per90 = round(stats["xa"] * per90, 4)

            name = stats["name"]
            player = (
                db.query(ScoutingPlayer)
                .filter(ScoutingPlayer.name.ilike(f"%{name}%"))
                .first()
            )
            if player:
                player.xg_per90 = xg_per90
                player.xa_per90 = xa_per90
                enriched += 1

        db.commit()
        print(f"  → StatsBomb: {enriched} giocatori arricchiti con xG/xA")

        return {
            "matches_processed":   len(matches),
            "players_with_stats":  len(player_stats),
            "players_enriched":    enriched,
        }