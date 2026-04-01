"""
sources/sofascore_source.py  — v1.0
-------------------------------------
Servizio per scaricare dati da SofaScore (https://www.sofascore.com/).

SofaScore espone una API JSON non documentata ma stabile, accessibile
tramite le stesse chiamate che il browser fa quando navighi il sito.
Questo modulo la usa direttamente — senza Selenium né Playwright.

DATI DISPONIBILI:
  ─ Statistiche giocatore (per match / per season)
  ─ Heatmap (coordinate di posizione durante la partita)
  ─ Rating SofaScore (voto 1-10 per partita / season average)
  ─ Statistiche avanzate: duelli, dribbling, tocchi, ecc.
  ─ Partite di una squadra (calendario + risultati)
  ─ Classifiche lega

ARCHITETTURA:
  SofaScoreClient   — client HTTP basso livello (gestisce rate-limit e headers)
  SofaScoreSearch   — ricerca giocatore/squadra per nome
  SofaScorePlayer   — recupera stats + heatmap di un giocatore
  SofaScoreMatch    — recupera stats di una singola partita
  SofaScoreLeague   — recupera rounds, squadre, classifiche

INTEGRAZIONE DB:
  import_player_stats()  — aggiorna ScoutingPlayer con dati SofaScore
  import_heatmap()       — salva heatmap JSON su ScoutingPlayer.heatmap_data

ENDPOINT BASE:
  https://api.sofascore.com/api/v1/
"""

import time
import json
import hashlib
import logging
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.services.player_matcher import find_player_in_db
from app.models.models import ScoutingPlayer

log = logging.getLogger(__name__)

# ── Costanti ──────────────────────────────────────────────────────
SOFASCORE_API = "https://api.sofascore.com/api/v1"
SOFASCORE_APP = "https://www.sofascore.com"

# Mapping lega → ID SofaScore
SOFASCORE_LEAGUES = {
    "serie_a":          {"id": 23,   "season_id": 63814, "slug": "serie-a"},
    "premier_league":   {"id": 17,   "season_id": 61627, "slug": "premier-league"},
    "la_liga":          {"id": 8,    "season_id": 61643, "slug": "laliga"},
    "bundesliga":       {"id": 35,   "season_id": 63609, "slug": "bundesliga"},
    "ligue_1":          {"id": 34,   "season_id": 63684, "slug": "ligue-1"},
    "champions_league": {"id": 7,    "season_id": 61657, "slug": "uefa-champions-league"},
    "eredivisie":       {"id": 37,   "season_id": 63646, "slug": "eredivisie"},
    "primeira_liga":    {"id": 238,  "season_id": 63751, "slug": "liga-portugal"},
}

# Posizione normalizzata SofaScore → nostro standard
POSITION_MAP = {
    "G":  "GK",
    "D":  "CB",
    "M":  "CM",
    "F":  "ST",
    "GK": "GK",
    "CB": "CB", "LB": "LB", "RB": "RB",
    "CM": "CM", "DM": "DM", "AM": "AM",
    "LW": "LW", "RW": "RW", "ST": "ST",
}


# ═══════════════════════════════════════════════════════════════════
# CLIENT HTTP — gestisce headers, rate limit, retry
# ═══════════════════════════════════════════════════════════════════

class SofaScoreClient:
    """
    Client HTTP per l'API non documentata di SofaScore.
    Gestisce: headers realistici, rate-limit, retry automatici.
    """

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://www.sofascore.com",
        "Referer": "https://www.sofascore.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    def __init__(self, delay: float = 1.5, max_retries: int = 3):
        self.delay = delay
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update(self.DEFAULT_HEADERS)
        self._last_call = 0.0

    def get(self, path: str, params: dict = None) -> dict:
        """
        GET su /api/v1/{path} con rate-limit e retry automatici.

        Returns:
            dict: risposta JSON parsificata

        Raises:
            RuntimeError: se tutti i retry falliscono
        """
        url = f"{SOFASCORE_API}/{path.lstrip('/')}"
        self._throttle()

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(url, params=params, timeout=20)

                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 10))
                    log.warning(f"SofaScore rate-limit (429) — attendo {wait}s")
                    time.sleep(wait)
                    continue

                if resp.status_code == 404:
                    return {}  # Risorsa non trovata, non è un errore critico

                resp.raise_for_status()
                self._last_call = time.monotonic()
                return resp.json()

            except requests.RequestException as e:
                log.warning(f"SofaScore [{attempt}/{self.max_retries}] {url} — {e}")
                if attempt < self.max_retries:
                    time.sleep(self.delay * attempt * 2)
                else:
                    raise RuntimeError(f"SofaScore: tutti i retry falliti per {url}") from e

        return {}

    def _throttle(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)


