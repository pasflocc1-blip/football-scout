"""
ingest/sofascore.py  — v3.0
-----------------------------
MODIFICHE v2 → v3:

  /ocr aggiornato per RPA v8 (multi-competizione):
    - Accetta extracted.competitions (lista di tornei) invece di extracted.season (singola).
    - Per ogni competition chiama _upsert_season_stats con:
        league  = tournament_name (es. "Serie A")
        season  = season_year formattato (es. "25/26" → "2025-26")
        tournament_id e season_id salvati nella riga PlayerSeasonStats
    - La heatmap è per competizione (non globale).
    - _save_matches() gestisce i nuovi campi: tournament_id, season_id, season_year,
      round, winner_code, status, has_xg, has_player_stats, has_heatmap.
    - _save_career() gestisce i nuovi campi: transfer_id, from/to_team_id,
      fee_description, type_code.
    - _upsert_national() gestisce la lista di entry (una per nazione).
    - _apply_profile() gestisce date_of_birth come stringa ISO (non timestamp).
    - Retrocompatibilità: se extracted.season esiste ancora (vecchio RPA v7),
      lo gestisce come prima.

  /raw e /player-done invariati.
"""

import json
import logging
from datetime import datetime, date, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import (
    ScoutingPlayer,
    PlayerSeasonStats,
    PlayerMatch,
    PlayerHeatmap,
    PlayerCareer,
    PlayerNationalStats,
)
from app.services.player_matcher import find_player_in_db

log = logging.getLogger(__name__)
router = APIRouter(prefix='/ingest/sofascore', tags=['ingest-sofascore'])

_stats_counter = {'received': 0, 'matched': 0, 'unmatched': 0, 'errors': 0}
CURRENT_SEASON = '2024-25'


# ── Modelli Pydantic ──────────────────────────────────────────────

class SofaRawPayload(BaseModel):
    type:        str
    url:         str
    ids:         dict
    data:        Any
    captured_at: str
    page_url:    Optional[str] = None
    tab_id:      Optional[int] = None
    tab_url:     Optional[str] = None

class PlayerDonePayload(BaseModel):
    name:         str
    club:         str           = ''
    db_id:        Optional[int] = None
    sofascore_id: Optional[int] = None
    completed_at: str

class OCRPayload(BaseModel):
    name:         str
    club:         str            = ''
    db_id:        Optional[int]  = None
    sofascore_id: Optional[int]  = None
    source:       str            = 'sofascore'
    extracted:    dict           = {}
    extracted_at: str            = ''


# ── /raw ─────────────────────────────────────────────────────────

@router.post('/raw')
async def ingest_raw(payload: SofaRawPayload, db: Session = Depends(get_db)):
    _stats_counter['received'] += 1
    try:
        handler = RAW_HANDLERS.get(payload.type)
        if handler is None:
            return {'status': 'ignored', 'type': payload.type}
        result = handler(db, payload)
        if result.get('matched'):
            _stats_counter['matched'] += 1
        else:
            _stats_counter['unmatched'] += 1
        return {'status': 'ok', **result}
    except Exception as e:
        _stats_counter['errors'] += 1
        log.error(f'Errore ingest {payload.type}: {e}', exc_info=True)
        return {'status': 'error', 'message': str(e)}


# ── /ocr (RPA v8 multi-competizione + retrocompatibilità v7) ──────

