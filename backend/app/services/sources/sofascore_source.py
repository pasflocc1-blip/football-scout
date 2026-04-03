"""
sources/sofascore_source.py  — v2.0
-------------------------------------
RISCRITTURA COMPLETA dopo scoperta URL reali tramite F12.

PROBLEMA VERSIONI PRECEDENTI:
  Usavamo 'api.sofascore.com' come dominio API — SBAGLIATO.
  Le API di SofaScore sono sullo stesso dominio del sito:
    www.sofascore.com/api/v1/...

  Inoltre i path erano errati:
    SBAGLIATO: /player/{id}/tournaments/{tid}/seasons/{sid}/statistics
    CORRETTO:  /player/{id}/unique-tournament/{tid}/season/{sid}/statistics/overall

URL REALI (scoperte via F12 su SofaScore):
  Profilo:      GET /api/v1/player/{id}
  Statistiche:  GET /api/v1/player/{id}/unique-tournament/{tid}/season/{sid}/statistics/overall
  Heatmap:      GET /api/v1/player/{id}/heatmap/{tid}/season/{sid}/overall
  Partite:      GET /api/v1/player/{id}/events/last/{page}
  Trasferimenti:GET /api/v1/player/{id}/transfer-history
  Stagioni:     GET /api/v1/player/{id}/unique-tournament/{tid}/seasons
  Nazionale:    GET /api/v1/player/{id}/national-team-statistics
  Ricerca:      GET /api/v1/search/all?q={nome}&page=0

APPROCCIO: chiamate HTTP dirette con requests/httpx.
  - Niente browser, niente Playwright, niente estensioni
  - Headers identici a quelli inviati dal browser reale (copiati da F12)
  - Rate limiting rispettoso (1-2 sec tra le chiamate)
  - Funziona da qualsiasi ambiente (Docker, VPS, locale)
"""

import time
import json
import logging
import re
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.services.player_matcher import find_player_in_db
from app.models.models import ScoutingPlayer

log = logging.getLogger(__name__)

# ── Costanti ──────────────────────────────────────────────────────
# BASE corretto: www.sofascore.com, non api.sofascore.com
SOFA_BASE = 'https://www.sofascore.com'
SOFA_API  = f'{SOFA_BASE}/api/v1'

# Leghe con tournament_id e season_id correnti
# season_id: trovato navigando la lega su SofaScore e guardando F12
LEAGUES = {
    'serie_a':          {'tournament_id': 23,  'season_id': 63515, 'name': 'Serie A'},
    'premier_league':   {'tournament_id': 17,  'season_id': 61627, 'name': 'Premier League'},
    'la_liga':          {'tournament_id': 8,   'season_id': 61643, 'name': 'La Liga'},
    'bundesliga':       {'tournament_id': 35,  'season_id': 63609, 'name': 'Bundesliga'},
    'ligue_1':          {'tournament_id': 34,  'season_id': 63684, 'name': 'Ligue 1'},
    'champions_league': {'tournament_id': 7,   'season_id': 61657, 'name': 'Champions League'},
    'eredivisie':       {'tournament_id': 37,  'season_id': 63646, 'name': 'Eredivisie'},
    'primeira_liga':    {'tournament_id': 238, 'season_id': 63751, 'name': 'Primeira Liga'},
    'championship':     {'tournament_id': 18,  'season_id': 63516, 'name': 'Championship'},
}

