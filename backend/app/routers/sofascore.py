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
from __future__ import annotations

import json
from datetime import date
from typing import Any
from pydantic import BaseModel
from app.models.models import (
    PlayerSeasonStats,
    PlayerMatch,
    PlayerHeatmap,
    PlayerNationalStats,
)
from app.services.player_matcher import find_player_in_db
from app.services.sources.sofascore_source import _upsert_sofascore_stats

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ScoutingPlayer
from app.models.sofascore_models import PlayerSofascoreStats

log = logging.getLogger(__name__)
router = APIRouter(prefix='/ingest/sofascore', tags=['ingest-sofascore'])

_stats_counter = {'received': 0, 'matched': 0, 'unmatched': 0, 'errors': 0}
CURRENT_SEASON = '2025-26'


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENDPOINT PRINCIPALE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/ocr")
def ingest_sofascore_ocr(
        payload: dict,
        db: Session = Depends(get_db),
):
    """
    Riceve il payload dall'RPA SofaScore e salva tutto nel DB.

    Struttura payload attesa (build_payload in sofascore_rpa.py):
    {
        "name": "...",
        "club": "...",
        "db_id": 123,
        "sofascore_id": 148899,
        "source": "playwright_v9",
        "extracted": {
            "profile": {...},
            "attributes": {...},        ← attributi giocatore (flat dict)
            "attributes_avg": {...},    ← media posizione (flat dict)
            "competitions": [...],      ← lista competizioni con stats + heatmap
            "matches": [...],
            "career": [...],
            "national": [...],
        }
    }
    """
    name = payload.get("name", "")
    db_id = payload.get("db_id")
    sofascore_id = payload.get("sofascore_id")
    extracted = payload.get("extracted", {})

    profile = extracted.get("profile", {})
    attrs = extracted.get("attributes", {}) or {}
    attrs_avg = extracted.get("attributes_avg", {}) or {}
    competitions = extracted.get("competitions", [])
    matches_raw = extracted.get("matches", [])
    career_raw = extracted.get("career", [])
    national_raw = extracted.get("national", [])

    # ── 1. Trova o crea ScoutingPlayer ────────────────────────────────
    player = _resolve_player(db, name, db_id, sofascore_id)
    if not player:
        raise HTTPException(
            status_code=404,
            detail=f"Giocatore '{name}' non trovato. Crea prima l'anagrafica."
        )

    # ── 2. Aggiorna anagrafica da profilo SofaScore ───────────────────
    _update_profile(player, profile, sofascore_id)
    player.last_updated_sofascore = datetime.now(timezone.utc)

    # ── 3. Upsert PlayerSofascoreStats per ogni competizione ──────────
    upserted_stats: list[PlayerSofascoreStats] = []

    for comp in competitions:
        stats_dict = comp.get("statistics", {})
        if not stats_dict:
            continue

        season_year = comp.get("season_year", "")
        season_name = comp.get("season_name", "")
        league_name = _normalize_league(
            comp.get("tournament_name", ""),
            season_year,
            season_name,
        )
        season_label = _season_label(season_year, season_name)

        row = _upsert_sofascore_stats(
            db,
            player_id=player.id,
            season=season_label,
            league=league_name,
            stats_dict=stats_dict,
            tournament_id=comp.get("tournament_id"),
            season_id=comp.get("season_id"),
            club=player.club,
        )
        upserted_stats.append(row)

        # AGGIUNGI QUESTO BLOCCO ALLA FINE DEL CICLO FOR:
        # Salviamo la heatmap che l'RPA ha gentilmente infilato qui dentro!
        heatmap_points = comp.get("heatmap_points", [])
        if heatmap_points:
            _upsert_heatmap_v8(
                db=db,
                player_id=player.id,
                season=season_label,
                league=league_name,
                points=heatmap_points,
                position='unknown',
                fetched_at=datetime.now(timezone.utc)
            )

    # ── 4. Salva attributi blob sulla riga con più minuti ─────────────
    #       (ex scouting_players.sofascore_attributes_raw)
    if attrs and upserted_stats:
        main_row = max(
            upserted_stats,
            key=lambda r: r.minutes_played or 0,
        )
        main_row.attributes_raw = attrs if attrs else None
        main_row.attributes_avg_raw = attrs_avg if attrs_avg else None
        log.info(
            f"  Attributi salvati su player_sofascore_stats "
            f"(league={main_row.league}, mins={main_row.minutes_played})"
        )

    # ── 5. Salva heatmap (su PlayerSofascoreStats) ────────────────────
    #       SofaScore non ha tabella separata per heatmap: li salviamo
    #       come JSON nella riga della competizione corrispondente.
    #       Se hai una tabella player_sofascore_heatmaps, adatta qui.
    for comp in competitions:
        heatmap_points = comp.get("heatmap_points", [])
        if not heatmap_points:
            continue
        season_year = comp.get("season_year", "")
        season_name = comp.get("season_name", "")
        league_name = _normalize_league(
            comp.get("tournament_name", ""),
            season_year, season_name,
        )
        season_label = _season_label(season_year, season_name)

        # Cerca la riga corrispondente tra quelle già upsertate
        matching = next(
            (r for r in upserted_stats
             if r.league == league_name and r.season == season_label),
            None,
        )
        if matching and not getattr(matching, 'heatmap_points', None):
            # Se il modello ha il campo heatmap_points, salvalo
            if hasattr(matching, 'heatmap_points'):
                matching.heatmap_points = heatmap_points

    # ── 6. Upsert partite ────────────────────────────────────────────
    if matches_raw:
        _upsert_matches(db, player.id, matches_raw)

    # ── 7. Upsert carriera/trasferimenti ─────────────────────────────
    if career_raw:
        _upsert_career(db, player.id, career_raw)

    # ── 8. Ricalcola PlayerScoutingIndex ──────────────────────────────
    #       (identico a come fa import_json.py dopo FBref)
    try:
        from app.routers.fbref.scoring import compute_scouting_index
        db.flush()
        compute_scouting_index(db, player)
        log.info(f"  PlayerScoutingIndex ricalcolato per {player.name}")
    except Exception as e:
        log.warning(f"  Scoring index skipped: {e}")

    db.commit()

    n_stats = len(upserted_stats)
    n_comps = len(competitions)
    n_match = len(matches_raw)
    n_career = len(career_raw)

    log.info(
        f"✓ {player.name} (id={player.id}): "
        f"{n_comps} competizioni, {n_stats} stats rows, "
        f"{n_match} partite, {n_career} carriera"
    )
    return {
        "ok": True,
        "player_id": player.id,
        "name": player.name,
        "competitions": n_comps,
        "stats_rows": n_stats,
        "matches": n_match,
        "career": n_career,
    }