# Istanza globale condivisa (evita di ricreare la session ogni volta)
_client: Optional[SofaScoreClient] = None


def get_client(delay: float = 1.5) -> SofaScoreClient:
    """Restituisce il client globale, creandolo se necessario."""
    global _client
    if _client is None:
        _client = SofaScoreClient(delay=delay)
    return _client


# ═══════════════════════════════════════════════════════════════════
# RICERCA — player / team per nome
# ═══════════════════════════════════════════════════════════════════

class SofaScoreSearch:

    @staticmethod
    def search_player(name: str, client: SofaScoreClient = None) -> list[dict]:
        """
        Cerca un giocatore per nome su SofaScore.

        Returns:
            Lista di dict con: id, name, team, position, nationality, slug
        """
        c = client or get_client()
        data = c.get("search/all", params={"q": name, "page": 0})

        results = []
        for item in data.get("results", []):
            if item.get("type") != "player":
                continue
            entity = item.get("entity", {})
            team   = entity.get("team", {})
            results.append({
                "id":          entity.get("id"),
                "name":        entity.get("name", ""),
                "short_name":  entity.get("shortName", ""),
                "slug":        entity.get("slug", ""),
                "position":    entity.get("position", ""),
                "nationality": entity.get("country", {}).get("name", ""),
                "team_id":     team.get("id"),
                "team_name":   team.get("name", ""),
                "team_slug":   team.get("slug", ""),
            })
        return results

    @staticmethod
    def search_team(name: str, client: SofaScoreClient = None) -> list[dict]:
        """Cerca una squadra per nome."""
        c = client or get_client()
        data = c.get("search/all", params={"q": name, "page": 0})

        results = []
        for item in data.get("results", []):
            if item.get("type") != "team":
                continue
            entity = item.get("entity", {})
            results.append({
                "id":       entity.get("id"),
                "name":     entity.get("name", ""),
                "slug":     entity.get("slug", ""),
                "country":  entity.get("country", {}).get("name", ""),
            })
        return results

    @staticmethod
    def find_player_id(name: str, team_name: str = "", client: SofaScoreClient = None) -> Optional[int]:
        """
        Trova l'ID SofaScore di un giocatore, opzionalmente filtrando per team.
        Restituisce None se non trovato.
        """
        results = SofaScoreSearch.search_player(name, client)
        if not results:
            return None

        if team_name:
            normalized_team = team_name.lower()
            for r in results:
                if normalized_team in r.get("team_name", "").lower():
                    return r["id"]

        # Fallback: prendi il primo risultato
        return results[0]["id"] if results else None


# ═══════════════════════════════════════════════════════════════════
# PLAYER — statistiche stagionali, per partita, heatmap
# ═══════════════════════════════════════════════════════════════════