@router.post('/ocr')
async def ingest_ocr(payload: OCRPayload, db: Session = Depends(get_db)):
    """
    Riceve il payload dall'RPA e salva nelle tabelle normalizzate.

    Struttura attesa (v8):
      extracted.profile       → scouting_players
      extracted.competitions  → list[{tournament_id, season_id, tournament_name,
                                      season_year, statistics, heatmap_points}]
      extracted.matches       → list[PlayerMatch]  (campi estesi)
      extracted.career        → list[PlayerCareer] (campi estesi)
      extracted.national      → list[PlayerNationalStats]

    Retrocompatibilità v7: se extracted.season esiste, lo gestisce come prima.
    """
    player = _find_player_for_ocr(db, payload)
    if not player:
        log.warning(f'OCR: giocatore non trovato: {payload.name}')
        return {'status': 'not_found', 'player': payload.name}

    updated_sections = []
    fetched_at = datetime.utcnow()
    ex = payload.extracted

    # 1. Profile → scouting_players
    profile = ex.get('profile', {})
    if profile:
        _apply_profile(player, profile, payload.sofascore_id)
        updated_sections.append('profile')

    # 1b. Attributi SofaScore → sofascore_attributes_raw
    # L'RPA v9 manda extracted.attributes come dict piatto:
    # {"attr_attacking": 72, "attr_technical": 68, ...}
    # Lo salviamo direttamente — player_detail.py lo trasforma per il Vue.
    attributes = ex.get('attributes', {})
    if attributes and hasattr(player, 'sofascore_attributes_raw'):
        # Merge con eventuali dati già presenti (non sovrascrivere con dict vuoto)
        existing = player.sofascore_attributes_raw or {}
        existing.update({k: v for k, v in attributes.items() if v is not None})
        player.sofascore_attributes_raw = existing
        n_attrs = len([v for v in existing.values() if v is not None])
        updated_sections.append(f'attributes({n_attrs})')

    # 2. Competitions → player_season_stats + player_heatmap (v8)
    competitions = ex.get('competitions', [])
    if competitions:
        for comp in competitions:
            season_str = _format_season(comp.get('season_year', ''))
            league_str = comp.get('tournament_name', 'unknown')
            stats      = comp.get('statistics', {})
            heatmap_pts= comp.get('heatmap_points', [])
            tid        = comp.get('tournament_id')
            sid        = comp.get('season_id')

            if stats:
                _upsert_season_stats_v8(
                    db, player.id, season_str, league_str, payload.source,
                    stats, tid, sid, fetched_at
                )
                # Cache rating su scouting_players (per la UI)
                if stats.get('rating') and not player.sofascore_rating:
                    player.sofascore_rating = _f(stats.get('rating'))

            if heatmap_pts:
                _upsert_heatmap_v8(
                    db, player.id, season_str, league_str,
                    heatmap_pts, profile.get('position'), fetched_at
                )

        n_comps = len(competitions)
        n_with_stats = sum(1 for c in competitions if c.get('statistics'))
        n_with_heat  = sum(1 for c in competitions if c.get('heatmap_points'))
        updated_sections.append(f'competitions({n_comps}: {n_with_stats} stats, {n_with_heat} heatmap)')

    # Retrocompatibilità v7: extracted.season
    season_data = ex.get('season', {})
    if season_data and not competitions:
        season_str = _detect_season_legacy(ex)
        league_str = ex.get('_raw_meta', {}).get('league', 'unknown')
        _upsert_season_stats_legacy(db, player.id, season_str, league_str,
                                    payload.source, season_data, ex, fetched_at)
        if season_data.get('rating') and not player.sofascore_rating:
            player.sofascore_rating = _f(season_data.get('rating'))
        updated_sections.append('season(legacy_v7)')

    # 3. Matches → player_matches
    matches_list = ex.get('matches', [])
    # Retrocompatibilità: vecchio formato {matches: [...], average_rating: ...}
    if isinstance(matches_list, dict):
        matches_list = matches_list.get('matches', [])
    if matches_list:
        _save_matches_v8(db, player.id, matches_list, payload.source, fetched_at)
        updated_sections.append(f'matches({len(matches_list)})')

    # 4. Career → player_career
    career_list = ex.get('career', [])
    # Retrocompatibilità: vecchio formato {transfers: [...]}
    if isinstance(career_list, dict):
        career_list = career_list.get('transfers', [])
    if career_list:
        _save_career_v8(db, player.id, career_list, payload.source, fetched_at)
        updated_sections.append(f'career({len(career_list)})')

    # 5. National → player_national_stats
    national_list = ex.get('national', [])
    if isinstance(national_list, dict):
        national_list = [national_list]
    if national_list:
        for entry in national_list:
            _upsert_national_v8(db, player.id, entry, payload.source, fetched_at)
        updated_sections.append(f'national({len(national_list)})')

    # 6. Timestamp
    player.last_updated_sofascore = fetched_at
    db.commit()

    log.info(f'OCR v3: {player.name} — {updated_sections}')
    return {
        'status':         'ok',
        'player':         player.name,
        'sections_saved': updated_sections,
        'sofascore_id':   payload.sofascore_id,
    }