@router.post("/player-done")
def player_done(payload: dict, db: Session = Depends(get_db)):
    """Callback leggero dell'RPA: aggiorna last_updated_sofascore."""
    db_id = payload.get("db_id")
    sofascore_id = payload.get("sofascore_id")
    name = payload.get("name", "")

    player = _resolve_player(db, name, db_id, sofascore_id)
    if player:
        player.last_updated_sofascore = datetime.now(timezone.utc)
        db.commit()
    return {"ok": True}

@router.get('/status')
async def status():
    return {'status': 'running', 'stats': _stats_counter,
            'timestamp': datetime.utcnow().isoformat()}


# ══════════════════════════════════════════════════════════════════
# HELPERS — v8 (multi-competizione)
# ══════════════════════════════════════════════════════════════════
def _find_player_for_ocr(db, payload):
    season = None
    profile = payload.extracted.get('profile', {})
    # La season viene dalla prima competition del payload
    competitions = payload.extracted.get('competitions', [])
    if competitions:
        season = _format_season(competitions[0].get('season_year', ''))

    if payload.db_id:
        p = db.query(ScoutingPlayer).filter(ScoutingPlayer.id == payload.db_id).first()
        if p: return p
    if payload.sofascore_id:
        p = db.query(ScoutingPlayer).filter(
            ScoutingPlayer.sofascore_id == str(payload.sofascore_id)
        ).first()
        if p: return p
    return find_player_in_db(db, payload.name, payload.club, season=season)


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
    Versione ATOMICA (PostgreSQL Upsert) per evitare errori UniqueViolation.
    """
    # Prepariamo il dizionario con i dati base
    data_to_insert = {
        "player_id": player_id,
        "season": season,
        "league": league,
        "source": source,
        "tournament_id": tournament_id,
        "season_id": season_id,
        "fetched_at": fetched_at,
        "updated_at": fetched_at
    }

    # Mappiamo i campi degli stats nel dizionario, convertendo i tipi
    for field, value in stats.items():
        if value is None:
            continue

        # Verifica se la colonna esiste nel modello
        col = PlayerSeasonStats.__table__.c.get(field)
        if col is None:
            continue

        col_type = str(col.type).upper()
        try:
            if 'INT' in col_type:
                data_to_insert[field] = _i(value)
            elif any(t in col_type for t in ['FLOAT', 'REAL', 'NUMERIC']):
                data_to_insert[field] = _f(value)
            else:
                data_to_insert[field] = value
        except:
            continue

    # Costruiamo lo statement di UPSERT
    stmt = insert(PlayerSeasonStats).values(data_to_insert)

    # Definiamo cosa aggiornare in caso di conflitto (tutto tranne le chiavi della JOIN)
    update_cols = {
        k: v for k, v in data_to_insert.items()
        if k not in ['player_id', 'season', 'league', 'source']
    }

    # Se c'è conflitto sulla constraint uq_player_season_league_source, fai l'UPDATE
    stmt = stmt.on_conflict_do_update(
        constraint="uq_player_season_league_source",
        set_=update_cols
    )

    # Eseguiamo direttamente
    db.execute(stmt)

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
    Salva i trasferimenti con season.
    La season viene derivata dalla transfer_date quando disponibile,
    altrimenti dalla chiave 'season' nel payload (mappata dall'RPA).
    """
    from app.models.models import PlayerCareer

    def _i(v):
        if v is None: return None
        try:
            return int(float(str(v).replace(',', '.')))
        except:
            return None

    def _f(v):
        if v is None: return None
        try:
            return round(float(str(v).replace(',', '.')), 4)
        except:
            return None

    def _s(obj, attr, val):
        if val is not None and hasattr(obj, attr):
            setattr(obj, attr, val)

    for t in transfers:
        from_str = t.get('from_team', '')
        to_str = t.get('to_team', '')
        type_str = t.get('transfer_type', str(t.get('type_code', '')))

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

        # Deriva season dalla data del trasferimento
        # Convenzione: trasferimento estate (Jun-Aug) → stagione che inizia quell'anno
        # Es: trasferimento Ago 2024 → season "2024-25"
        season_str = t.get('season', '')  # l'RPA può mandarlo esplicitamente
        if not season_str and transfer_date:
            yr = transfer_date.year
            mo = transfer_date.month
            if mo >= 6:
                season_str = f'{yr}-{str(yr + 1)[-2:]}'
            else:
                season_str = f'{yr - 1}-{str(yr)[-2:]}'

        fee = t.get('fee')
        if fee and isinstance(fee, (int, float)) and fee > 10000:
            fee = round(fee / 1_000_000, 2)

        # Deduplicazione: (player_id, to_team, transfer_type, season)
        existing = db.query(PlayerCareer).filter_by(
            player_id=player_id, to_team=to_str, transfer_type=type_str
        ).first()

        if existing:
            existing.from_team = from_str
            existing.transfer_date = transfer_date
            existing.fee = fee
            existing.fetched_at = fetched_at
            if season_str:
                existing.season = season_str
        else:
            row = PlayerCareer(
                player_id=player_id,
                from_team=from_str,
                to_team=to_str,
                transfer_date=transfer_date,
                fee=fee,
                transfer_type=type_str,
                season=season_str or None,
                source=source,
                fetched_at=fetched_at,
            )
            db.add(row)


