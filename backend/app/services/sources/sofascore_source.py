"""
app/services/sources/sofascore_source.py  — v2.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MODIFICHE rispetto alla v1:
  • _apply_to_player() è stata RIMOSSA.
  • I dati statistici vengono ora scritti in player_sofascore_stats
    (nuova tabella) tramite _upsert_sofascore_stats().
  • scouting_players conserva SOLO anagrafica + identificatori +
    cache sofascore_rating (denormalizzata per la UI senza join).
  • import_player_stats() e import_single_player() aggiornati.

Tutto il resto (SofaScoreClient, search_player, get_player_*) è
invariato.
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.services.player_matcher import find_player_in_db
from app.models.models import ScoutingPlayer
from app.models.sofascore_models import PlayerSofascoreStats

log = logging.getLogger(__name__)

# ── Costanti ──────────────────────────────────────────────────────
SOFA_BASE = "https://www.sofascore.com"
SOFA_API  = f"{SOFA_BASE}/api/v1"

LEAGUES = {
    "serie_a":          {"tournament_id": 23,  "season_id": 63515, "name": "Serie A"},
    "premier_league":   {"tournament_id": 17,  "season_id": 61627, "name": "Premier League"},
    "la_liga":          {"tournament_id": 8,   "season_id": 61643, "name": "La Liga"},
    "bundesliga":       {"tournament_id": 35,  "season_id": 63609, "name": "Bundesliga"},
    "ligue_1":          {"tournament_id": 34,  "season_id": 63684, "name": "Ligue 1"},
    "champions_league": {"tournament_id": 7,   "season_id": 61657, "name": "Champions League"},
    "eredivisie":       {"tournament_id": 37,  "season_id": 63646, "name": "Eredivisie"},
    "primeira_liga":    {"tournament_id": 238, "season_id": 63751, "name": "Primeira Liga"},
    "championship":     {"tournament_id": 18,  "season_id": 63516, "name": "Championship"},
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.sofascore.com/",
    "Origin":          "https://www.sofascore.com",
    "Sec-Fetch-Dest":  "empty",
    "Sec-Fetch-Mode":  "cors",
    "Sec-Fetch-Site":  "same-origin",
    "Cache-Control":   "no-cache",
    "Pragma":          "no-cache",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HTTP CLIENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SofaScoreClient:
    def __init__(self, delay: float = 1.5, max_retries: int = 3):
        self.delay       = delay
        self.max_retries = max_retries
        self._session    = requests.Session()
        self._session.headers.update(HEADERS)
        self._last_call  = 0.0

    def get(self, path: str, params: dict = None) -> dict:
        url = f"{SOFA_API}/{path.lstrip('/')}"
        self._throttle()
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(url, params=params, timeout=20)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 15))
                    log.warning(f"SofaScore rate-limit — attendo {wait}s")
                    time.sleep(wait)
                    continue
                if resp.status_code in (404, 403):
                    log.debug(f"HTTP {resp.status_code}: {url}")
                    return {}
                resp.raise_for_status()
                self._last_call = time.monotonic()
                return resp.json()
            except requests.RequestException as e:
                log.warning(f"SofaScore [{attempt}/{self.max_retries}] {url}: {e}")
                if attempt < self.max_retries:
                    time.sleep(self.delay * attempt * 2)
                else:
                    log.error(f"Tutti i retry falliti: {url}")
                    return {}
        return {}

    def _throttle(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)


_default_client: Optional[SofaScoreClient] = None


def get_client() -> SofaScoreClient:
    global _default_client
    if _default_client is None:
        _default_client = SofaScoreClient()
    return _default_client


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RICERCA GIOCATORE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_player(name: str, team: str = "", client: SofaScoreClient = None) -> Optional[dict]:
    c    = client or get_client()
    data = c.get("search/all", params={"q": name, "page": 0})
    results = []
    for item in data.get("results", []):
        if item.get("type") != "player":
            continue
        entity      = item.get("entity", {})
        player_team = entity.get("team", {})
        results.append({
            "id":        entity.get("id"),
            "name":      entity.get("name", ""),
            "slug":      entity.get("slug", ""),
            "position":  entity.get("position", ""),
            "team_name": player_team.get("name", ""),
        })
    if not results:
        return None
    name_lower = name.lower()
    team_lower = team.lower()
    for r in results:
        if name_lower in r["name"].lower():
            if team_lower and team_lower in r["team_name"].lower():
                return r
    for r in results:
        if name_lower in r["name"].lower():
            return r
    return results[0]


def find_season_id(player_id: int, tournament_id: int, client=None) -> Optional[int]:
    c       = client or get_client()
    data    = c.get(f"player/{player_id}/unique-tournament/{tournament_id}/seasons")
    seasons = data.get("uniqueTournamentSeasons", [])
    return seasons[0].get("id") if seasons else None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FETCH DATI DAL PROVIDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_player_profile(player_id: int, client=None) -> dict:
    c = client or get_client()
    data = c.get(f"player/{player_id}")
    p    = data.get("player", {})
    team = p.get("team", {})
    return {
        "id":             p.get("id"),
        "name":           p.get("name", ""),
        "slug":           p.get("slug", ""),
        "position":       p.get("position", ""),
        "age":            p.get("age"),
        "height":         p.get("height"),
        "weight":         p.get("weight"),
        "nationality":    p.get("country", {}).get("name", ""),
        "preferred_foot": p.get("preferredFoot", ""),
        "jersey_number":  p.get("jerseyNumber"),
        "market_value":   p.get("proposedMarketValue"),
        "contract_until": p.get("contractUntilTimestamp"),
        "team_name":      team.get("name", ""),
    }


def get_player_stats(player_id: int, tournament_id: int, season_id: int, client=None) -> dict:
    c    = client or get_client()
    path = f"player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
    data = c.get(path)
    raw  = data.get("statistics", {})
    if not raw:
        log.warning(f"Nessuna stat SofaScore player={player_id} tournament={tournament_id} season={season_id}")
        return {}
    return _parse_stats(raw)


def get_player_heatmap(player_id: int, tournament_id: int, season_id: int, client=None) -> dict:
    c    = client or get_client()
    path = f"player/{player_id}/heatmap/{tournament_id}/season/{season_id}/overall"
    data = c.get(path)
    points = data.get("heatmap", [])
    return {
        "player_id":     player_id,
        "tournament_id": tournament_id,
        "season_id":     season_id,
        "points":        points,
        "point_count":   len(points),
    }


def get_player_matches(player_id: int, page: int = 0, client=None) -> list:
    c    = client or get_client()
    data = c.get(f"player/{player_id}/events/last/{page}")
    events = data.get("events", [])
    matches = []
    for ev in events:
        home   = ev.get("homeTeam", {})
        away   = ev.get("awayTeam", {})
        pstats = ev.get("playerStatistics", {})
        matches.append({
            "event_id":       ev.get("id"),
            "date":           _ts(ev.get("startTimestamp")),
            "home_team":      home.get("name", ""),
            "away_team":      away.get("name", ""),
            "home_score":     ev.get("homeScore", {}).get("current"),
            "away_score":     ev.get("awayScore", {}).get("current"),
            "tournament":     ev.get("tournament", {}).get("name", ""),
            "rating":         pstats.get("rating"),
            "minutes_played": pstats.get("minutesPlayed"),
            "goals":          pstats.get("goals", 0),
            "assists":        pstats.get("goalAssist", 0),
            "yellow_card":    bool(pstats.get("yellowCards", 0)),
            "red_card":       bool(pstats.get("redCards", 0)),
        })
    return matches


def get_player_transfers(player_id: int, client=None) -> list:
    c    = client or get_client()
    data = c.get(f"player/{player_id}/transfer-history")
    return [
        {
            "date":      _ts(t.get("transferDateTimestamp")),
            "from_team": t.get("fromTeam", {}).get("name", ""),
            "to_team":   t.get("toTeam", {}).get("name", ""),
            "fee":       t.get("transferFee"),
            "type":      t.get("type", ""),
        }
        for t in data.get("transferHistory", [])
    ]


def get_player_national_stats(player_id: int, client=None) -> dict:
    c    = client or get_client()
    data = c.get(f"player/{player_id}/national-team-statistics")
    return _parse_stats(data.get("statistics", {}))


def get_player_full(player_id: int, league_key: str = "serie_a", client=None) -> dict:
    league = LEAGUES.get(league_key)
    if not league:
        raise ValueError(f"Lega non supportata: {league_key}. Opzioni: {list(LEAGUES.keys())}")

    c             = client or get_client()
    tournament_id = league["tournament_id"]
    season_id     = find_season_id(player_id, tournament_id, c) or league["season_id"]

    result = {
        "player_id":     player_id,
        "league":        league_key,
        "league_name":   league["name"],
        "tournament_id": tournament_id,
        "season_id":     season_id,
        "fetched_at":    datetime.utcnow().isoformat(),
    }
    result["profile"]       = get_player_profile(player_id, c)
    result["stats"]         = get_player_stats(player_id, tournament_id, season_id, c)
    result["heatmap"]       = get_player_heatmap(player_id, tournament_id, season_id, c)
    result["matches"]       = get_player_matches(player_id, page=0, client=c)
    result["transfers"]     = get_player_transfers(player_id, c)
    result["national_stats"] = get_player_national_stats(player_id, c)
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTEGRAZIONE DB  ← PUNTO CHIAVE DELLA MIGRAZIONE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def import_player_stats(
    db: Session,
    league_key: str = "serie_a",
    min_minutes: int = 200,
    progress_cb=None,
    stop_event=None,
) -> dict:
    """
    Importa le statistiono scrittche SofaScore per tutti i giocatori nel DB.
    Le statistiche venge in player_sofascore_stats (NON in scouting_players).
    """
    from app.models.models import PlayerSeasonStats

    # Considera eleggibili i giocatori che hanno già minuti da qualsiasi fonte
    players = (
        db.query(ScoutingPlayer)
        .join(PlayerSeasonStats, PlayerSeasonStats.player_id == ScoutingPlayer.id, isouter=True)
        .filter(PlayerSeasonStats.minutes_played >= min_minutes)
        .distinct()
        .all()
    )

    if not players:
        # Fallback: prendi tutti (primo import)
        players = db.query(ScoutingPlayer).all()

    client    = get_client()
    enriched  = 0
    not_found = 0
    errors    = 0
    total     = len(players)

    log.info(f"SofaScore: aggiornamento {total} giocatori per {league_key}")

    for idx, player in enumerate(players):
        if stop_event and stop_event.is_set():
            break
        try:
            sofa_id = getattr(player, "sofascore_id", None)
            if not sofa_id:
                result = search_player(player.name, player.club or "", client)
                if not result:
                    not_found += 1
                    log.debug(f"Non trovato: {player.name}")
                    continue
                sofa_id = result["id"]
                player.sofascore_id = str(sofa_id)

            data = get_player_full(int(sofa_id), league_key, client)

            # ── Aggiorna SOLO l'anagrafica su scouting_players ──────
            _apply_profile(player, data.get("profile", {}))

            # ── Scrivi le statistiche nella nuova tabella dedicata ──
            stats = data.get("stats", {})
            if stats:
                season_label = _current_season_label(data)
                _upsert_sofascore_stats(
                    db,
                    player_id=player.id,
                    season=season_label,
                    league=data.get("league_name", league_key),
                    tournament_id=data.get("tournament_id"),
                    season_id=data.get("season_id"),
                    stats=stats,
                    fetched_at=datetime.utcnow(),
                )
                # Cache del rating su scouting_players (per la UI senza join)
                if stats.get("sofascore_rating") is not None:
                    player.sofascore_rating = stats["sofascore_rating"]

            player.last_updated_sofascore = datetime.utcnow()
            enriched += 1

            if idx % 30 == 0:
                db.commit()
                log.info(f"  {idx}/{total} — {enriched} aggiornati, {not_found} non trovati")

            if progress_cb and idx % 10 == 0:
                progress_cb(idx + 1, total)

        except Exception as e:
            errors += 1
            log.error(f"Errore per {player.name}: {e}", exc_info=True)

    db.commit()
    log.info(f"SofaScore completato: {enriched} aggiornati, {not_found} non trovati, {errors} errori")
    return {"enriched": enriched, "not_found": not_found, "errors": errors, "total": total, "league": league_key}


def import_single_player(
    db: Session,
    player_name: str,
    club: str = "",
    sofascore_id: int = None,
    league_key: str = "serie_a",
) -> dict:
    """Importa i dati SofaScore per un singolo giocatore."""
    client = get_client()

    if not sofascore_id:
        found = search_player(player_name, club, client)
        if not found:
            return {"status": "not_found", "player": player_name}
        sofascore_id = found["id"]
        log.info(f"ID SofaScore trovato per {player_name}: {sofascore_id}")

    data   = get_player_full(sofascore_id, league_key, client)
    player = find_player_in_db(db, player_name, club)
    if not player:
        log.warning(f"Giocatore non nel DB: {player_name}")
        return {"status": "not_in_db", "player": player_name}

    _apply_profile(player, data.get("profile", {}))

    stats = data.get("stats", {})
    if stats:
        season_label = _current_season_label(data)
        _upsert_sofascore_stats(
            db,
            player_id=player.id,
            season=season_label,
            league=data.get("league_name", league_key),
            tournament_id=data.get("tournament_id"),
            season_id=data.get("season_id"),
            stats=stats,
            fetched_at=datetime.utcnow(),
        )
        if stats.get("sofascore_rating") is not None:
            player.sofascore_rating = stats["sofascore_rating"]

    player.last_updated_sofascore = datetime.utcnow()
    db.commit()
    return {
        "status": "ok",
        "player": player_name,
        "sofascore_id": sofascore_id,
        "stats_fields": len(stats),
        "heatmap_pts":  data.get("heatmap", {}).get("point_count", 0),
        "matches":      len(data.get("matches", [])),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS INTERNI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _apply_profile(player: ScoutingPlayer, profile: dict):
    """Aggiorna i campi ANAGRAFICI su scouting_players — solo questi."""
    _s(player, "sofascore_id",   str(profile.get("id")) if profile.get("id") else None)
    _s(player, "height",         profile.get("height"))
    _s(player, "weight",         profile.get("weight"))
    _s(player, "preferred_foot", profile.get("preferred_foot"))
    _s(player, "jersey_number",  profile.get("jersey_number"))
    _s(player, "nationality",    profile.get("nationality"))
    _s(player, "market_value",   _market_val(profile.get("market_value")))


def _upsert_sofascore_stats(
    db: Session,
    player_id: int,
    season: str,
    league: str,
    tournament_id: Optional[int],
    season_id: Optional[int],
    stats: dict,
    fetched_at: datetime,
):
    """
    PostgreSQL UPSERT su player_sofascore_stats.
    Mappa il dizionario stats (output di _parse_stats) nelle colonne del modello.
    """
    FIELD_MAP = {
        # stat dict key          : colonna modello
        "sofascore_rating":       "sofascore_rating",
        "minutes_played":         "minutes_played",
        "appearances":            "appearances",
        "games_started":          "matches_started",
        "goals":                  "goals",
        "assists":                "assists",
        "big_chances_created":    "big_chances_created",
        "big_chances_missed":     "big_chances_missed",
        "shots_on_target":        "shots_on_target",
        "shots_off_target":       "shots_off_target",
        "blocked_shots":          "blocked_shots",
        "key_passes":             "key_passes",
        "accurate_passes":        "accurate_passes",
        "total_passes":           "total_passes",
        "pass_accuracy_pct":      "pass_accuracy_pct",
        "long_balls_accurate":    "accurate_long_balls",
        "crosses_accurate":       "accurate_crosses",
        "dribbles_attempted":     "dribble_attempts",
        "dribbles_won":           "successful_dribbles",
        "duels_won":              "total_duels_won",
        "aerial_duels_won":       "aerial_duels_won",
        "ground_duels_won":       "ground_duels_won",
        "tackles":                "tackles",
        "interceptions":          "interceptions",
        "clearances":             "clearances",
        "errors_leading_to_shot": "errors_led_to_shot",
        "errors_leading_to_goal": "errors_led_to_goal",
        "yellow_cards":           "yellow_cards",
        "red_cards":              "red_cards",
        "fouls_committed":        "fouls_committed",
        "fouls_suffered":         "fouls_won",
        "offsides":               "offsides",
        "saves":                  "saves",
        "goals_conceded":         "goals_conceded",
        "clean_sheets":           "clean_sheets",
        "high_claims":            "high_claims",
        "punches":                "punches",
        "xg":                     "xg",
        "xa":                     "xa",
    }

    data_to_insert: dict = {
        "player_id":     player_id,
        "season":        season,
        "league":        league,
        "tournament_id": tournament_id,
        "season_id":     season_id,
        "fetched_at":    fetched_at,
        "updated_at":    fetched_at,
    }

    for src_key, col_name in FIELD_MAP.items():
        val = stats.get(src_key)
        if val is not None:
            data_to_insert[col_name] = val

    # Calcola xG/90 e xA/90 se abbiamo minuti
    minutes = data_to_insert.get("minutes_played") or 0
    if minutes > 0:
        if data_to_insert.get("xg") is not None:
            data_to_insert["xg_per90"] = round(data_to_insert["xg"] * 90 / minutes, 4)
        if data_to_insert.get("xa") is not None:
            data_to_insert["xa_per90"] = round(data_to_insert["xa"] * 90 / minutes, 4)

    # Calcola shots_total e goal_conversion_pct
    sot = data_to_insert.get("shots_on_target") or 0
    soff = data_to_insert.get("shots_off_target") or 0
    sblk = data_to_insert.get("blocked_shots") or 0
    if sot + soff + sblk > 0:
        data_to_insert["shots_total"] = sot + soff + sblk
    goals = data_to_insert.get("goals") or 0
    shots_tot = data_to_insert.get("shots_total") or 0
    if shots_tot > 0:
        data_to_insert["goal_conversion_pct"] = round(goals / shots_tot * 100, 1)

    # Percentuali duelli
    total_dw = data_to_insert.get("total_duels_won")
    aerial_dw = data_to_insert.get("aerial_duels_won")
    ground_dw = data_to_insert.get("ground_duels_won")
    if total_dw is not None:
        # SofaScore non riporta duels_total direttamente — usiamo i dati parziali
        total_est = (aerial_dw or 0) + (ground_dw or 0)
        if total_est > 0:
            data_to_insert["total_duels_won_pct"] = round(total_dw / total_est * 100, 1)

    stmt = insert(PlayerSofascoreStats).values(data_to_insert)
    update_cols = {k: v for k, v in data_to_insert.items()
                   if k not in ("player_id", "season", "league")}
    stmt = stmt.on_conflict_do_update(
        constraint="uq_sofascore_player_season_league",
        set_=update_cols,
    )
    db.execute(stmt)


def _current_season_label(data: dict) -> str:
    """Costruisce etichetta stagione da season_id o anno corrente."""
    now = datetime.utcnow()
    y   = now.year
    m   = now.month
    # Stagione europea: luglio→giugno
    start_year = y if m >= 7 else y - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _parse_stats(raw: dict) -> dict:
    """Normalizza le statistiche raw di SofaScore in un dict standard."""
    def fi(k):
        v = raw.get(k)
        return int(v) if v is not None else None

    def ff(k):
        v = raw.get(k)
        return round(float(v), 4) if v is not None else None

    return {
        "sofascore_rating":       ff("rating"),
        "minutes_played":         fi("minutesPlayed"),
        "appearances":            fi("appearances"),
        "games_started":          fi("matchesStarted"),
        "goals":                  fi("goals"),
        "assists":                fi("goalAssist"),
        "big_chances_created":    fi("bigChanceCreated"),
        "big_chances_missed":     fi("bigChanceMissed"),
        "shots_on_target":        fi("onTargetScoringAttempt"),
        "shots_off_target":       fi("missedBalls"),
        "blocked_shots":          fi("blockedScoringAttempt"),
        "key_passes":             fi("keyPass"),
        "accurate_passes":        fi("accuratePasses"),
        "total_passes":           fi("totalPasses"),
        "pass_accuracy_pct":      ff("accuratePassesPercentage"),
        "long_balls_accurate":    fi("accurateLongBalls"),
        "crosses_accurate":       fi("accurateCrosses"),
        "dribbles_attempted":     fi("attemptedDribbles"),
        "dribbles_won":           fi("successfulDribbles"),
        "duels_won":              fi("duelsWon"),
        "aerial_duels_won":       fi("aerialDuelsWon"),
        "ground_duels_won":       fi("groundDuelsWon"),
        "tackles":                fi("tackles"),
        "interceptions":          fi("interceptions"),
        "clearances":             fi("clearances"),
        "errors_leading_to_shot": fi("errorLeadToShot"),
        "errors_leading_to_goal": fi("errorLeadToGoal"),
        "yellow_cards":           fi("yellowCards"),
        "red_cards":              fi("redCards"),
        "fouls_committed":        fi("fouls"),
        "fouls_suffered":         fi("wasFouled"),
        "offsides":               fi("offsides"),
        "saves":                  fi("saves"),
        "goals_conceded":         fi("goalsConceded"),
        "clean_sheets":           fi("cleanSheet"),
        "high_claims":            fi("highClaims"),
        "punches":                fi("punches"),
        "xg":                     ff("expectedGoals"),
        "xa":                     ff("expectedAssists"),
    }


def _s(obj, attr: str, val):
    if val is not None and hasattr(obj, attr):
        setattr(obj, attr, val)


def _ts(timestamp) -> Optional[str]:
    if not timestamp:
        return None
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return None


def _market_val(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return round(float(v) / 1_000_000, 2)
    except (ValueError, TypeError):
        return None