class SofaScorePlayer:

    @staticmethod
    def get_profile(player_id: int, client: SofaScoreClient = None) -> dict:
        """
        Profilo anagrafico del giocatore.

        Returns:
            dict con: name, position, age, height, weight, nationality,
                      market_value, preferred_foot, jersey_number, team
        """
        c = client or get_client()
        data = c.get(f"player/{player_id}")
        p = data.get("player", {})
        team = p.get("team", {})

        return {
            "id":              p.get("id"),
            "name":            p.get("name", ""),
            "short_name":      p.get("shortName", ""),
            "slug":            p.get("slug", ""),
            "position":        p.get("position", ""),
            "age":             p.get("age"),
            "height":          p.get("height"),
            "weight":          p.get("weight"),
            "nationality":     p.get("country", {}).get("name", ""),
            "preferred_foot":  p.get("preferredFoot", ""),
            "jersey_number":   p.get("jerseyNumber"),
            "market_value":    p.get("proposedMarketValue"),
            "market_currency": p.get("proposedMarketValueRaw", {}).get("currency", "EUR"),
            "team_id":         team.get("id"),
            "team_name":       team.get("name", ""),
            "sofascore_url":   f"https://www.sofascore.com/player/{p.get('slug', '')}/{p.get('id', '')}",
        }

    @staticmethod
    def get_season_stats(
        player_id: int,
        tournament_id: int,
        season_id: int,
        client: SofaScoreClient = None,
    ) -> dict:
        """
        Statistiche aggregate di un giocatore per una stagione.

        Args:
            player_id:     ID SofaScore del giocatore
            tournament_id: ID del torneo (es. 23 per Serie A)
            season_id:     ID della stagione (es. 63814 per Serie A 24/25)

        Returns:
            dict con tutte le statistiche disponibili (varia per posizione):
              - rating, goals, assists, minutes_played
              - shots, shots_on_target, key_passes, big_chances_created
              - accurate_passes, pass_accuracy, long_balls
              - dribble_attempts, dribble_success
              - tackles, interceptions, clearances, errors_leading_to_shot
              - aerial_duels_won, ground_duels_won
              - yellow_cards, red_cards
              → GK: saves, goals_conceded, save_percentage, clean_sheets
        """
        c = client or get_client()
        data = c.get(
            f"player/{player_id}/tournaments/{tournament_id}/seasons/{season_id}/statistics/overall"
        )
        raw = data.get("statistics", {})
        return _parse_player_stats(raw)

    @staticmethod
    def get_heatmap(
        player_id: int,
        tournament_id: int,
        season_id: int,
        client: SofaScoreClient = None,
    ) -> dict:
        """
        Heatmap di posizione del giocatore in una stagione.

        Returns:
            dict con:
              - points: lista di {x, y, value} (coordinate 0-100)
              - raw: dati JSON originali di SofaScore (per rendering avanzato)

        Il campo `points` può essere usato per disegnare la heatmap
        su un campo da calcio (coordinate normalizzate 0-100).
        """
        c = client or get_client()
        data = c.get(
            f"player/{player_id}/heatmap/{tournament_id}/season/{season_id}/overall"
        )
        points = data.get("heatmap", [])
        return {
            "player_id":     player_id,
            "tournament_id": tournament_id,
            "season_id":     season_id,
            "points":        points,          # [{x, y, value}, ...]
            "point_count":   len(points),
            "raw":           data,            # JSON completo per rendering
        }

    @staticmethod
    def get_match_stats(player_id: int, event_id: int, client: SofaScoreClient = None) -> dict:
        """
        Statistiche di un giocatore in una singola partita.

        Args:
            player_id: ID SofaScore del giocatore
            event_id:  ID della partita (event) su SofaScore

        Returns:
            dict con stats individuali + rating per quella partita
        """
        c = client or get_client()
        data = c.get(f"event/{event_id}/player/{player_id}/statistics")
        raw = data.get("statistics", {})
        return _parse_player_stats(raw)

    @staticmethod
    def get_recent_matches(player_id: int, client: SofaScoreClient = None) -> list[dict]:
        """
        Ultime partite del giocatore con rating e stats essenziali.

        Returns:
            Lista di dict con: event_id, date, home_team, away_team,
                               home_score, away_score, rating, minutes_played,
                               goals, assists, yellow_card, red_card
        """
        c = client or get_client()
        data = c.get(f"player/{player_id}/events/last/0")  # page 0 = più recenti
        events = data.get("events", [])

        matches = []
        for ev in events:
            home = ev.get("homeTeam", {})
            away = ev.get("awayTeam", {})
            score = ev.get("homeScore", {})
            player_data = ev.get("playerStatistics", {})

            matches.append({
                "event_id":       ev.get("id"),
                "slug":           ev.get("slug", ""),
                "date":           datetime.fromtimestamp(ev.get("startTimestamp", 0)).isoformat() if ev.get("startTimestamp") else None,
                "home_team":      home.get("name", ""),
                "away_team":      away.get("name", ""),
                "home_score":     score.get("current"),
                "away_score":     ev.get("awayScore", {}).get("current"),
                "rating":         player_data.get("rating"),
                "minutes_played": player_data.get("minutesPlayed"),
                "goals":          player_data.get("goals", 0),
                "assists":        player_data.get("goalAssist", 0),
                "yellow_card":    player_data.get("yellowCards", 0) > 0,
                "red_card":       player_data.get("redCards", 0) > 0,
                "sofascore_url":  f"https://www.sofascore.com/{ev.get('slug', '')}/{ev.get('customId', '')}",
            })
        return matches

    @staticmethod
    def get_transfer_history(player_id: int, client: SofaScoreClient = None) -> list[dict]:
        """
        Storico trasferimenti del giocatore.

        Returns:
            Lista di dict con: date, from_team, to_team, transfer_fee, type
        """
        c = client or get_client()
        data = c.get(f"player/{player_id}/transfer-history")
        transfers = data.get("transferHistory", [])

        result = []
        for t in transfers:
            result.append({
                "date":      t.get("transferDateTimestamp"),
                "from_team": t.get("fromTeam", {}).get("name", ""),
                "to_team":   t.get("toTeam", {}).get("name", ""),
                "fee":       t.get("transferFee"),
                "fee_currency": t.get("transferFeeRaw", {}).get("currency", "EUR"),
                "type":      t.get("type", ""),   # "transfer", "loan", "loan_return", "free"
            })
        return result

    @staticmethod
    def get_national_team_stats(player_id: int, client: SofaScoreClient = None) -> dict:
        """Statistiche in nazionale."""
        c = client or get_client()
        data = c.get(f"player/{player_id}/national-team-statistics")
        return data.get("statistics", {})