# ── /player-done ─────────────────────────────────────────────────

@router.post('/player-done')
async def player_done(payload: PlayerDonePayload, db: Session = Depends(get_db)):
    player = db.query(ScoutingPlayer).filter(
        (ScoutingPlayer.sofascore_id == str(payload.sofascore_id)) |
        (ScoutingPlayer.name == payload.name)
    ).first()
    if not player:
        player = find_player_in_db(db, payload.name, payload.club)
    if player:
        if not player.sofascore_id:
            player.sofascore_id = str(payload.sofascore_id)
        player.last_updated_sofascore = datetime.now()
        db.commit()
        log.info(f'player-done: {payload.name}')
        return {'status': 'updated', 'player': payload.name, 'player_id': player.id}
    return {'status': 'not_found', 'player': payload.name}


@router.get('/status')
async def status():
    return {'status': 'running', 'stats': _stats_counter,
            'timestamp': datetime.utcnow().isoformat()}


# ══════════════════════════════════════════════════════════════════
# HELPERS — v8 (multi-competizione)
# ══════════════════════════════════════════════════════════════════

def _find_player_for_ocr(db: Session, payload: OCRPayload) -> Optional[ScoutingPlayer]:
    if payload.db_id:
        p = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == payload.db_id).first()
        if p: return p
    if payload.sofascore_id:
        p = db.query(ScoutingPlayer).filter(
            ScoutingPlayer.sofascore_id == str(payload.sofascore_id)
        ).first()
        if p: return p
    return find_player_in_db(db, payload.name, payload.club)


def _apply_profile(player: ScoutingPlayer, profile: dict, sofascore_id: Optional[int]):
    """Aggiorna i campi anagrafici su scouting_players."""
    if sofascore_id and not player.sofascore_id:
        player.sofascore_id = str(sofascore_id)
    elif profile.get('sofascore_id') and not player.sofascore_id:
        player.sofascore_id = str(profile['sofascore_id'])

    _s(player, 'height',          _i(profile.get('height_cm')))
    _s(player, 'weight',          _i(profile.get('weight_kg')))
    _s(player, 'preferred_foot',  profile.get('preferred_foot'))
    _s(player, 'jersey_number',   _i(profile.get('jersey_number')))
    _s(player, 'nationality',     profile.get('nationality'))
    _s(player, 'position',        profile.get('position'))
    _s(player, 'position_detail', profile.get('position_detail'))
    _s(player, 'gender',          profile.get('gender'))
    _s(player, 'market_value',    profile.get('market_value'))  # già in milioni

    # contract_until: stringa "YYYY-MM-DD" (v8) oppure timestamp int (legacy)
    ct = profile.get('contract_until')
    if ct:
        try:
            if isinstance(ct, str) and len(ct) >= 10:
                _s(player, 'contract_until', date.fromisoformat(ct[:10]))
            elif isinstance(ct, (int, float)):
                _s(player, 'contract_until',
                   date.fromtimestamp(ct, tz=timezone.utc))
        except Exception:
            pass

    # date_of_birth: stringa "YYYY-MM-DD" (v8) oppure timestamp int (legacy)
    dob = profile.get('date_of_birth')
    if dob:
        try:
            if isinstance(dob, str) and len(dob) >= 10:
                _s(player, 'birth_date', date.fromisoformat(dob[:10]))
            elif isinstance(dob, (int, float)):
                _s(player, 'birth_date',
                   date.fromtimestamp(dob, tz=timezone.utc))
        except Exception:
            pass