# Headers identici a quelli del browser Chrome (copiati da F12 → Network → Headers)
# Questi sono fondamentali — senza di essi SofaScore risponde 403
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept':          'application/json, text/plain, */*',
    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer':         'https://www.sofascore.com/',
    'Origin':          'https://www.sofascore.com',
    'Sec-Fetch-Dest':  'empty',
    'Sec-Fetch-Mode':  'cors',
    'Sec-Fetch-Site':  'same-origin',
    'Cache-Control':   'no-cache',
    'Pragma':          'no-cache',
    'sec-ch-ua':       '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    'sec-ch-ua-mobile':   '?0',
    'sec-ch-ua-platform': '"Windows"',
}


# ══════════════════════════════════════════════════════════════════
# CLIENT HTTP
# ══════════════════════════════════════════════════════════════════

class SofaScoreClient:
    """Client HTTP con rate limiting e retry automatico."""

    def __init__(self, delay: float = 1.5, max_retries: int = 3):
        self.delay       = delay
        self.max_retries = max_retries
        self._session    = requests.Session()
        self._session.headers.update(HEADERS)
        self._last_call  = 0.0

    def get(self, path: str, params: dict = None) -> dict:
        """
        GET su /api/v1/{path}.
        Gestisce rate-limit, retry, 403/404.
        """
        url = f'{SOFA_API}/{path.lstrip("/")}'
        self._throttle()

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(url, params=params, timeout=20)

                if resp.status_code == 429:
                    wait = int(resp.headers.get('Retry-After', 15))
                    log.warning(f'SofaScore rate-limit — attendo {wait}s')
                    time.sleep(wait)
                    continue

                if resp.status_code == 404:
                    log.debug(f'404: {url}')
                    return {}

                if resp.status_code == 403:
                    log.warning(f'403 Forbidden: {url} — headers potrebbero essere cambiati')
                    return {}

                resp.raise_for_status()
                self._last_call = time.monotonic()
                return resp.json()

            except requests.RequestException as e:
                log.warning(f'SofaScore [{attempt}/{self.max_retries}] {url}: {e}')
                if attempt < self.max_retries:
                    time.sleep(self.delay * attempt * 2)
                else:
                    log.error(f'Tutti i retry falliti: {url}')
                    return {}

        return {}

    def _throttle(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)


# Istanza globale condivisa
_default_client: Optional[SofaScoreClient] = None

def get_client() -> SofaScoreClient:
    global _default_client
    if _default_client is None:
        _default_client = SofaScoreClient()
    return _default_client


# ══════════════════════════════════════════════════════════════════
# RICERCA GIOCATORE
# ══════════════════════════════════════════════════════════════════

def search_player(name: str, team: str = '', client: SofaScoreClient = None) -> Optional[dict]:
    """
    Cerca un giocatore per nome e restituisce il primo risultato pertinente.

    Returns:
        dict con: id, name, team, position, nationality, slug
        None se non trovato
    """
    c = client or get_client()
    data = c.get('search/all', params={'q': name, 'page': 0})

    results = []
    for item in data.get('results', []):
        if item.get('type') != 'player':
            continue
        entity = item.get('entity', {})
        player_team = entity.get('team', {})
        results.append({
            'id':        entity.get('id'),
            'name':      entity.get('name', ''),
            'slug':      entity.get('slug', ''),
            'position':  entity.get('position', ''),
            'team_id':   player_team.get('id'),
            'team_name': player_team.get('name', ''),
        })

    if not results:
        return None

    # Priorità: match esatto nome + squadra
    name_lower = name.lower()
    team_lower = team.lower()
    for r in results:
        if name_lower in r['name'].lower():
            if team_lower and team_lower in r['team_name'].lower():
                return r
    # Fallback: primo risultato con nome corrispondente
    for r in results:
        if name_lower in r['name'].lower():
            return r

    return results[0]


def find_season_id(
    player_id: int,
    tournament_id: int,
    client: SofaScoreClient = None,
) -> Optional[int]:
    """
    Trova il season_id più recente per un giocatore in un dato torneo.
    Utile quando il season_id hardcoded è scaduto a inizio stagione.

    URL: /api/v1/player/{id}/unique-tournament/{tid}/seasons
    """
    c = client or get_client()
    data = c.get(f'player/{player_id}/unique-tournament/{tournament_id}/seasons')
    seasons = data.get('uniqueTournamentSeasons', [])
    if not seasons:
        return None
    # Prende la stagione più recente (prima della lista, ordinata per anno desc)
    return seasons[0].get('id')


# ══════════════════════════════════════════════════════════════════
# DATI GIOCATORE
# ══════════════════════════════════════════════════════════════════

def get_player_profile(player_id: int, client: SofaScoreClient = None) -> dict:
    """
    Profilo anagrafico del giocatore.
    URL: GET /api/v1/player/{id}
    """
    c = client or get_client()
    data = c.get(f'player/{player_id}')
    p    = data.get('player', {})
    team = p.get('team', {})

    return {
        'id':             p.get('id'),
        'name':           p.get('name', ''),
        'short_name':     p.get('shortName', ''),
        'slug':           p.get('slug', ''),
        'position':       p.get('position', ''),
        'age':            p.get('age'),
        'height':         p.get('height'),
        'weight':         p.get('weight'),
        'nationality':    p.get('country', {}).get('name', ''),
        'preferred_foot': p.get('preferredFoot', ''),
        'jersey_number':  p.get('jerseyNumber'),
        'market_value':   p.get('proposedMarketValue'),
        'contract_until': p.get('contractUntilTimestamp'),
        'team_id':        team.get('id'),
        'team_name':      team.get('name', ''),
        'profile_url':    f'{SOFA_BASE}/football/player/{p.get("slug","")}/{p.get("id","")}',
    }


def get_player_stats(
    player_id: int,
    tournament_id: int,
    season_id: int,
    client: SofaScoreClient = None,
) -> dict:
    """
    Statistiche stagionali aggregate.
    URL: GET /api/v1/player/{id}/unique-tournament/{tid}/season/{sid}/statistics/overall

    Questa è l'URL trovata tramite F12 — la struttura corretta.
    """
    c    = client or get_client()
    path = f'player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall'
    data = c.get(path)
    raw  = data.get('statistics', {})

    if not raw:
        log.warning(f'Nessuna statistica per player={player_id} tournament={tournament_id} season={season_id}')
        return {}

    return _parse_stats(raw)


def get_player_heatmap(
    player_id: int,
    tournament_id: int,
    season_id: int,
    client: SofaScoreClient = None,
) -> dict:
    """
    Heatmap posizionale stagionale.
    URL: GET /api/v1/player/{id}/heatmap/{tid}/season/{sid}/overall
    """
    c    = client or get_client()
    path = f'player/{player_id}/heatmap/{tournament_id}/season/{season_id}/overall'
    data = c.get(path)
    points = data.get('heatmap', [])

    return {
        'player_id':     player_id,
        'tournament_id': tournament_id,
        'season_id':     season_id,
        'points':        points,        # lista di {x, y, value}
        'point_count':   len(points),
        'raw':           data,
    }


def get_player_matches(
    player_id: int,
    page: int = 0,
    client: SofaScoreClient = None,
) -> list[dict]:
    """
    Ultime partite del giocatore con rating e stats.
    URL: GET /api/v1/player/{id}/events/last/{page}
    """
    c    = client or get_client()
    data = c.get(f'player/{player_id}/events/last/{page}')
    events = data.get('events', [])

    matches = []
    for ev in events:
        home   = ev.get('homeTeam', {})
        away   = ev.get('awayTeam', {})
        pstats = ev.get('playerStatistics', {})
        matches.append({
            'event_id':       ev.get('id'),
            'slug':           ev.get('slug', ''),
            'date':           _ts(ev.get('startTimestamp')),
            'home_team':      home.get('name', ''),
            'away_team':      away.get('name', ''),
            'home_score':     ev.get('homeScore', {}).get('current'),
            'away_score':     ev.get('awayScore', {}).get('current'),
            'tournament':     ev.get('tournament', {}).get('name', ''),
            'rating':         pstats.get('rating'),
            'minutes_played': pstats.get('minutesPlayed'),
            'goals':          pstats.get('goals', 0),
            'assists':        pstats.get('goalAssist', 0),
            'yellow_card':    bool(pstats.get('yellowCards', 0)),
            'red_card':       bool(pstats.get('redCards', 0)),
            'match_url':      f'{SOFA_BASE}/football/{ev.get("slug","")}/{ev.get("customId","")}',
        })
    return matches


def get_player_transfers(player_id: int, client: SofaScoreClient = None) -> list[dict]:
    """
    Storico trasferimenti.
    URL: GET /api/v1/player/{id}/transfer-history
    """
    c    = client or get_client()
    data = c.get(f'player/{player_id}/transfer-history')

    transfers = []
    for t in data.get('transferHistory', []):
        transfers.append({
            'date':      _ts(t.get('transferDateTimestamp')),
            'from_team': t.get('fromTeam', {}).get('name', ''),
            'to_team':   t.get('toTeam', {}).get('name', ''),
            'fee':       t.get('transferFee'),
            'fee_raw':   t.get('transferFeeRaw', {}).get('value'),
            'currency':  t.get('transferFeeRaw', {}).get('currency', 'EUR'),
            'type':      t.get('type', ''),  # transfer/loan/loan_return/free
        })
    return transfers


def get_player_national_stats(player_id: int, client: SofaScoreClient = None) -> dict:
    """
    Statistiche in nazionale.
    URL: GET /api/v1/player/{id}/national-team-statistics
    """
    c    = client or get_client()
    data = c.get(f'player/{player_id}/national-team-statistics')
    return _parse_stats(data.get('statistics', {}))


def get_player_full(
    player_id: int,
    league_key: str = 'serie_a',
    client: SofaScoreClient = None,
) -> dict:
    """
    Recupera TUTTI i dati disponibili per un giocatore in una chiamata.

    Sequenza:
      1. Profilo anagrafico
      2. Cerca season_id più recente per la lega
      3. Statistiche stagionali (URL corretta trovata tramite F12)
      4. Heatmap stagionale
      5. Ultime partite
      6. Storico trasferimenti
      7. Statistiche nazionale (opzionale)

    Args:
        player_id:  ID SofaScore del giocatore
        league_key: chiave lega (serie_a, premier_league, ecc.)
    """
    league = LEAGUES.get(league_key)
    if not league:
        raise ValueError(f'Lega non supportata: {league_key}. Opzioni: {list(LEAGUES.keys())}')

    c             = client or get_client()
    tournament_id = league['tournament_id']

    # Trova season_id dinamicamente (gestisce cambi di stagione)
    season_id = find_season_id(player_id, tournament_id, c)
    if not season_id:
        season_id = league['season_id']  # fallback al valore hardcoded
        log.warning(f'season_id non trovato dinamicamente, uso default: {season_id}')
    else:
        log.info(f'season_id trovato: {season_id} per tournament_id={tournament_id}')

    result = {
        'player_id':     player_id,
        'league':        league_key,
        'tournament_id': tournament_id,
        'season_id':     season_id,
        'fetched_at':    datetime.utcnow().isoformat(),
    }

    log.info(f'[SofaScore] Profilo player_id={player_id}')
    result['profile'] = get_player_profile(player_id, c)

    log.info(f'[SofaScore] Statistiche tournament={tournament_id} season={season_id}')
    result['stats'] = get_player_stats(player_id, tournament_id, season_id, c)

    log.info(f'[SofaScore] Heatmap')
    result['heatmap'] = get_player_heatmap(player_id, tournament_id, season_id, c)

    log.info(f'[SofaScore] Partite recenti')
    result['matches'] = get_player_matches(player_id, page=0, client=c)

    log.info(f'[SofaScore] Trasferimenti')
    result['transfers'] = get_player_transfers(player_id, c)

    log.info(f'[SofaScore] Nazionale')
    result['national_stats'] = get_player_national_stats(player_id, c)

    return result


# ══════════════════════════════════════════════════════════════════
# INTEGRAZIONE DB
# ══════════════════════════════════════════════════════════════════

def import_player_stats(
    db: Session,
    league_key: str = 'serie_a',
    min_minutes: int = 200,
    progress_cb=None,
    stop_event=None,
) -> dict:
    """
    Importa le statistiche SofaScore per tutti i giocatori nel DB.

    Per ogni giocatore:
      1. Cerca l'ID SofaScore se non ce l'abbiamo (via search)
      2. Scarica profilo + stats + heatmap + partite
      3. Aggiorna ScoutingPlayer nel DB
    """
    players = db.query(ScoutingPlayer).filter(
        ScoutingPlayer.minutes_season >= min_minutes
    ).all()

    if not players:
        return {'enriched': 0, 'not_found': 0, 'errors': 0, 'total': 0}

    client    = get_client()
    enriched  = 0
    not_found = 0
    errors    = 0
    total     = len(players)

    log.info(f'SofaScore: aggiornamento {total} giocatori per {league_key}')

    for idx, player in enumerate(players):
        if stop_event and stop_event.is_set():
            break

        try:
            # 1. Trova o recupera sofascore_id
            sofa_id = getattr(player, 'sofascore_id', None)
            if not sofa_id:
                result = search_player(player.name, player.club or '', client)
                if not result:
                    not_found += 1
                    log.debug(f'Non trovato: {player.name}')
                    continue
                sofa_id = result['id']
                if hasattr(player, 'sofascore_id'):
                    player.sofascore_id = sofa_id

            # 2. Scarica tutti i dati
            data = get_player_full(sofa_id, league_key, client)

            # 3. Aggiorna il DB
            _apply_to_player(player, data)
            enriched += 1

            if idx % 30 == 0:
                db.commit()
                log.info(f'  {idx}/{total} — {enriched} aggiornati, {not_found} non trovati')

            if progress_cb and idx % 10 == 0:
                progress_cb(idx + 1, total)

        except Exception as e:
            errors += 1
            log.error(f'Errore per {player.name}: {e}')

    db.commit()
    log.info(f'SofaScore completato: {enriched} aggiornati, {not_found} non trovati, {errors} errori')

    return {
        'enriched':  enriched,
        'not_found': not_found,
        'errors':    errors,
        'total':     total,
        'league':    league_key,
    }


def import_single_player(
    db: Session,
    player_name: str,
    club: str = '',
    sofascore_id: int = None,
    league_key: str = 'serie_a',
) -> dict:
    """
    Importa i dati SofaScore per un singolo giocatore.
    Utile per aggiornamenti manuali o test.

    Esempio:
        result = import_single_player(db, "Leonardo Spinazzola", "Roma", 148899)
    """
    client = get_client()

    # Trova l'ID se non fornito
    if not sofascore_id:
        found = search_player(player_name, club, client)
        if not found:
            return {'status': 'not_found', 'player': player_name}
        sofascore_id = found['id']
        log.info(f'ID trovato per {player_name}: {sofascore_id}')

    # Scarica tutti i dati
    data = get_player_full(sofascore_id, league_key, client)

    # Trova il giocatore nel DB
    player = find_player_in_db(db, player_name, club)
    if not player:
        log.warning(f'Giocatore non nel DB: {player_name}')
        return {'status': 'not_in_db', 'player': player_name, 'data': data}

    # Applica i dati
    _apply_to_player(player, data)
    db.commit()

    log.info(f'Aggiornato: {player_name} — stats={bool(data.get("stats"))}, heatmap={data.get("heatmap",{}).get("point_count",0)} punti')

    return {
        'status':       'ok',
        'player':       player_name,
        'sofascore_id': sofascore_id,
        'stats_fields': len(data.get('stats', {})),
        'heatmap_pts':  data.get('heatmap', {}).get('point_count', 0),
        'matches':      len(data.get('matches', [])),
        'transfers':    len(data.get('transfers', [])),
    }


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _parse_stats(raw: dict) -> dict:
    """Normalizza le statistiche raw di SofaScore in un dict standard."""
    def fi(k): v = raw.get(k); return int(v) if v is not None else None
    def ff(k): v = raw.get(k); return round(float(v), 4) if v is not None else None

    return {
        # Rating e presenze
        'sofascore_rating':       ff('rating'),
        'minutes_played':         fi('minutesPlayed'),
        'appearances':            fi('appearances'),
        'games_started':          fi('matchesStarted'),
        # Attacco
        'goals':                  fi('goals'),
        'assists':                fi('goalAssist'),
        'big_chances_created':    fi('bigChanceCreated'),
        'big_chances_missed':     fi('bigChanceMissed'),
        # Tiri
        'shots_on_target':        fi('onTargetScoringAttempt'),
        'shots_off_target':       fi('missedBalls'),
        'blocked_shots':          fi('blockedScoringAttempt'),
        # Passaggi
        'key_passes':             fi('keyPass'),
        'accurate_passes':        fi('accuratePasses'),
        'total_passes':           fi('totalPasses'),
        'pass_accuracy_pct':      ff('accuratePassesPercentage'),
        'long_balls_accurate':    fi('accurateLongBalls'),
        'crosses_accurate':       fi('accurateCrosses'),
        # Dribbling e duelli
        'dribbles_attempted':     fi('attemptedDribbles'),
        'dribbles_won':           fi('successfulDribbles'),
        'duels_won':              fi('duelsWon'),
        'aerial_duels_won':       fi('aerialDuelsWon'),
        'ground_duels_won':       fi('groundDuelsWon'),
        # Difesa
        'tackles':                fi('tackles'),
        'interceptions':          fi('interceptions'),
        'clearances':             fi('clearances'),
        'errors_leading_to_shot': fi('errorLeadToShot'),
        'errors_leading_to_goal': fi('errorLeadToGoal'),
        # Disciplina
        'yellow_cards':           fi('yellowCards'),
        'red_cards':              fi('redCards'),
        'fouls_committed':        fi('fouls'),
        'fouls_suffered':         fi('wasFouled'),
        'offsides':               fi('offsides'),
        # Portiere
        'saves':                  fi('saves'),
        'goals_conceded':         fi('goalsConceded'),
        'save_pct':               ff('savedShotsFromInsideTheBox'),
        'clean_sheets':           fi('cleanSheet'),
        'punches':                fi('punches'),
        'high_claims':            fi('highClaims'),
        # xG/xA (se disponibili)
        'xg':                     ff('expectedGoals'),
        'xa':                     ff('expectedAssists'),
    }


def _apply_to_player(player: ScoutingPlayer, data: dict):
    """Applica i dati SofaScore al record ScoutingPlayer."""
    profile   = data.get('profile', {})
    stats     = data.get('stats', {})
    heatmap   = data.get('heatmap', {})
    matches   = data.get('matches', [])
    transfers = data.get('transfers', [])

    # Profilo
    _s(player, 'sofascore_id',      data.get('player_id') or profile.get('id'))
    _s(player, 'height',            profile.get('height'))
    _s(player, 'preferred_foot',    profile.get('preferred_foot'))
    _s(player, 'jersey_number',     profile.get('jersey_number'))
    _s(player, 'market_value',      profile.get('market_value'))

    # Statistiche stagionali
    _s(player, 'sofascore_rating',    stats.get('sofascore_rating'))
    _s(player, 'goals_season',        stats.get('goals'))
    _s(player, 'assists_season',      stats.get('assists'))
    _s(player, 'minutes_season',      stats.get('minutes_played'))
    _s(player, 'games_season',        stats.get('appearances'))
    _s(player, 'shots_season',        stats.get('shots_on_target'))
    _s(player, 'key_passes_season',   stats.get('key_passes'))
    _s(player, 'tackles_season',      stats.get('tackles'))
    _s(player, 'interceptions_season', stats.get('interceptions'))
    _s(player, 'dribbles_season',     stats.get('dribbles_won'))
    _s(player, 'big_chances_created', stats.get('big_chances_created'))
    _s(player, 'aerial_duels_won',    stats.get('aerial_duels_won'))
    _s(player, 'pass_accuracy',       stats.get('pass_accuracy_pct'))
    _s(player, 'yellow_cards',        stats.get('yellow_cards'))
    _s(player, 'red_cards',           stats.get('red_cards'))
    _s(player, 'xg_per90',           stats.get('xg'))
    _s(player, 'xa_per90',           stats.get('xa'))
    # GK
    _s(player, 'saves',              stats.get('saves'))
    _s(player, 'goals_conceded',     stats.get('goals_conceded'))
    _s(player, 'clean_sheets',       stats.get('clean_sheets'))

    # Heatmap
    if heatmap.get('points'):
        _s(player, 'heatmap_data', json.dumps({
            'points':        heatmap['points'],
            'point_count':   heatmap['point_count'],
            'tournament_id': data.get('tournament_id'),
            'season_id':     data.get('season_id'),
            'fetched_at':    data.get('fetched_at'),
        }))

    # Storico partite e trasferimenti
    if matches:
        _s(player, 'matches_history', json.dumps(matches))
    if transfers:
        _s(player, 'transfer_history', json.dumps(transfers))

    # Timestamp
    _s(player, 'last_updated_sofascore', datetime.utcnow())


def _s(player: ScoutingPlayer, field: str, value):
    """Set field solo se esiste nel modello e value non è None."""
    if value is not None and hasattr(player, field):
        setattr(player, field, value)


def _ts(timestamp) -> Optional[str]:
    """Converte Unix timestamp in stringa ISO."""
    if not timestamp:
        return None
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d')
    except (ValueError, OSError):
        return None