from sqlalchemy.dialects.postgresql import insert  # Assicurati che questo import sia presente in alto


def _upsert_national_v8(db, player_id, entry: dict, source, fetched_at):
    """
    Versione ATOMICA per evitare UniqueViolation su player_national_stats.
    Constraint: uq_national_player_team (player_id, national_team, source)
    """
    national_team = entry.get('national_team')
    if not national_team:
        return

    # Prepariamo i dati per l'inserimento/aggiornamento
    base_values = {
        "player_id": player_id,
        "national_team": national_team,
        "season": entry.get('season_year', '2025-26'),  # Default se manca
        "appearances": _i(entry.get('appearances')),
        "goals": _i(entry.get('goals')),
        "assists": _i(entry.get('assists')),
        "minutes": _i(entry.get('minutes')),
        "rating": _f(entry.get('rating')),
        "yellow_cards": _i(entry.get('yellow_cards')),
        "red_cards": _i(entry.get('red_cards')),
        "raw_data": json.dumps(entry),
        "source": source,
        "fetched_at": fetched_at,
        "updated_at": fetched_at
    }

    # Costruiamo lo statement di UPSERT
    stmt = insert(PlayerNationalStats).values(base_values)

    # In caso di conflitto su (player_id, national_team, source), aggiorna i dati
    update_cols = {
        k: v for k, v in base_values.items()
        if k not in ['player_id', 'national_team', 'source']
    }

    stmt = stmt.on_conflict_do_update(
        constraint="uq_national_player_team",
        set_=update_cols
    )

    db.execute(stmt)

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

        # Gestione Data e Stagione (Fix per la colonna Season vuota)
        ts = ev.get('startTimestamp')
        from datetime import datetime
        dt_obj = datetime.fromtimestamp(ts) if ts else None
        season_label = ""
        if dt_obj:
            year = dt_obj.year
            season_label = f"{year}/{year + 1}" if dt_obj.month >= 8 else f"{year - 1}/{year}"

        # Mappiamo i dati usando i nomi esatti che il database si aspetta
        matches.append({
            'event_id': str(ev.get('id')),
            #'date': dt_obj,
            'date': ev.get('startTimestamp'),
            # Cambiato 'tournament_name' in 'tournament' per matchare il DB
            'tournament': ut.get('name') or t.get('name', ''),
            'season': season_label,
            'home_team': ev.get('homeTeam', {}).get('name', ''),
            'away_team': ev.get('awayTeam', {}).get('name', ''),
            "home_score": ev.get("home_score") or ev.get("homeScore", {}).get("current"),
            "away_score": ev.get("away_score") or ev.get("awayScore", {}).get("current"),
            # Stats (Fix Rating e Minuti)
            'rating': ps.get('rating'),
            'minutes_played': ps.get('minutesPlayed'),
            'goals': ps.get('goals', 0),
            'assists': ps.get('goalAssist', 0),
            'yellow_card': 1 if ps.get('yellowCard') else 0,
            'red_card': 1 if ps.get('redCard') else 0,
        })

    # Usiamo _save_matches_v8 ma con i dati puliti
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _resolve_player(
        db: Session,
        name: str,
        db_id: Optional[int],
        sofascore_id: Optional[int],
) -> Optional[ScoutingPlayer]:
    """Cerca il giocatore per db_id, poi sofascore_id, poi nome."""
    if db_id:
        p = db.query(ScoutingPlayer).filter_by(id=db_id).first()
        if p:
            return p
    if sofascore_id:
        p = db.query(ScoutingPlayer).filter_by(sofascore_id=str(sofascore_id)).first()
        if p:
            return p
    if name:
        p = db.query(ScoutingPlayer).filter(
            ScoutingPlayer.name.ilike(f"%{name.split()[-1]}%")
        ).first()
        if p:
            return p
    return None