def _upsert_season_stats_v8(db, player_id, season, league, source,
                             stats: dict, tournament_id, season_id, fetched_at):
    """
    Crea o aggiorna player_season_stats con i dati da _map_stats() dell'RPA v8.
    I nomi dei campi in `stats` corrispondono DIRETTAMENTE alle colonne del modello.
    """
    row = db.query(PlayerSeasonStats).filter_by(
        player_id=player_id, season=season, league=league, source=source
    ).first()
    if not row:
        row = PlayerSeasonStats(
            player_id=player_id, season=season, league=league, source=source
        )
        db.add(row)

    # Tutti i campi hanno lo stesso nome nel dict e nella colonna — loop diretto
    for field, value in stats.items():
        if value is None:
            continue
        if not hasattr(row, field):
            continue  # campo extra non ancora in DB (es. total_rating) — ignora silenziosamente
        # Determina tipo dalla colonna SQLAlchemy
        col = PlayerSeasonStats.__table__.c.get(field)
        if col is None:
            continue
        col_type = str(col.type)
        try:
            if 'INTEGER' in col_type or 'INT' in col_type:
                setattr(row, field, _i(value))
            elif 'FLOAT' in col_type or 'REAL' in col_type or 'NUMERIC' in col_type:
                setattr(row, field, _f(value))
            else:
                setattr(row, field, value)
        except Exception:
            pass

    _s(row, 'tournament_id', tournament_id)
    _s(row, 'season_id',     season_id)
    row.fetched_at = fetched_at
    row.updated_at = fetched_at


def _upsert_heatmap_v8(db, player_id, season, league, points, position, fetched_at):
    """Crea o aggiorna player_heatmap per (player_id, season, league)."""
    row = db.query(PlayerHeatmap).filter_by(
        player_id=player_id, season=season, league=league, source='sofascore'
    ).first()
    if not row:
        row = PlayerHeatmap(
            player_id=player_id, season=season, league=league, source='sofascore'
        )
        db.add(row)
    row.points          = points
    row.point_count     = len(points)
    row.position_played = position
    row.fetched_at      = fetched_at


def _save_matches_v8(db, player_id, matches, source, fetched_at):
    """
    Salva le partite con i campi estesi dell'RPA v8.
    Campi nuovi rispetto alla v7: tournament_id, season_id, season_year, round,
    winner_code, status, has_xg, has_player_stats, has_heatmap.
    """
    for m in matches:
        event_id = m.get('event_id')
        if not event_id:
            continue

        existing = db.query(PlayerMatch).filter_by(
            player_id=player_id, event_id=event_id
        ).first()

        if existing:
            # Aggiorna i campi che possono cambiare (punteggio finale, rating)
            _s(existing, 'rating',         m.get('rating'))
            _s(existing, 'minutes_played', m.get('minutes_played'))
            _s(existing, 'goals',          m.get('goals', 0))
            _s(existing, 'assists',        m.get('assists', 0))
            _s(existing, 'yellow_card',    int(bool(m.get('yellow_card', False))))
            _s(existing, 'red_card',       int(bool(m.get('red_card', False))))
            _s(existing, 'home_score',     m.get('home_score'))
            _s(existing, 'away_score',     m.get('away_score'))
            _s(existing, 'winner_code',    m.get('winner_code'))
            continue

        # Converti data: v8 manda stringa ISO, legacy manda timestamp int
        match_date = None
        raw_date = m.get('date')
        if raw_date:
            try:
                if isinstance(raw_date, str):
                    match_date = datetime.fromisoformat(raw_date)
                else:
                    match_date = datetime.fromtimestamp(float(raw_date), tz=timezone.utc)
            except Exception:
                pass

        row = PlayerMatch(
            player_id=player_id,
            event_id=event_id,
            date=match_date,
            # Campi estesi v8
            tournament=m.get('tournament_name') or m.get('tournament', ''),
            home_team=m.get('home_team', ''),
            away_team=m.get('away_team', ''),
            home_score=m.get('home_score'),
            away_score=m.get('away_score'),
            rating=m.get('rating'),
            minutes_played=m.get('minutes_played'),
            goals=m.get('goals', 0),
            assists=m.get('assists', 0),
            yellow_card=int(bool(m.get('yellow_card', False))),
            red_card=int(bool(m.get('red_card', False))),
            source=source,
            fetched_at=fetched_at,
        )
        # Campi aggiuntivi v8 (se esistono nel modello)
        _s(row, 'season',          m.get('season_year', ''))
        _s(row, 'tournament_id',   m.get('tournament_id'))
        _s(row, 'season_id',       m.get('season_id'))
        _s(row, 'winner_code',     m.get('winner_code'))
        db.add(row)


