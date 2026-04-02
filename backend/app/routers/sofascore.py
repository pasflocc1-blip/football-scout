"""
ingest/sofascore.py  — v1.0
-----------------------------
Endpoint FastAPI che riceve i payload dall'estensione Chrome Scout Interceptor
e li salva sul DB abbinandoli ai giocatori in ScoutingPlayer.

ENDPOINTS:
  POST /ingest/sofascore/raw          ← chiamato dall'estensione Chrome
  POST /ingest/sofascore/player-done  ← chiamato dal RPA a fine giocatore
  GET  /ingest/sofascore/status       ← monitoring
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ScoutingPlayer
from app.services.player_matcher import find_player_in_db

log = logging.getLogger(__name__)
router = APIRouter(prefix='/ingest/sofascore', tags=['ingest-sofascore'])

# Contatori sessione (reset a ogni restart del server)
_stats = {'received': 0, 'matched': 0, 'unmatched': 0, 'errors': 0}


# ── Modelli Pydantic ──────────────────────────────────────────────

class SofaRawPayload(BaseModel):
    type:        str             # player_profile | player_season_stats | player_heatmap | ...
    url:         str
    ids:         dict            # {player_id, event_id, tournament_id, season_id}
    data:        Any             # JSON grezzo di SofaScore
    captured_at: str
    page_url:    Optional[str]   = None
    tab_id:      Optional[int]   = None
    tab_url:     Optional[str]   = None


class PlayerDonePayload(BaseModel):
    name:         str
    club:         str           = ''
    db_id:        Optional[int] = None
    sofascore_id: Optional[int] = None
    completed_at: str


# ── Endpoint principale ───────────────────────────────────────────

@router.post('/raw')
async def ingest_raw(payload: SofaRawPayload, db: Session = Depends(get_db)):
    """
    Riceve il JSON intercettato dall'estensione e lo smista
    al parser corretto in base al tipo.
    """
    _stats['received'] += 1

    try:
        handler = HANDLERS.get(payload.type)
        if handler is None:
            log.debug(f'Tipo non gestito: {payload.type} — {payload.url}')
            return {'status': 'ignored', 'type': payload.type}

        result = handler(db, payload)
        if result.get('matched'):
            _stats['matched'] += 1
        else:
            _stats['unmatched'] += 1

        return {'status': 'ok', **result}

    except Exception as e:
        _stats['errors'] += 1
        log.error(f'Errore ingest {payload.type}: {e}', exc_info=True)
        return {'status': 'error', 'message': str(e)}


@router.post('/player-done')
async def player_done(payload: PlayerDonePayload, db: Session = Depends(get_db)):
    """
    Ricevuto dal RPA quando ha finito di navigare tutte le tab di un giocatore.
    Aggiorna il timestamp last_updated_sofascore.
    """
    player = None

    if payload.db_id:
        player = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == payload.db_id).first()

    if not player and payload.sofascore_id:
        player = db.query(ScoutingPlayer).filter(
            ScoutingPlayer.sofascore_id == payload.sofascore_id
        ).first()

    if not player:
        player = find_player_in_db(db, payload.name, payload.club)

    if player and hasattr(player, 'last_updated_sofascore'):
        player.last_updated_sofascore = datetime.utcnow()
        db.commit()
        log.info(f'Player done: {payload.name} → last_updated_sofascore aggiornato')
        return {'status': 'ok', 'player': payload.name}

    return {'status': 'not_found', 'player': payload.name}


@router.get('/status')
async def status():
    """Stato del servizio di ingest."""
    return {
        'status':    'running',
        'stats':     _stats,
        'timestamp': datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════
# HANDLERS — uno per tipo di payload
# ══════════════════════════════════════════════════════════════════

def _handle_player_profile(db: Session, payload: SofaRawPayload) -> dict:
    """
    Payload: /api/v1/player/{id}
    Estrae: nome, posizione, altezza, peso, piede, numero maglia, nazionalità, squadra
    """
    data = payload.data
    p = data.get('player', {})
    if not p:
        return {'matched': False, 'reason': 'no player object'}

    player = _find_player(db, p, payload.ids)
    if not player:
        return {'matched': False, 'reason': 'not in db', 'name': p.get('name')}

    # Salva l'ID SofaScore sul giocatore (fondamentale per i futuri lookup)
    sofa_id = payload.ids.get('player_id') or p.get('id')
    if sofa_id and hasattr(player, 'sofascore_id'):
        player.sofascore_id = sofa_id

    _safe_set(player, 'preferred_foot',  p.get('preferredFoot'))
    _safe_set(player, 'height',          p.get('height'))
    _safe_set(player, 'weight',          p.get('weight'))
    _safe_set(player, 'jersey_number',   p.get('jerseyNumber'))
    _safe_set(player, 'market_value',    p.get('proposedMarketValue'))

    # Posizione
    pos_raw = p.get('position', '')
    if pos_raw:
        _safe_set(player, 'position', _normalize_position(pos_raw))

    db.commit()
    log.info(f'Profile: {p.get("name")} → sofascore_id={sofa_id}')
    return {'matched': True, 'player': p.get('name'), 'sofascore_id': sofa_id}


def _handle_player_season_stats(db: Session, payload: SofaRawPayload) -> dict:
    """
    Payload: /api/v1/player/{id}/tournaments/{tid}/seasons/{sid}/statistics/overall
    Estrae: tutti i parametri statistici stagionali
    """
    raw = payload.data.get('statistics', {})
    if not raw:
        return {'matched': False, 'reason': 'no statistics'}

    player = _find_player_by_sofa_id(db, payload.ids.get('player_id'))
    if not player:
        return {'matched': False, 'reason': 'player not found by sofascore_id'}

    stats = _parse_stats(raw)
    _apply_stats(player, stats)
    db.commit()

    log.info(f'Stats stagionali: {player.name} — rating={stats.get("sofascore_rating")}')
    return {'matched': True, 'player': player.name, 'params': len(stats)}


def _handle_player_heatmap(db: Session, payload: SofaRawPayload) -> dict:
    """
    Payload: /api/v1/player/{id}/heatmap/{tid}/season/{sid}/overall
    Salva i punti heatmap come JSON su player.heatmap_data
    """
    points = payload.data.get('heatmap', [])
    if not points:
        return {'matched': False, 'reason': 'empty heatmap'}

    player = _find_player_by_sofa_id(db, payload.ids.get('player_id'))
    if not player:
        return {'matched': False, 'reason': 'player not found'}

    heatmap_json = json.dumps({
        'points':      points,
        'point_count': len(points),
        'url':         payload.url,
        'captured_at': payload.captured_at,
    })

    _safe_set(player, 'heatmap_data', heatmap_json)
    db.commit()

    log.info(f'Heatmap: {player.name} — {len(points)} punti salvati')
    return {'matched': True, 'player': player.name, 'points': len(points)}


def _handle_player_matches(db: Session, payload: SofaRawPayload) -> dict:
    """
    Payload: /api/v1/player/{id}/events/last/{page}
    Salva le ultime partite con rating per ogni match
    """
    events = payload.data.get('events', [])
    if not events:
        return {'matched': False, 'reason': 'no events'}

    player = _find_player_by_sofa_id(db, payload.ids.get('player_id'))
    if not player:
        return {'matched': False, 'reason': 'player not found'}

    matches = []
    rating_sum = 0.0
    rating_count = 0

    for ev in events:
        pstats = ev.get('playerStatistics', {})
        rating = pstats.get('rating')
        matches.append({
            'event_id':       ev.get('id'),
            'date':           ev.get('startTimestamp'),
            'home_team':      ev.get('homeTeam', {}).get('name', ''),
            'away_team':      ev.get('awayTeam', {}).get('name', ''),
            'home_score':     ev.get('homeScore', {}).get('current'),
            'away_score':     ev.get('awayScore', {}).get('current'),
            'rating':         rating,
            'minutes_played': pstats.get('minutesPlayed'),
            'goals':          pstats.get('goals', 0),
            'assists':        pstats.get('goalAssist', 0),
        })
        if rating:
            rating_sum += float(rating)
            rating_count += 1

    # Salva storico partite come JSON
    _safe_set(player, 'matches_history', json.dumps(matches))

    # Aggiorna rating medio se non già presente dai season stats
    if rating_count > 0 and not getattr(player, 'sofascore_rating', None):
        avg_rating = round(rating_sum / rating_count, 2)
        _safe_set(player, 'sofascore_rating', avg_rating)

    db.commit()
    log.info(f'Matches: {player.name} — {len(matches)} partite, rating medio={round(rating_sum/rating_count, 2) if rating_count else "N/D"}')
    return {'matched': True, 'player': player.name, 'matches': len(matches)}


def _handle_transfers(db: Session, payload: SofaRawPayload) -> dict:
    """
    Payload: /api/v1/player/{id}/transfer-history
    """
    transfers = payload.data.get('transferHistory', [])
    if not transfers:
        return {'matched': False, 'reason': 'no transfers'}

    player = _find_player_by_sofa_id(db, payload.ids.get('player_id'))
    if not player:
        return {'matched': False, 'reason': 'player not found'}

    parsed = []
    for t in transfers:
        parsed.append({
            'date':      t.get('transferDateTimestamp'),
            'from_team': t.get('fromTeam', {}).get('name', ''),
            'to_team':   t.get('toTeam', {}).get('name', ''),
            'fee':       t.get('transferFee'),
            'type':      t.get('type', ''),
        })

    _safe_set(player, 'transfer_history', json.dumps(parsed))
    db.commit()

    log.info(f'Transfers: {player.name} — {len(parsed)} trasferimenti')
    return {'matched': True, 'player': player.name, 'transfers': len(parsed)}


def _handle_match_heatmap(db: Session, payload: SofaRawPayload) -> dict:
    """Heatmap di una singola partita — salviamo solo se utile."""
    points = payload.data.get('heatmap', [])
    log.debug(f'Match heatmap: event={payload.ids.get("event_id")} player={payload.ids.get("player_id")} — {len(points)} punti (non salvato)')
    return {'matched': False, 'reason': 'match heatmap not persisted (use season heatmap)'}


# ── Dispatch table ────────────────────────────────────────────────
HANDLERS = {
    'player_profile':      _handle_player_profile,
    'player_season_stats': _handle_player_season_stats,
    'player_heatmap':      _handle_player_heatmap,
    'player_matches':      _handle_player_matches,
    'transfers':           _handle_transfers,
    'match_heatmap':       _handle_match_heatmap,
}


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _find_player(db: Session, p: dict, ids: dict) -> Optional[ScoutingPlayer]:
    """Trova il giocatore nel DB: prima per sofascore_id, poi per nome+squadra."""
    sofa_id = ids.get('player_id') or p.get('id')
    if sofa_id:
        player = _find_player_by_sofa_id(db, sofa_id)
        if player:
            return player

    name  = p.get('name', '')
    team  = p.get('team', {}).get('name', '')
    return find_player_in_db(db, name, team)


def _find_player_by_sofa_id(db: Session, sofa_id: Optional[int]) -> Optional[ScoutingPlayer]:
    if not sofa_id:
        return None
    if hasattr(ScoutingPlayer, 'sofascore_id'):
        return db.query(ScoutingPlayer).filter(
            ScoutingPlayer.sofascore_id == sofa_id
        ).first()
    return None


def _safe_set(player: ScoutingPlayer, field: str, value):
    """Imposta un campo solo se esiste nel modello e il valore è valido."""
    if value is not None and hasattr(player, field):
        setattr(player, field, value)


def _parse_stats(raw: dict) -> dict:
    """Normalizza le statistiche raw di SofaScore."""
    def fi(key):
        v = raw.get(key)
        return int(v) if v is not None else None
    def ff(key):
        v = raw.get(key)
        return round(float(v), 4) if v is not None else None

    return {
        'sofascore_rating':       ff('rating'),
        'minutes_season':         fi('minutesPlayed'),
        'games_season':           fi('appearances'),
        'goals_season':           fi('goals'),
        'assists_season':         fi('goalAssist'),
        'shots_season':           fi('onTargetScoringAttempt'),
        'key_passes_season':      fi('keyPass'),
        'tackles_season':         fi('tackles'),
        'interceptions_season':   fi('interceptions'),
        'dribbles_season':        fi('successfulDribbles'),
        'big_chances_created':    fi('bigChanceCreated'),
        'big_chances_missed':     fi('bigChanceMissed'),
        'aerial_duels_won':       fi('aerialDuelsWon'),
        'ground_duels_won':       fi('groundDuelsWon'),
        'pass_accuracy':          ff('accuratePassesPercentage'),
        'accurate_passes':        fi('accuratePasses'),
        'long_balls_accurate':    fi('accurateLongBalls'),
        'crosses_accurate':       fi('accurateCrosses'),
        'fouls_committed':        fi('fouls'),
        'yellow_cards':           fi('yellowCards'),
        'red_cards':              fi('redCards'),
        'saves':                  fi('saves'),
        'goals_conceded':         fi('goalsConceded'),
        'clean_sheets':           fi('cleanSheet'),
    }


def _apply_stats(player: ScoutingPlayer, stats: dict):
    for field, value in stats.items():
        _safe_set(player, field, value)


def _normalize_position(raw: str) -> str:
    MAP = {
        'G': 'GK', 'GK': 'GK',
        'D': 'CB', 'DF': 'CB',
        'M': 'CM', 'MF': 'CM',
        'F': 'ST', 'FW': 'ST',
    }
    first = raw.split(',')[0].strip().upper()
    return MAP.get(first, first)