def _update_profile(
        player: ScoutingPlayer,
        profile: dict,
        sofascore_id: Optional[int],
) -> None:
    """
    Aggiorna i campi anagrafici su ScoutingPlayer da profilo SofaScore.
    Sovrascrive solo i campi vuoti (non sovrascrive dati già presenti
    da fonti più affidabili come TransferMarkt).
    """
    if sofascore_id and not player.sofascore_id:
        player.sofascore_id = sofascore_id

    # Cache rating UI (sempre aggiornata)
    if profile.get("sofascore_rating") is not None:
        player.sofascore_rating = profile["sofascore_rating"]

    # Anagrafica: aggiorna solo se vuota
    _set_if_empty(player, "height", profile.get("height_cm"))
    _set_if_empty(player, "weight", profile.get("weight_kg"))
    _set_if_empty(player, "preferred_foot", profile.get("preferred_foot"))
    _set_if_empty(player, "jersey_number", profile.get("jersey_number"))
    _set_if_empty(player, "market_value", profile.get("market_value"))
    _set_if_empty(player, "nationality", profile.get("nationality"))
    _set_if_empty(player, "gender", profile.get("gender"))

    # Posizione: aggiorna sempre (SS è la fonte più aggiornata)
    if profile.get("position"):
        player.position = profile["position"]
    if profile.get("position_detail"):
        player.position_detail = profile["position_detail"]

    # Contract: aggiorna sempre
    if profile.get("contract_until"):
        try:
            from datetime import date
            player.contract_until = date.fromisoformat(str(profile["contract_until"])[:10])
        except Exception:
            pass