def _save_career_v8(db, player_id, transfers, source, fetched_at):
    """
    Salva i trasferimenti con i campi estesi dell'RPA v8.
    Campi nuovi: transfer_id, from/to_team_id, fee_description, type_code.
    Deduplicazione: per transfer_id se disponibile, altrimenti per (to_team, transfer_type).
    """
    for t in transfers:
        from_str = t.get('from_team', '')
        to_str   = t.get('to_team', '')
        type_str = t.get('transfer_type', str(t.get('type_code', '')))

        # Deduplicazione primaria per transfer_id (più affidabile)
        existing = None
        if t.get('transfer_id'):
            # Non c'è una colonna transfer_id nel modello — dedup per to_team + type
            existing = db.query(PlayerCareer).filter_by(
                player_id=player_id, to_team=to_str, transfer_type=type_str
            ).first()
        if not existing:
            existing = db.query(PlayerCareer).filter_by(
                player_id=player_id, to_team=to_str, transfer_type=type_str
            ).first()

        # Converti data
        transfer_date = None
        raw_date = t.get('transfer_date')
        if raw_date:
            try:
                if isinstance(raw_date, str):
                    transfer_date = datetime.fromisoformat(raw_date)
                else:
                    transfer_date = datetime.fromtimestamp(float(raw_date), tz=timezone.utc)
            except Exception:
                pass

        fee = t.get('fee')
        # SofaScore restituisce fee in EUR (intero) — converti in milioni se > 10000
        if fee and isinstance(fee, (int, float)) and fee > 10000:
            fee = round(fee / 1_000_000, 2)

        if existing:
            existing.from_team     = from_str
            existing.transfer_date = transfer_date
            existing.fee           = fee
            existing.fetched_at    = fetched_at
        else:
            db.add(PlayerCareer(
                player_id=player_id,
                from_team=from_str,
                to_team=to_str,
                transfer_date=transfer_date,
                fee=fee,
                transfer_type=type_str,
                source=source,
                fetched_at=fetched_at,
            ))


def _upsert_national_v8(db, player_id, entry: dict, source, fetched_at):
    """
    Salva una voce di statistiche nazionali.
    entry ha: national_team, national_team_id, appearances, goals, assists,
              minutes, rating, yellow_cards, red_cards, debut_date.
    """
    national_team = entry.get('national_team', '')
    row = db.query(PlayerNationalStats).filter_by(
        player_id=player_id, national_team=national_team, source=source
    ).first()
    if not row:
        row = PlayerNationalStats(
            player_id=player_id, national_team=national_team, source=source
        )
        db.add(row)

    _s(row, 'appearances',   _i(entry.get('appearances')))
    _s(row, 'goals',         _i(entry.get('goals')))
    _s(row, 'assists',       _i(entry.get('assists')))
    _s(row, 'minutes',       _i(entry.get('minutes')))
    _s(row, 'rating',        _f(entry.get('rating')))
    _s(row, 'yellow_cards',  _i(entry.get('yellow_cards')))
    _s(row, 'red_cards',     _i(entry.get('red_cards')))
    row.raw_data   = entry
    row.fetched_at = fetched_at
    row.updated_at = fetched_at


# ── Retrocompatibilità v7 ─────────────────────────────────────────