# ═══════════════════════════════════════════════════════════════════
# MATCH — statistiche di una singola partita
# ═══════════════════════════════════════════════════════════════════

class SofaScoreMatch:

    @staticmethod
    def get_lineups(event_id: int, client: SofaScoreClient = None) -> dict:
        """
        Formazioni di una partita con rating e stats per ogni giocatore.

        Returns:
            dict con: home_lineup, away_lineup, formation_home, formation_away
            Ogni giocatore ha: id, name, position, rating, minutes_played,
                               goals, assists, yellow_card, red_card
        """
        c = client or get_client()
        data = c.get(f"event/{event_id}/lineups")

        def parse_lineup(side_data):
            if not side_data:
                return []
            players = []
            for p in side_data.get("players", []):
                player = p.get("player", {})
                stats  = p.get("statistics", {})
                players.append({
                    "id":             player.get("id"),
                    "name":           player.get("name", ""),
                    "position":       p.get("position", ""),
                    "jersey_number":  p.get("jerseyNumber"),
                    "substitute":     p.get("substitute", False),
                    "captain":        p.get("captain", False),
                    "rating":         stats.get("rating"),
                    "minutes_played": stats.get("minutesPlayed"),
                    "goals":          stats.get("goals", 0),
                    "assists":        stats.get("goalAssist", 0),
                    "yellow_card":    stats.get("yellowCards", 0) > 0 if stats.get("yellowCards") else False,
                    "red_card":       stats.get("redCards", 0) > 0 if stats.get("redCards") else False,
                    "shots":          stats.get("onTargetScoringAttempt", 0),
                    "key_passes":     stats.get("keyPass", 0),
                    "dribbles":       stats.get("successfulDribbles", 0),
                    "tackles":        stats.get("tackles", 0),
                })
            return players

        home = data.get("home", {})
        away = data.get("away", {})

        return {
            "formation_home": home.get("formation", ""),
            "formation_away": away.get("formation", ""),
            "home_lineup":    parse_lineup(home),
            "away_lineup":    parse_lineup(away),
        }

    @staticmethod
    def get_heatmap(event_id: int, player_id: int, client: SofaScoreClient = None) -> dict:
        """Heatmap di un giocatore in una singola partita."""
        c = client or get_client()
        data = c.get(f"event/{event_id}/player/{player_id}/heatmap")
        return {
            "player_id": player_id,
            "event_id":  event_id,
            "points":    data.get("heatmap", []),
            "raw":       data,
        }

    @staticmethod
    def get_incidents(event_id: int, client: SofaScoreClient = None) -> list[dict]:
        """
        Cronologia degli eventi della partita (gol, cartellini, sostituzioni, VAR).
        """
        c = client or get_client()
        data = c.get(f"event/{event_id}/incidents")
        return data.get("incidents", [])

    @staticmethod
    def get_momentum(event_id: int, client: SofaScoreClient = None) -> list[dict]:
        """
        Momentum della partita (controllo palla per minuto).
        Restituisce lista di {minute, home, away} con valori -100..+100.
        """
        c = client or get_client()
        data = c.get(f"event/{event_id}/graph")
        return data.get("graphPoints", [])