def _set_if_empty(obj, attr: str, value) -> None:
    if value is not None and getattr(obj, attr, None) is None:
        setattr(obj, attr, value)


def _normalize_league(tournament_name: str, season_year: str, season_name: str) -> str:
    """Normalizza il nome torneo verso i nomi standard del DB."""
    name = tournament_name.strip()
    mapping = {
        "Serie A": "Serie A",
        "Premier League": "Premier League",
        "La Liga": "La Liga",
        "Bundesliga": "Bundesliga",
        "Ligue 1": "Ligue 1",
        "UEFA Champions League": "Champions League",
        "Champions League": "Champions League",
        "UEFA Europa League": "Europa League",
        "Europa League": "Europa League",
        "UEFA Conference League": "Conference League",
        "Coppa Italia": "Coppa Italia",
        "FA Cup": "FA Cup",
        "DFB-Pokal": "DFB-Pokal",
        "Ligue 2": "Ligue 2",
        "Supercoppa Italiana": "Supercoppa Italiana",
        "Super Cup": "Super Cup",
    }
    for key, val in mapping.items():
        if key.lower() in name.lower():
            return val
    return name or "Unknown"


def _season_label(season_year: str, season_name: str) -> str:
    """
    Produce un'etichetta stagione coerente con player_fbref_stats.season.
    Esempi: "24/25" → "2024-25",  "2025/2026" → "2025-26"
    """
    y = (season_year or season_name or "").strip()
    # Gestisci formati: "24/25", "2024/25", "2025/2026"
    if "/" in y:
        parts = y.split("/")
        p0, p1 = parts[0].strip(), parts[1].strip()
        if len(p0) == 2:
            p0 = "20" + p0
        if len(p1) == 2:
            p1_full = p0[:2] + p1
        else:
            p1_full = p1[-2:]  # prendi ultime 2 cifre di "2026" → "26"
        return f"{p0}-{p1_full}"
    # Già formato "2025-26"
    if "-" in y and len(y) == 7:
        return y
    # Fallback: stagione corrente
    now = datetime.utcnow()
    m = now.month
    s = now.year if m >= 7 else now.year - 1
    return f"{s}-{str(s + 1)[-2:]}"