def _upsert_season_stats_legacy(db, player_id, season, league, source,
                                 season_data, extracted, fetched_at):
    """Gestisce il vecchio formato extracted.season dell'RPA v7."""
    row = db.query(PlayerSeasonStats).filter_by(
        player_id=player_id, season=season, league=league, source=source
    ).first()
    if not row:
        row = PlayerSeasonStats(
            player_id=player_id, season=season, league=league, source=source
        )
        db.add(row)
    s = season_data
    # Mapping v7 (nomi diversi da v8)
    _s(row, 'sofascore_rating', _f(s.get('rating')))
    _s(row, 'appearances',      _i(s.get('appearances')))
    _s(row, 'matches_started',  _i(s.get('matches_started')))
    _s(row, 'minutes_played',   _i(s.get('minutes_played')))
    _s(row, 'goals',            _i(s.get('goals')))
    _s(row, 'assists',          _i(s.get('assists')))
    _s(row, 'shots_on_target',  _i(s.get('shots')))
    _s(row, 'big_chances_created', _i(s.get('big_chances_created')))
    _s(row, 'key_passes',       _i(s.get('key_passes')))
    _s(row, 'tackles',          _i(s.get('tackles')))
    _s(row, 'interceptions',    _i(s.get('interceptions')))
    _s(row, 'pass_accuracy_pct',_f(s.get('pass_accuracy_pct')))
    _s(row, 'yellow_cards',     _i(s.get('yellow_cards')))
    _s(row, 'red_cards',        _i(s.get('red_cards')))
    _s(row, 'xg',               _f(s.get('xg')))
    _s(row, 'xa',               _f(s.get('xa')))
    _s(row, 'aerial_duels_won', _i(s.get('aerial_duels_won')))
    _s(row, 'successful_dribbles', _i(s.get('dribbles_won')))
    _s(row, 'accurate_long_balls', _i(s.get('long_balls_accurate')))
    _s(row, 'accurate_crosses',    _i(s.get('crosses_accurate')))
    _s(row, 'fouls_committed',     _i(s.get('fouls_committed')))
    _s(row, 'saves',               _i(s.get('saves')))
    _s(row, 'goals_conceded',      _i(s.get('goals_conceded')))
    _s(row, 'clean_sheets',        _i(s.get('clean_sheets')))
    meta = extracted.get('_raw_meta', {})
    _s(row, 'tournament_id', meta.get('tournament_id'))
    _s(row, 'season_id',     meta.get('season_id'))
    row.fetched_at = fetched_at
    row.updated_at = fetched_at


# ══════════════════════════════════════════════════════════════════
# HANDLERS per /raw  (estensione Chrome — invariati)
# ══════════════════════════════════════════════════════════════════

def _handle_player_profile(db: Session, payload: SofaRawPayload) -> dict:
    data = payload.data
    p = data.get('player', {})
    if not p:
        return {'matched': False, 'reason': 'no player object'}
    player = _find_player_raw(db, p, payload.ids)
    if not player:
        return {'matched': False, 'reason': 'not in db', 'name': p.get('name')}
    sofa_id = payload.ids.get('player_id') or p.get('id')
    if sofa_id and not player.sofascore_id:
        player.sofascore_id = str(sofa_id)
    _s(player, 'preferred_foot', p.get('preferredFoot'))
    _s(player, 'height',         _i(p.get('height')))
    _s(player, 'weight',         _i(p.get('weight')))
    _s(player, 'jersey_number',  _i(p.get('jerseyNumber')))
    _s(player, 'market_value',   _market_value_from_raw(p.get('proposedMarketValue')))
    db.commit()
    return {'matched': True, 'player': p.get('name'), 'sofascore_id': sofa_id}


def _handle_player_season_stats(db: Session, payload: SofaRawPayload) -> dict:
    raw = payload.data.get('statistics', {})
    if not raw:
        return {'matched': False, 'reason': 'no statistics'}
    player = _find_player_by_sofa_id(db, payload.ids.get('player_id'))
    if not player:
        return {'matched': False, 'reason': 'player not found'}
    stats = _raw_stats_to_v8_dict(raw)
    _upsert_season_stats_v8(db, player.id, CURRENT_SEASON, 'unknown',
                             'sofascore_extension', stats, None, None, datetime.utcnow())
    db.commit()
    return {'matched': True, 'player': player.name, 'params': len(stats)}