# ═══════════════════════════════════════════════════════════════════
# LEAGUE — squadre, calendari, classifiche, top giocatori
# ═══════════════════════════════════════════════════════════════════

class SofaScoreLeague:

    @staticmethod
    def get_standings(league_key: str, client: SofaScoreClient = None) -> list[dict]:
        """
        Classifica attuale di una lega.

        Returns:
            Lista di dict con: position, team_name, played, won, drawn, lost,
                               goals_for, goals_against, goal_difference, points
        """
        league = _get_league(league_key)
        c = client or get_client()
        data = c.get(
            f"unique-tournament/{league['id']}/season/{league['season_id']}/standings/total"
        )

        rows = data.get("standings", [{}])[0].get("rows", [])
        result = []
        for row in rows:
            team = row.get("team", {})
            result.append({
                "position":         row.get("position"),
                "team_id":          team.get("id"),
                "team_name":        team.get("name", ""),
                "team_slug":        team.get("slug", ""),
                "played":           row.get("matches"),
                "won":              row.get("wins"),
                "drawn":            row.get("draws"),
                "lost":             row.get("losses"),
                "goals_for":        row.get("scoresFor"),
                "goals_against":    row.get("scoresAgainst"),
                "goal_difference":  row.get("scoreDifference"),
                "points":           row.get("points"),
                "form":             row.get("form", []),   # ['W', 'D', 'L', ...]
            })
        return result

    @staticmethod
    def get_top_players(
        league_key: str,
        stat: str = "rating",
        client: SofaScoreClient = None,
    ) -> list[dict]:
        """
        Top giocatori di una lega per una statistica.

        Args:
            stat: "rating" | "goals" | "assists" | "goals_assists" |
                  "shots" | "tackles" | "saves"

        Returns:
            Lista di giocatori con nome, team, valore statistica
        """
        stat_map = {
            "rating":        "rating",
            "goals":         "goals",
            "assists":       "assists",
            "goals_assists": "goalsAssists",
            "shots":         "shots",
            "tackles":       "tackles",
            "saves":         "saves",
            "key_passes":    "keyPasses",
            "dribbles":      "successfulDribbles",
        }
        api_stat = stat_map.get(stat, "rating")

        league = _get_league(league_key)
        c = client or get_client()
        data = c.get(
            f"unique-tournament/{league['id']}/season/{league['season_id']}/top-players/{api_stat}"
        )

        players = []
        for item in data.get("topPlayers", []):
            p = item.get("player", {})
            team = p.get("team", {})
            players.append({
                "id":        p.get("id"),
                "name":      p.get("name", ""),
                "team":      team.get("name", ""),
                "team_id":   team.get("id"),
                "position":  p.get("position", ""),
                "value":     item.get("statistics", {}).get(api_stat),
                "stat":      stat,
            })
        return players

    @staticmethod
    def get_team_matches(
        team_id: int,
        league_id: int,
        season_id: int,
        client: SofaScoreClient = None,
    ) -> list[dict]:
        """
        Tutte le partite di una squadra in una stagione.
        """
        c = client or get_client()
        data = c.get(f"team/{team_id}/events/season/{season_id}/page/0")
        events = data.get("events", [])

        matches = []
        for ev in events:
            home = ev.get("homeTeam", {})
            away = ev.get("awayTeam", {})
            matches.append({
                "event_id":    ev.get("id"),
                "date":        datetime.fromtimestamp(ev.get("startTimestamp", 0)).isoformat() if ev.get("startTimestamp") else None,
                "home_team":   home.get("name", ""),
                "away_team":   away.get("name", ""),
                "home_score":  ev.get("homeScore", {}).get("current"),
                "away_score":  ev.get("awayScore", {}).get("current"),
                "status":      ev.get("status", {}).get("description", ""),
                "slug":        ev.get("slug", ""),
            })
        return sorted(matches, key=lambda x: x["date"] or "")