def _upsert_sofascore_stats(
        db: Session,
        player_id: int,
        season: str,
        league: str,
        stats_dict: dict,
        tournament_id: Optional[int],
        season_id: Optional[int],
        club: Optional[str],
) -> PlayerSofascoreStats:
    """Upsert su player_sofascore_stats. Ritorna la riga (nuova o aggiornata)."""
    row = db.query(PlayerSofascoreStats).filter_by(
        player_id=player_id,
        season=season,
        league=league,
    ).first()

    if not row:
        row = PlayerSofascoreStats(
            player_id=player_id,
            season=season,
            league=league,
        )
        db.add(row)

    # Campi di contesto
    row.tournament_id = tournament_id
    row.season_id = season_id
    row.season_club = club
    row.updated_at = datetime.now(timezone.utc)

    # Stats — mappa dal dict flat del payload ai campi ORM
    # Usa .get() su tutti: se non c'è, non sovrascrivere il valore esistente
    # (preferisci mantenere il dato precedente se il nuovo è None)
    def _set(attr, key, cast=None):
        val = stats_dict.get(key)
        if val is not None:
            if cast:
                try:
                    val = cast(val)
                except Exception:
                    return
            setattr(row, attr, val)

    _set("sofascore_rating", "rating", float)
    _set("appearances", "appearances", int)
    _set("matches_started", "matches_started", int)
    _set("minutes_played", "minutes_played", int)
    _set("goals", "goals", int)
    _set("assists", "assists", int)
    _set("goals_assists_sum", "goals_assists_sum", int)
    _set("shots_total", "shots_total", int)
    _set("shots_on_target", "shots_on_target", int)
    _set("shots_off_target", "shots_off_target", int)
    _set("big_chances_created", "big_chances_created", int)
    _set("big_chances_missed", "big_chances_missed", int)
    _set("goal_conversion_pct", "goal_conversion_pct", float)
    _set("headed_goals", "headed_goals", int)
    _set("penalty_goals", "penalty_goals", int)
    _set("penalty_won", "penalty_won", int)
    _set("xg", "xg", float)
    _set("xa", "xa", float)
    _set("accurate_passes", "accurate_passes", int)
    _set("inaccurate_passes", "inaccurate_passes", int)
    _set("total_passes", "total_passes", int)
    _set("pass_accuracy_pct", "pass_accuracy_pct", float)
    _set("accurate_long_balls", "accurate_long_balls", int)
    _set("long_ball_accuracy_pct", "long_ball_accuracy_pct", float)
    _set("total_long_balls", "total_long_balls", int)
    _set("accurate_crosses", "accurate_crosses", int)
    _set("cross_accuracy_pct", "cross_accuracy_pct", float)
    _set("total_crosses", "total_crosses", int)
    _set("key_passes", "key_passes", int)
    _set("accurate_own_half_passes", "accurate_own_half_passes", int)
    _set("accurate_opp_half_passes", "accurate_opp_half_passes", int)
    _set("accurate_final_third_passes", "accurate_final_third_passes", int)
    _set("successful_dribbles", "successful_dribbles", int)
    _set("dribble_success_pct", "dribble_success_pct", float)
    _set("dribbled_past", "dribbled_past", int)
    _set("dispossessed", "dispossessed", int)
    _set("ground_duels_won", "ground_duels_won", int)
    _set("ground_duels_won_pct", "ground_duels_won_pct", float)
    _set("aerial_duels_won", "aerial_duels_won", int)
    _set("aerial_duels_lost", "aerial_duels_lost", int)
    _set("aerial_duels_won_pct", "aerial_duels_won_pct", float)
    _set("total_duels_won", "total_duels_won", int)
    _set("total_duels_won_pct", "total_duels_won_pct", float)
    _set("total_contest", "total_contest", int)
    _set("tackles", "tackles", int)
    _set("tackles_won", "tackles_won", int)
    _set("tackles_won_pct", "tackles_won_pct", float)
    _set("interceptions", "interceptions", int)
    _set("clearances", "clearances", int)
    _set("blocked_shots", "blocked_shots", int)
    _set("errors_led_to_goal", "errors_led_to_goal", int)
    _set("errors_led_to_shot", "errors_led_to_shot", int)
    _set("ball_recovery", "ball_recovery", int)
    _set("possession_won_att_third", "possession_won_att_third", int)
    _set("touches", "touches", int)
    _set("possession_lost", "possession_lost", int)
    _set("yellow_cards", "yellow_cards", int)
    _set("yellow_red_cards", "yellow_red_cards", int)
    _set("red_cards", "red_cards", int)
    _set("fouls_committed", "fouls_committed", int)
    _set("fouls_won", "fouls_won", int)
    _set("offsides", "offsides", int)
    _set("hit_woodwork", "hit_woodwork", int)
    _set("saves", "saves", int)
    _set("goals_conceded", "goals_conceded", int)
    _set("clean_sheets", "clean_sheets", int)
    _set("penalty_saved", "penalty_saved", int)
    _set("penalty_faced", "penalty_faced", int)
    _set("high_claims", "high_claims", int)
    _set("punches", "punches", int)

    # xG/xA per90: calcola se minuti disponibili e xg/xa presenti
    mins = row.minutes_played
    if mins and mins > 0:
        if row.xg is not None and not row.xg_per90:
            row.xg_per90 = round(row.xg / (mins / 90.0), 4)
        if row.xa is not None and not row.xa_per90:
            row.xa_per90 = round(row.xa / (mins / 90.0), 4)

    # Scrive immediatamente le modifiche nel DB (senza chiudere la transazione)
    db.flush()

    return row