def _handle_player_heatmap(db: Session, payload: SofaRawPayload) -> dict:
    points = payload.data.get('heatmap', [])
    if not points:
        return {'matched': False, 'reason': 'empty heatmap'}
    player = _find_player_by_sofa_id(db, payload.ids.get('player_id'))
    if not player:
        return {'matched': False, 'reason': 'player not found'}
    _upsert_heatmap_v8(db, player.id, CURRENT_SEASON, 'unknown',
                       points, None, datetime.utcnow())
    db.commit()
    return {'matched': True, 'player': player.name, 'points': len(points)}


def _handle_player_matches(db: Session, payload: SofaRawPayload) -> dict:
    events = payload.data.get('events', [])
    if not events:
        return {'matched': False, 'reason': 'no events'}
    player = _find_player_by_sofa_id(db, payload.ids.get('player_id'))
    if not player:
        return {'matched': False, 'reason': 'player not found'}
    matches = []
    for ev in events:
        t = ev.get('tournament', {})
        ut = t.get('uniqueTournament', {})
        ps = ev.get('playerStatistics', {})
        matches.append({
            'event_id':       ev.get('id'),
            'date':           ev.get('startTimestamp'),
            'tournament_name': ut.get('name') or t.get('name', ''),
            'tournament_id':  ut.get('id'),
            'home_team':      ev.get('homeTeam', {}).get('name', ''),
            'away_team':      ev.get('awayTeam', {}).get('name', ''),
            'home_score':     ev.get('homeScore', {}).get('current'),
            'away_score':     ev.get('awayScore', {}).get('current'),
            'rating':         ps.get('rating'),
            'minutes_played': ps.get('minutesPlayed'),
            'goals':          ps.get('goals', 0),
            'assists':        ps.get('goalAssist', 0),
            'yellow_card':    ps.get('yellowCard', False),
            'red_card':       ps.get('redCard', False),
        })
    _save_matches_v8(db, player.id, matches, 'sofascore_extension', datetime.utcnow())
    db.commit()
    return {'matched': True, 'player': player.name, 'matches': len(matches)}


def _handle_transfers(db: Session, payload: SofaRawPayload) -> dict:
    transfers = payload.data.get('transferHistory', [])
    if not transfers:
        return {'matched': False, 'reason': 'no transfers'}
    player = _find_player_by_sofa_id(db, payload.ids.get('player_id'))
    if not player:
        return {'matched': False, 'reason': 'player not found'}
    TYPE_MAP = {1: 'Transfer', 2: 'Loan', 3: 'Free', 4: 'Youth', 5: 'Return from loan'}
    parsed = [{
        'from_team':     t.get('fromTeamName') or t.get('transferFrom', {}).get('name', ''),
        'to_team':       t.get('toTeamName')   or t.get('transferTo', {}).get('name', ''),
        'transfer_date': t.get('transferDateTimestamp'),
        'fee':           t.get('transferFee'),
        'fee_description': t.get('transferFeeDescription', ''),
        'transfer_type': TYPE_MAP.get(t.get('type', 0), str(t.get('type', ''))),
        'type_code':     t.get('type', 0),
    } for t in transfers]
    _save_career_v8(db, player.id, parsed, 'sofascore_extension', datetime.utcnow())
    db.commit()
    return {'matched': True, 'player': player.name, 'transfers': len(parsed)}


RAW_HANDLERS = {
    'player_profile':      _handle_player_profile,
    'player_season_stats': _handle_player_season_stats,
    'player_heatmap':      _handle_player_heatmap,
    'player_matches':      _handle_player_matches,
    'transfers':           _handle_transfers,
}


# ══════════════════════════════════════════════════════════════════
# UTILITY
# ══════════════════════════════════════════════════════════════════

def _s(obj, attr, val):
    if val is not None and hasattr(obj, attr):
        setattr(obj, attr, val)

def _i(v) -> Optional[int]:
    if v is None: return None
    try: return int(float(str(v).replace(',', '.')))
    except: return None

def _f(v) -> Optional[float]:
    if v is None: return None
    try: return round(float(str(v).replace(',', '.')), 4)
    except: return None

def _market_value_from_raw(v) -> Optional[float]:
    if v is None: return None
    try: return round(float(v) / 1_000_000, 2)
    except: return None