# ═══════════════════════════════════════════════════════════════════
# INTEGRAZIONE DB — aggiornamento ScoutingPlayer
# ═══════════════════════════════════════════════════════════════════

def import_player_stats(
    db: Session,
    league_key: str = "serie_a",
    min_minutes: int = 200,
    progress_cb=None,
    stop_event=None,
) -> dict:
    """
    Importa le statistiche SofaScore per tutti i giocatori nel DB
    che appartengono alla lega specificata.

    Aggiorna i campi:
      - sofascore_id, sofascore_rating
      - goals_season, assists_season, minutes_season
      - shots_season, key_passes_season
      - tackles_season, interceptions_season
      - dribbles_season (se il campo esiste nel modello)

    Args:
        league_key:   chiave lega (es. "serie_a")
        min_minutes:  minimo minuti giocati per essere incluso
        progress_cb:  callback(current, total) per progress bar

    Returns:
        dict con: enriched, not_found, errors, total
    """
    league = _get_league(league_key)
    client = get_client()

    # Recupera tutti i giocatori del DB con minuti sufficienti
    players = db.query(ScoutingPlayer).filter(
        ScoutingPlayer.minutes_season >= min_minutes
    ).all()

    if not players:
        return {"enriched": 0, "not_found": 0, "errors": 0, "total": 0}

    enriched = 0
    not_found = 0
    errors = 0
    total = len(players)

    log.info(f"SofaScore: aggiornamento {total} giocatori per {league_key}")

    for idx, player in enumerate(players):
        if stop_event and stop_event.is_set():
            break

        try:
            # 1. Cerca l'ID SofaScore se non lo abbiamo
            sofa_id = getattr(player, "sofascore_id", None)

            if not sofa_id:
                sofa_id = SofaScoreSearch.find_player_id(
                    player.name,
                    player.club or "",
                    client=client,
                )
                if not sofa_id:
                    not_found += 1
                    continue

                if hasattr(player, "sofascore_id"):
                    player.sofascore_id = sofa_id

            # 2. Recupera le statistiche stagionali
            stats = SofaScorePlayer.get_season_stats(
                player_id=sofa_id,
                tournament_id=league["id"],
                season_id=league["season_id"],
                client=client,
            )

            if not stats:
                not_found += 1
                continue

            # 3. Aggiorna i campi del player
            _apply_sofa_stats(player, stats, sofa_id)
            enriched += 1

            # Commit ogni 50 giocatori
            if idx % 50 == 0:
                db.commit()
                log.info(f"SofaScore: {idx}/{total} ({enriched} arricchiti, {not_found} non trovati)")

            if progress_cb and idx % 10 == 0:
                progress_cb(idx + 1, total)

        except Exception as e:
            log.error(f"SofaScore: errore per {player.name} — {e}")
            errors += 1

    db.commit()
    log.info(f"SofaScore: completato — {enriched} arricchiti, {not_found} non trovati, {errors} errori")

    return {
        "enriched":  enriched,
        "not_found": not_found,
        "errors":    errors,
        "total":     total,
        "league":    league_key,
    }