def _upsert_matches(db, player_id: int, matches: list) -> None:
    """
    Salva/aggiorna le partite nella tabella player_matches.

    Il parametro `matches` è la lista già mappata da _map_matches()
    in sofascore_rpa.py: tutti i campi sono piatti e già convertiti
    (date è stringa ISO, home_score/away_score sono int, ecc.).
    """
    for m in matches:
        # ── event_id ──────────────────────────────────────────────────
        event_id = m.get("event_id")
        if not event_id:
            continue

        # ── BUG 1 FIX: date e season ──────────────────────────────────
        # _map_matches() ha già convertito startTimestamp in 'date' (stringa ISO)
        # e season_year in 'season_year'. NON cercare "startTimestamp".
        match_date = None
        raw_date = m.get("date")  # es. "2024-11-03T20:00:00+00:00"
        if raw_date:
            try:
                if isinstance(raw_date, str):
                    match_date = datetime.fromisoformat(raw_date)
                else:
                    # legacy: timestamp int (non dovrebbe arrivare dal v9)
                    match_date = datetime.fromtimestamp(float(raw_date), tz=timezone.utc)
            except Exception:
                pass

        # season_year è il campo dell'RPA: "24/25" o "2024/25" ecc.
        # Lo usiamo direttamente come stringa season (il modello accetta String(10))
        season_val = m.get("season_year") or m.get("season_name") or ""

        # ── BUG 2 FIX: rating e minutes_played ────────────────────────
        # _map_matches() ha già spianato playerStatistics al livello root:
        #   m["rating"]         (float o None)
        #   m["minutes_played"] (int o None)
        #   m["goals"]          (int, default 0)
        #   m["assists"]        (int, default 0)
        # NON cercare m.get("playerStatistics").
        rating_val = m.get("rating")  # già float o None
        mins_val = m.get("minutes_played")  # già int o None
        goals_val = m.get("goals", 0)
        assists_val = m.get("assists", 0)
        yellow_val = m.get("yellow_card", False)
        red_val = m.get("red_card", False)

        # ── BUG 3 FIX: home_score / away_score ────────────────────────
        # _map_matches() ha già convertito homeScore.current → home_score (int)
        # NON fare m.get("homeScore", {}).get("current").
        home_score_val = m.get("home_score")  # già int o None
        away_score_val = m.get("away_score")  # già int o None

        # ── Altri campi disponibili dal mapping v9 ─────────────────────
        tournament_val = m.get("tournament_name") or m.get("tournament", "")
        home_team_val = m.get("home_team", "")
        away_team_val = m.get("away_team", "")

        # ── Upsert ────────────────────────────────────────────────────
        existing = db.query(PlayerMatch).filter_by(
            player_id=player_id,
            event_id=event_id,
        ).first()

        if existing:
            # Aggiorna sempre: potremmo avere record vecchi con campi NULL
            # (precedente versione buggata), quindi forziamo la riscrittura.
            if match_date is not None:
                existing.date = match_date
            if season_val:
                existing.season = season_val
            existing.rating = float(rating_val) if rating_val is not None else existing.rating
            existing.minutes_played = int(mins_val) if mins_val is not None else existing.minutes_played
            existing.goals = int(goals_val) if goals_val is not None else 0
            existing.assists = int(assists_val) if assists_val is not None else 0
            existing.yellow_card = 1 if yellow_val else 0
            existing.red_card = 1 if red_val else 0
            if home_score_val is not None:
                existing.home_score = int(home_score_val)
            if away_score_val is not None:
                existing.away_score = int(away_score_val)
            if tournament_val:
                existing.tournament = tournament_val
            if home_team_val:
                existing.home_team = home_team_val
            if away_team_val:
                existing.away_team = away_team_val
        else:
            obj = PlayerMatch(
                player_id=player_id,
                event_id=int(event_id),
                date=match_date,
                season=season_val or None,
                tournament=tournament_val,
                home_team=home_team_val,
                away_team=away_team_val,
                home_score=int(home_score_val) if home_score_val is not None else None,
                away_score=int(away_score_val) if away_score_val is not None else None,
                rating=float(rating_val) if rating_val is not None else None,
                minutes_played=int(mins_val) if mins_val is not None else None,
                goals=int(goals_val) if goals_val is not None else 0,
                assists=int(assists_val) if assists_val is not None else 0,
                yellow_card=1 if yellow_val else 0,
                red_card=1 if red_val else 0,
                source="sofascore",
            )
            db.add(obj)

    db.flush()

def _upsert_career(db: Session, player_id: int, career: list) -> None:
    """Upsert trasferimenti/carriera."""
    try:
        from app.models.models import PlayerCareer
    except ImportError:
        return

    for t in career:
        transfer_id = t.get("transfer_id")
        if not transfer_id:
            continue
        existing = db.query(PlayerCareer).filter_by(
            player_id=player_id,
            from_team=t.get("from_team"),
            to_team=t.get("to_team")
        ).first()
        if existing:
            continue
        obj = PlayerCareer(player_id=player_id, **{
            k: v for k, v in t.items()
            if k != "transfer_id" and hasattr(PlayerCareer, k)
        })
        obj.transfer_id = transfer_id
        db.add(obj)