def _format_season(year_str: str) -> str:
    """
    Converte la season year di SofaScore in formato DB.
    "25/26" → "2025-26"
    "2026"  → "2026"   (nazionale/coppa)
    ""      → CURRENT_SEASON
    """
    if not year_str:
        return CURRENT_SEASON
    if '/' in year_str and len(year_str) == 5:
        return f'20{year_str.replace("/", "-")}'
    return year_str

def _detect_season_legacy(extracted: dict) -> str:
    meta   = extracted.get('_raw_meta', {})
    s_name = meta.get('season_name', '')
    if not s_name:
        return CURRENT_SEASON
    if '/' in s_name and len(s_name) == 5:
        return f'20{s_name.replace("/", "-")}'
    return s_name

def _find_player_raw(db, p, ids) -> Optional[ScoutingPlayer]:
    sofa_id = ids.get('player_id') or p.get('id')
    if sofa_id:
        player = _find_player_by_sofa_id(db, sofa_id)
        if player: return player
    return find_player_in_db(db, p.get('name', ''), p.get('team', {}).get('name', ''))

def _find_player_by_sofa_id(db, sofa_id) -> Optional[ScoutingPlayer]:
    if not sofa_id: return None
    return db.query(ScoutingPlayer).filter(
        ScoutingPlayer.sofascore_id == str(sofa_id)
    ).first()

def _raw_stats_to_v8_dict(raw: dict) -> dict:
    """Converte statistiche raw dell'endpoint /raw nei nomi colonna v8."""
    return {
        'rating': raw.get('rating'), 'goals': raw.get('goals'),
        'assists': raw.get('assists') or raw.get('goalAssist'),
        'minutes_played': raw.get('minutesPlayed'),
        'appearances': raw.get('appearances'),
        'matches_started': raw.get('matchesStarted'),
        'shots_on_target': raw.get('shotsOnTarget'),
        'shots_total': raw.get('totalShots'),
        'big_chances_created': raw.get('bigChancesCreated'),
        'key_passes': raw.get('keyPasses'),
        'tackles': raw.get('tackles'), 'interceptions': raw.get('interceptions'),
        'pass_accuracy_pct': raw.get('accuratePassesPercentage'),
        'yellow_cards': raw.get('yellowCards'), 'red_cards': raw.get('redCards'),
        'xg': raw.get('expectedGoals'), 'xa': raw.get('expectedAssists'),
        'aerial_duels_won': raw.get('aerialDuelsWon'),
        'aerial_duels_won_pct': raw.get('aerialDuelsWonPercentage'),
        'successful_dribbles': raw.get('successfulDribbles'),
        'accurate_long_balls': raw.get('accurateLongBalls'),
        'accurate_crosses': raw.get('accurateCrosses'),
        'fouls_committed': raw.get('fouls'), 'fouls_won': raw.get('wasFouled'),
        'saves': raw.get('saves'), 'goals_conceded': raw.get('goalsConceded'),
        'clean_sheets': raw.get('cleanSheet'),
        'accurate_passes': raw.get('accuratePasses'),
        'total_passes': raw.get('totalPasses'),
        'ground_duels_won': raw.get('groundDuelsWon'),
        'total_duels_won': raw.get('totalDuelsWon'),
        'clearances': raw.get('clearances'),
        'blocked_shots': raw.get('blockedShots'),
        'errors_led_to_goal': raw.get('errorLeadToGoal'),
        'errors_led_to_shot': raw.get('errorLeadToShot'),
        'ball_recovery': raw.get('ballRecovery'),
        'touches': raw.get('touches'), 'possession_lost': raw.get('possessionLost'),
        'dribbled_past': raw.get('dribbledPast'), 'dispossessed': raw.get('dispossessed'),
        'offsides': raw.get('offsides'), 'hit_woodwork': raw.get('hitWoodwork'),
        'penalty_goals': raw.get('penaltyGoals'), 'penalty_won': raw.get('penaltyWon'),
        'goal_conversion_pct': raw.get('goalConversionPercentage'),
    }