def import_heatmap(
    db: Session,
    player_id_db: int,
    league_key: str = "serie_a",
    client: SofaScoreClient = None,
) -> Optional[dict]:
    """
    Recupera e salva la heatmap SofaScore per un singolo giocatore.

    Args:
        player_id_db: ID nel nostro DB (ScoutingPlayer.id)
        league_key:   chiave lega

    Returns:
        dict con la heatmap, oppure None se il giocatore non ha SofaScore ID
    """
    player = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == player_id_db).first()
    if not player:
        raise ValueError(f"Giocatore {player_id_db} non trovato nel DB")

    sofa_id = getattr(player, "sofascore_id", None)
    if not sofa_id:
        sofa_id = SofaScoreSearch.find_player_id(player.name, player.club or "")
        if not sofa_id:
            return None
        if hasattr(player, "sofascore_id"):
            player.sofascore_id = sofa_id
            db.commit()

    league = _get_league(league_key)
    c = client or get_client()

    heatmap = SofaScorePlayer.get_heatmap(
        player_id=sofa_id,
        tournament_id=league["id"],
        season_id=league["season_id"],
        client=c,
    )

    # Salva il JSON della heatmap nel player (se il campo esiste)
    if hasattr(player, "heatmap_data") and heatmap.get("points"):
        player.heatmap_data = json.dumps(heatmap)
        db.commit()
        log.info(f"SofaScore heatmap: {len(heatmap['points'])} punti salvati per {player.name}")

    return heatmap


def get_player_full_report(
    player_name: str,
    team_name: str = "",
    league_key: str = "serie_a",
    client: SofaScoreClient = None,
) -> dict:
    """
    Report completo di un giocatore da SofaScore.
    Non richiede accesso al DB — utile per anteprima o scouting ad hoc.

    Returns:
        dict con: profile, season_stats, heatmap, recent_matches, transfers
    """
    c = client or get_client()
    league = _get_league(league_key)

    # 1. Cerca il giocatore
    results = SofaScoreSearch.search_player(player_name, c)
    if not results:
        return {"error": f"Giocatore '{player_name}' non trovato su SofaScore"}

    # Filtro per team se specificato
    player_data = results[0]
    if team_name:
        for r in results:
            if team_name.lower() in r.get("team_name", "").lower():
                player_data = r
                break

    sofa_id = player_data["id"]
    log.info(f"SofaScore report: {player_data['name']} (id={sofa_id}) per {league_key}")

    # 2. Raccoglie tutti i dati in parallelo (in sequenza per rispettare rate-limit)
    profile         = SofaScorePlayer.get_profile(sofa_id, c)
    season_stats    = SofaScorePlayer.get_season_stats(sofa_id, league["id"], league["season_id"], c)
    heatmap         = SofaScorePlayer.get_heatmap(sofa_id, league["id"], league["season_id"], c)
    recent_matches  = SofaScorePlayer.get_recent_matches(sofa_id, c)
    transfers       = SofaScorePlayer.get_transfer_history(sofa_id, c)

    return {
        "player_id":      sofa_id,
        "profile":        profile,
        "season_stats":   season_stats,
        "heatmap":        heatmap,
        "recent_matches": recent_matches[:10],  # ultime 10 partite
        "transfers":      transfers,
        "sofascore_url":  profile.get("sofascore_url", ""),
        "fetched_at":     datetime.utcnow().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════
# HELPERS INTERNI
# ═══════════════════════════════════════════════════════════════════

def _get_league(league_key: str) -> dict:
    league = SOFASCORE_LEAGUES.get(league_key)
    if not league:
        raise ValueError(
            f"Lega '{league_key}' non supportata. "
            f"Opzioni: {list(SOFASCORE_LEAGUES.keys())}"
        )
    return league


def _parse_player_stats(raw: dict) -> dict:
    """
    Normalizza le statistiche raw di SofaScore in un dict standard.
    Funziona sia per stats stagionali che per stats di singola partita.
    """
    if not raw:
        return {}

    return {
        # Rating
        "rating":                    _safe_float(raw.get("rating")),
        "sofascore_rating":          _safe_float(raw.get("rating")),

        # Minuti e partite
        "minutes_played":            _safe_int(raw.get("minutesPlayed")),
        "matches_played":            _safe_int(raw.get("appearances")),
        "games_started":             _safe_int(raw.get("matchesStarted")),

        # Contributi offensivi
        "goals":                     _safe_int(raw.get("goals")),
        "assists":                   _safe_int(raw.get("goalAssist")),
        "goals_assists":             _safe_int(raw.get("goalsAssists")),
        "big_chances_created":       _safe_int(raw.get("bigChanceCreated")),
        "big_chances_missed":        _safe_int(raw.get("bigChanceMissed")),
        "penalty_goals":             _safe_int(raw.get("penaltyConversion")),

        # Tiri
        "shots":                     _safe_int(raw.get("shotFromSetPiece", 0) + raw.get("onTargetScoringAttempt", 0) + raw.get("blockedScoringAttempt", 0)),
        "shots_on_target":           _safe_int(raw.get("onTargetScoringAttempt")),
        "shots_off_target":          _safe_int(raw.get("missedBalls")),
        "blocked_shots":             _safe_int(raw.get("blockedScoringAttempt")),

        # Passaggi
        "key_passes":                _safe_int(raw.get("keyPass")),
        "accurate_passes":           _safe_int(raw.get("accuratePasses")),
        "total_passes":              _safe_int(raw.get("totalPasses")),
        "pass_accuracy":             _safe_float(raw.get("accuratePassesPercentage")),
        "long_balls_accurate":       _safe_int(raw.get("accurateLongBalls")),
        "crosses_accurate":          _safe_int(raw.get("accurateCrosses")),

        # Dribbling e duelli
        "dribble_attempts":          _safe_int(raw.get("attemptedDribbles")),
        "dribbles_won":              _safe_int(raw.get("successfulDribbles")),
        "dribble_success_rate":      _safe_float(raw.get("dribbleSuccessRatio")),
        "duels_won":                 _safe_int(raw.get("duelsWon")),
        "duels_total":               _safe_int(raw.get("totalDuels")),
        "aerial_duels_won":          _safe_int(raw.get("aerialDuelsWon")),
        "ground_duels_won":          _safe_int(raw.get("groundDuelsWon")),

        # Difesa
        "tackles":                   _safe_int(raw.get("tackles")),
        "interceptions":             _safe_int(raw.get("interceptions")),
        "clearances":                _safe_int(raw.get("clearances")),
        "errors_leading_to_shot":    _safe_int(raw.get("errorLeadToShot")),
        "errors_leading_to_goal":    _safe_int(raw.get("errorLeadToGoal")),

        # Disciplina
        "yellow_cards":              _safe_int(raw.get("yellowCards")),
        "red_cards":                 _safe_int(raw.get("redCards")),
        "fouls_committed":           _safe_int(raw.get("fouls")),
        "fouls_suffered":            _safe_int(raw.get("wasFouled")),
        "offsides":                  _safe_int(raw.get("offsides")),

        # GK specifici
        "saves":                     _safe_int(raw.get("saves")),
        "goals_conceded":            _safe_int(raw.get("goalsConceded")),
        "save_percentage":           _safe_float(raw.get("savedShotsFromInsideTheBox")),
        "clean_sheets":              _safe_int(raw.get("cleanSheet")),
        "high_claims":               _safe_int(raw.get("highClaims")),
        "punches":                   _safe_int(raw.get("punches")),
    }


def _apply_sofa_stats(player: ScoutingPlayer, stats: dict, sofa_id: int):
    """Applica le statistiche SofaScore al record ScoutingPlayer."""
    field_map = {
        "sofascore_id":          sofa_id,
        "sofascore_rating":      stats.get("sofascore_rating"),
        "goals_season":          stats.get("goals"),
        "assists_season":        stats.get("assists"),
        "minutes_season":        stats.get("minutes_played"),
        "shots_season":          stats.get("shots"),
        "key_passes_season":     stats.get("key_passes"),
        "games_season":          stats.get("matches_played"),
    }

    # Campi opzionali (potrebbero non esistere nel modello)
    optional_map = {
        "tackles_season":        stats.get("tackles"),
        "interceptions_season":  stats.get("interceptions"),
        "dribbles_season":       stats.get("dribbles_won"),
        "big_chances_created":   stats.get("big_chances_created"),
        "aerial_duels_won":      stats.get("aerial_duels_won"),
        "pass_accuracy":         stats.get("pass_accuracy"),
    }

    for field, value in {**field_map, **optional_map}.items():
        if value is not None and hasattr(player, field):
            setattr(player, field, value)

    if hasattr(player, "last_updated_sofascore"):
        player.last_updated_sofascore = datetime.utcnow()


def _safe_float(val) -> Optional[float]:
    try:
        return round(float(val), 4) if val is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None