"""
app/ingest/fbref/import_json.py

Legge tutti i file *_complete.json dalla directory data/fbref,
li mappa sui modelli PlayerFbrefStats e PlayerFbrefMatchLog,
poi ricalcola il PlayerScoutingIndex per ogni giocatore importato.

Utilizzo da riga di comando (dalla root del backend):
    python -m app.ingest.fbref.import_json

Utilizzo programmatico:
    from app.ingest.fbref.import_json import run_import
    run_import()          # importa tutti i JSON
    run_import("leonardo_spinazzola_complete.json")  # solo un file
"""

import json

import logging
import os
from datetime import datetime, timezone # Assicurati di avere questo import in alto
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import ScoutingPlayer
from app.models.fbref_models import (
    PlayerFbrefStats,
    PlayerFbrefMatchLog,
    PlayerScoutingIndex,
)
from app.routers.fbref.scoring import compute_scouting_index

log = logging.getLogger("FBRefImport")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ── Percorso directory JSON ───────────────────────────────────────
# Costruito in modo relativo per funzionare sia su Windows che Mac/Linux.
# Su Windows diventa: ..\data\fbref   →   D:\...\backend\app\data\fbref
CURRENT_DIR = Path(__file__).resolve().parent          # app/ingest/fbref
DATA_DIR = CURRENT_DIR.parents[1] / "data" / "fbref"  # app/data/fbref


# ═════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════

def _int(val) -> int | None:
    """Converte stringa FBref in int, gestisce vuoti e virgole."""
    if val is None or val == "" or val == "Matches":
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _float(val) -> float | None:
    """Converte stringa FBref in float."""
    if val is None or val == "" or val == "Matches":
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _clean_team(team: str) -> str:
    """Rimuove prefissi nazionalità tipo 'it Napoli' → 'Napoli'."""
    if not team:
        return team
    parts = team.strip().split(" ", 1)
    if len(parts) == 2 and len(parts[0]) <= 3 and parts[0].islower():
        return parts[1]
    return team


def _clean_opponent(opp: str) -> str:
    """Rimuove prefissi nazionalità tipo 'eng Manchester City' → 'Manchester City'."""
    return _clean_team(opp)


def _comp_to_league(comp: str) -> str:
    """
    Normalizza il nome competizione dai match_logs verso il nome standard.
    FBref usa nomi brevi nei match_logs (es. "Champions Lg") diversi da
    quelli in comp_level delle tables (es. "UEFA Champions League").
    """
    mapping = {
        "Champions Lg":    "Champions League",
        "UEFA Champions":  "Champions League",
        "Europa Lg":       "Europa League",
        "UEFA Europa":     "Europa League",
        "Conference Lg":   "Conference League",
        "WCQ":             "World Cup Qual.",
        "EURO Qual.":      "Euro Qual.",
        "Coppa Italia":    "Coppa Italia",
        "DFB-Pokal":       "DFB-Pokal",
        "FA Cup":          "FA Cup",
        "EFL Cup":         "EFL Cup",
        "Supercoppa":      "Supercoppa Italiana",
        "Super Cup":       "Super Cup",
    }
    for key, val in mapping.items():
        if key.lower() in comp.lower():
            return val
    return comp


def _aggregate_stats_from_logs(
    player_id: int,
    season: str,
    match_logs: list[dict],
    fbref_player_id: str | None,
) -> list[PlayerFbrefStats]:
    """
    Aggrega i match_logs per competizione e crea righe PlayerFbrefStats
    per le competizioni che non hanno una riga nelle 'tables' del JSON.

    FBref fornisce statistiche aggregate (xG, passaggi, ecc.) solo per
    la competizione principale nelle 'tables'. Le altre competizioni
    (Champions League, Coppa Italia, ecc.) compaiono solo nel match_log.
    Questa funzione calcola i totali contabili (gol, assist, minuti, ecc.)
    direttamente dai match_logs per colmare quel gap.
    """
    from collections import defaultdict

    # Aggrega per competizione
    by_comp: dict[str, dict] = defaultdict(lambda: {
        "appearances": 0,
        "starts": 0,
        "minutes": 0,
        "goals": 0,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "shots": 0,
        "shots_on_target": 0,
        "fouls_committed": 0,
        "fouls_drawn": 0,
        "offsides": 0,
        "crosses": 0,
        "tackles_won": 0,
        "interceptions": 0,
        "own_goals": 0,
        "pens_made": 0,
        "pens_att": 0,
    })

    for m in match_logs:
        comp = m.get("comp", "")
        if not comp or comp == "Comp":  # riga di intestazione spurie
            continue
        agg = by_comp[comp]
        mins = _int(m.get("minutes")) or 0
        if mins > 0:
            agg["appearances"] += 1
            if m.get("game_started") == "Y":
                agg["starts"] += 1
            agg["minutes"]        += mins
        agg["goals"]          += _int(m.get("goals"))          or 0
        agg["assists"]        += _int(m.get("assists"))        or 0
        agg["yellow_cards"]   += _int(m.get("cards_yellow"))   or 0
        agg["red_cards"]      += _int(m.get("cards_red"))      or 0
        agg["shots"]          += _int(m.get("shots"))          or 0
        agg["shots_on_target"]+= _int(m.get("shots_on_target"))or 0
        agg["fouls_committed"]+= _int(m.get("fouls"))          or 0
        agg["fouls_drawn"]    += _int(m.get("fouled"))         or 0
        agg["offsides"]       += _int(m.get("offsides"))       or 0
        agg["crosses"]        += _int(m.get("crosses"))        or 0
        agg["tackles_won"]    += _int(m.get("tackles_won"))    or 0
        agg["interceptions"]  += _int(m.get("interceptions"))  or 0
        agg["own_goals"]      += _int(m.get("own_goals"))      or 0
        agg["pens_made"]      += _int(m.get("pens_made"))      or 0
        agg["pens_att"]       += _int(m.get("pens_att"))       or 0

    results = []
    for comp, agg in by_comp.items():
        if agg["minutes"] == 0:
            continue  # salta competizioni senza minuti giocati
        league_name = _comp_to_league(comp)
        m90 = agg["minutes"] / 90.0 if agg["minutes"] > 0 else None

        stats = PlayerFbrefStats(
            player_id       = player_id,
            season          = season,
            league          = league_name,
            fbref_player_id = fbref_player_id,
            appearances     = agg["appearances"],
            starts          = agg["starts"],
            minutes         = agg["minutes"],
            goals           = agg["goals"],
            assists         = agg["assists"],
            pens_made       = agg["pens_made"],
            pens_att        = agg["pens_att"],
            yellow_cards    = agg["yellow_cards"],
            red_cards       = agg["red_cards"],
            goals_per90     = round(agg["goals"] / m90, 2) if m90 else None,
            assists_per90   = round(agg["assists"] / m90, 2) if m90 else None,
            # Shooting
            shots           = agg["shots"],
            shots_on_target = agg["shots_on_target"],
            shots_on_target_pct = round(agg["shots_on_target"] / agg["shots"] * 100, 1)
                                  if agg["shots"] > 0 else None,
            shots_per90     = round(agg["shots"] / m90, 2) if m90 else None,
            goals_per_shot  = round(agg["goals"] / agg["shots"], 2)
                              if agg["shots"] > 0 else None,
            # Misc
            fouls_committed = agg["fouls_committed"],
            fouls_drawn     = agg["fouls_drawn"],
            offsides        = agg["offsides"],
            crosses         = agg["crosses"],
            own_goals       = agg["own_goals"],
            # Defense (da match_logs)
            tackles_won     = agg["tackles_won"],
            interceptions   = agg["interceptions"],
        )
        results.append((league_name, stats))

    return results


def _extract_season(tables: dict) -> str:
    """Legge year_id dalla prima tabella non-null."""
    for t in tables.values():
        if t and t.get("year_id"):
            return t["year_id"]
    return "unknown"


def _extract_league(tables: dict) -> str:
    """Legge comp_level e restituisce il nome pulito della competizione."""
    for t in tables.values():
        if t and t.get("comp_level"):
            # "1. Serie A" → "Serie A"
            raw = t["comp_level"]
            parts = raw.split(". ", 1)
            return parts[1] if len(parts) == 2 else raw
    return "unknown"


def _resolve_player(db: Session, player_name: str, fbref_id: str | None) -> ScoutingPlayer | None:
    """
    Trova il giocatore nel DB.
    Strategia: prima per fbref_id (se disponibile), poi per nome esatto.
    """
    if fbref_id:
        player = db.query(ScoutingPlayer).filter(
            ScoutingPlayer.fbref_id == fbref_id
        ).first()
        if player:
            return player

    # Fallback: ricerca per nome (case-insensitive)
    player = db.query(ScoutingPlayer).filter(
        ScoutingPlayer.name.ilike(player_name.strip())
    ).first()
    return player


# ═════════════════════════════════════════════════════════════════
# MAPPER: tables dict → PlayerFbrefStats
# ═════════════════════════════════════════════════════════════════

def _map_fbref_stats(
    player_id: int,
    season: str,
    league: str,
    tables: dict,
    fbref_player_id: str | None,
) -> PlayerFbrefStats:

    std  = tables.get("standard")  or {}
    sh   = tables.get("shooting")  or {}
    pas  = tables.get("passing")   or {}
    gca  = tables.get("gca")       or {}
    defs = tables.get("defense")   or {}
    poss = tables.get("possession") or {}
    misc = tables.get("misc")      or {}

    return PlayerFbrefStats(
        player_id   = player_id,
        season      = season,
        league      = league,
        fbref_player_id = fbref_player_id,

        # Standard
        appearances     = _int(std.get("games")),
        starts          = _int(std.get("games_starts")),
        minutes         = _int(std.get("minutes")),
        goals           = _int(std.get("goals")),
        assists         = _int(std.get("assists")),
        goals_pens      = _int(std.get("goals_pens")),
        pens_made       = _int(std.get("pens_made")),
        pens_att        = _int(std.get("pens_att")),
        yellow_cards    = _int(std.get("cards_yellow")),
        red_cards       = _int(std.get("cards_red")),
        xg              = _float(std.get("xg")),
        npxg            = _float(std.get("npxg")),
        xa              = _float(std.get("xa")),
        npxg_xa         = _float(std.get("npxg_xa")),
        goals_per90     = _float(std.get("goals_per90")),
        assists_per90   = _float(std.get("assists_per90")),
        xg_per90        = _float(std.get("xg_per90")),
        xa_per90        = _float(std.get("xa_per90")),
        npxg_per90      = _float(std.get("npxg_per90")),

        # Shooting
        shots               = _int(sh.get("shots")),
        shots_on_target     = _int(sh.get("shots_on_target")),
        shots_on_target_pct = _float(sh.get("shots_on_target_pct")),
        shots_per90         = _float(sh.get("shots_per90")),
        sot_per90           = _float(sh.get("shots_on_target_per90")),
        goals_per_shot      = _float(sh.get("goals_per_shot")),
        goals_per_sot       = _float(sh.get("goals_per_shot_on_target")),
        avg_shot_distance   = _float(sh.get("average_shot_distance")),
        npxg_per_shot       = _float(sh.get("npxg_per_shot")),
        xg_net              = _float(sh.get("xg_net")),
        npxg_net            = _float(sh.get("npxg_net")),

        # Passing
        passes_completed       = _int(pas.get("passes_completed")),
        passes_attempted       = _int(pas.get("passes")),
        pass_completion_pct    = _float(pas.get("passes_pct")),
        passes_total_dist      = _float(pas.get("passes_total_distance")),
        passes_prog_dist       = _float(pas.get("passes_progressive_distance")),
        passes_short_pct       = _float(pas.get("passes_short_pct")),
        passes_medium_pct      = _float(pas.get("passes_medium_pct")),
        passes_long_completed  = _int(pas.get("passes_long_completed")),
        passes_long_attempted  = _int(pas.get("passes_long")),
        passes_long_pct        = _float(pas.get("passes_long_pct")),
        key_passes             = _int(pas.get("assisted_shots")),
        passes_final_third     = _int(pas.get("passes_into_final_third")),
        passes_penalty_area    = _int(pas.get("passes_into_penalty_area")),
        crosses_penalty_area   = _int(pas.get("crosses_into_penalty_area")),
        progressive_passes     = _int(pas.get("progressive_passes")),
        xa_pass                = _float(pas.get("xa")),

        # GCA
        sca           = _int(gca.get("sca")),
        sca_per90     = _float(gca.get("sca_per90")),
        sca_pass_live = _int(gca.get("sca_passes_live")),
        sca_pass_dead = _int(gca.get("sca_passes_dead")),
        sca_take_on   = _int(gca.get("sca_take_ons")),
        sca_shot      = _int(gca.get("sca_shots")),
        gca           = _int(gca.get("gca")),
        gca_per90     = _float(gca.get("gca_per90")),
        gca_pass_live = _int(gca.get("gca_passes_live")),
        gca_take_on   = _int(gca.get("gca_take_ons")),

        # Defense
        tackles             = _int(defs.get("tackles")),
        tackles_won         = _int(defs.get("tackles_won")),
        tackles_def_3rd     = _int(defs.get("tackles_def_3rd")),
        tackles_mid_3rd     = _int(defs.get("tackles_mid_3rd")),
        tackles_att_3rd     = _int(defs.get("tackles_att_3rd")),
        challenge_tackles   = _int(defs.get("challenge_tackles")),
        challenges          = _int(defs.get("challenges")),
        challenge_tackles_pct = _float(defs.get("challenge_tackles_pct")),
        blocks              = _int(defs.get("blocks")),
        blocked_shots       = _int(defs.get("blocked_shots")),
        blocked_passes      = _int(defs.get("blocked_passes")),
        interceptions       = _int(defs.get("interceptions")),
        tkl_int             = _int(defs.get("tackles_interceptions")),
        clearances          = _int(defs.get("clearances")),
        errors              = _int(defs.get("errors")),

        # Possession
        touches             = _int(poss.get("touches")),
        touches_def_pen     = _int(poss.get("touches_def_pen_area")),
        touches_def_3rd     = _int(poss.get("touches_def_3rd")),
        touches_mid_3rd     = _int(poss.get("touches_mid_3rd")),
        touches_att_3rd     = _int(poss.get("touches_att_3rd")),
        touches_att_pen     = _int(poss.get("touches_att_pen_area")),
        take_ons_att        = _int(poss.get("take_ons")),
        take_ons_succ       = _int(poss.get("take_ons_won")),
        take_ons_succ_pct   = _float(poss.get("take_ons_won_pct")),
        take_ons_tackled    = _int(poss.get("take_ons_tackled")),
        carries             = _int(poss.get("carries")),
        carries_prog_dist   = _float(poss.get("carries_progressive_distance")),
        progressive_carries = _int(poss.get("progressive_carries")),
        carries_final_third = _int(poss.get("carries_into_final_third")),
        carries_penalty_area = _int(poss.get("carries_into_penalty_area")),
        miscontrols         = _int(poss.get("miscontrols")),
        dispossessed        = _int(poss.get("dispossessed")),
        progressive_passes_received = _int(poss.get("progressive_passes_received")),

        # Misc  (misc usa "tackles_won" → già in defense; "interceptions" → già in defense)
        fouls_committed = _int(misc.get("fouls")),
        fouls_drawn     = _int(misc.get("fouled")),
        offsides        = _int(misc.get("offsides")),
        crosses         = _int(misc.get("crosses")),
        pens_won        = _int(misc.get("pens_won")),
        pens_conceded   = _int(misc.get("pens_conceded")),
        own_goals       = _int(misc.get("own_goals")),
        ball_recoveries = _int(misc.get("ball_recoveries")),
        aerials_won     = _int(misc.get("aerials_won")),
        aerials_lost    = _int(misc.get("aerials_lost")),
        aerials_won_pct = _float(misc.get("aerials_won_pct")),
    )


# ═════════════════════════════════════════════════════════════════
# MAPPER: match_logs list → [PlayerFbrefMatchLog]
# ═════════════════════════════════════════════════════════════════

def _map_match_logs(
    player_id: int,
    season: str,
    match_logs: list[dict],
) -> list[PlayerFbrefMatchLog]:

    records = []
    for m in match_logs:
        records.append(PlayerFbrefMatchLog(
            player_id    = player_id,
            season       = season,
            date         = m.get("date"),
            dayofweek    = m.get("dayofweek"),
            comp         = m.get("comp"),
            round        = m.get("round"),
            venue        = m.get("venue"),
            result       = m.get("result"),
            team         = _clean_team(m.get("team", "")),
            opponent     = _clean_opponent(m.get("opponent", "")),
            game_started = m.get("game_started"),
            position     = m.get("position"),
            minutes      = _int(m.get("minutes")),
            goals        = _int(m.get("goals")),
            assists      = _int(m.get("assists")),
            pens_made    = _int(m.get("pens_made")),
            pens_att     = _int(m.get("pens_att")),
            shots        = _int(m.get("shots")),
            shots_on_target = _int(m.get("shots_on_target")),
            yellow_card  = _int(m.get("cards_yellow")),
            red_card     = _int(m.get("cards_red")),
            fouls_committed = _int(m.get("fouls")),
            fouls_drawn  = _int(m.get("fouled")),
            offsides     = _int(m.get("offsides")),
            crosses      = _int(m.get("crosses")),
            tackles_won  = _int(m.get("tackles_won")),
            interceptions = _int(m.get("interceptions")),
            own_goals    = _int(m.get("own_goals")),
            pens_won     = m.get("pens_won") or None,
            pens_conceded = m.get("pens_conceded") or None,
        ))
    return records


# ═════════════════════════════════════════════════════════════════
# IMPORT SINGOLO FILE
# ═════════════════════════════════════════════════════════════════

def import_file(db: Session, json_path: Path) -> bool:
    """
    Importa un singolo file JSON nel DB.
    Ritorna True se importato con successo, False altrimenti.
    """
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log.error(f"❌ Impossibile leggere {json_path.name}: {e}")
        return False

    player_name = data.get("name", "")
    tables      = data.get("tables", {})
    match_logs  = data.get("match_logs", [])

    season = _extract_season(tables)
    league = _extract_league(tables)

    # Trova il giocatore nel DB
    # fbref_id potrebbe essere nel nome file: "federico_gatti_complete.json"
    # non lo conosciamo qui, usiamo solo il nome.
    player = _resolve_player(db, player_name, fbref_id=None)
    if not player:
        log.warning(
            f"⚠️  {player_name}: non trovato in scouting_players. "
            f"Crea prima l'anagrafica o imposta fbref_id."
        )
        return False

    # ── PlayerFbrefStats ─────────────────────────────────────────
    # 1. Riga principale dalle "tables" (Serie A o lega principale)
    existing_stats = db.query(PlayerFbrefStats).filter_by(
        player_id=player.id, season=season, league=league
    ).first()

    stats_obj = _map_fbref_stats(player.id, season, league, tables, player.fbref_id)

    if existing_stats:
        for col in PlayerFbrefStats.__table__.columns:
            if col.name in ("id", "player_id", "season", "league", "fetched_at"):
                continue
            setattr(existing_stats, col.name, getattr(stats_obj, col.name))
        existing_stats.updated_at = datetime.now(timezone.utc)
        log.info(f"🔄 {player_name} — stats aggiornate ({season} / {league})")
    else:
        db.add(stats_obj)
        log.info(f"➕ {player_name} — stats inserite ({season} / {league})")

    # 2. Righe aggregate dai match_logs per le altre competizioni
    #    (Champions League, Coppa Italia, ecc. che non sono nelle "tables")
    all_agg = _aggregate_stats_from_logs(player.id, season, match_logs, player.fbref_id)
    for league_name, agg_obj in all_agg:
        # Salta la lega principale — già gestita sopra con dati più completi
        if league_name.lower() == league.lower():
            continue
        existing_agg = db.query(PlayerFbrefStats).filter_by(
            player_id=player.id, season=season, league=league_name
        ).first()
        if existing_agg:
            for col in PlayerFbrefStats.__table__.columns:
                if col.name in ("id", "player_id", "season", "league", "fetched_at"):
                    continue
                new_val = getattr(agg_obj, col.name)
                if new_val is not None:  # non sovrascrivere con None
                    setattr(existing_agg, col.name, new_val)
            existing_agg.updated_at = datetime.now(timezone.utc)
            log.info(f"🔄 {player_name} — stats aggiornate da match_log ({season} / {league_name})")
        else:
            db.add(agg_obj)
            log.info(f"➕ {player_name} — stats inserite da match_log ({season} / {league_name})")

    # ── PlayerFbrefMatchLog ───────────────────────────────────────
    inserted_logs = 0
    skipped_logs  = 0
    for log_obj in _map_match_logs(player.id, season, match_logs):
        exists = db.query(PlayerFbrefMatchLog).filter_by(
            player_id=player.id,
            date=log_obj.date,
            comp=log_obj.comp,
        ).first()
        if not exists:
            db.add(log_obj)
            inserted_logs += 1
        else:
            skipped_logs += 1

    log.info(
        f"   match logs: {inserted_logs} inseriti, {skipped_logs} già presenti"
    )

    # Aggiungi questo log temporaneo in import_json.py dopo aver caricato i match_log
    for m in match_logs:
        if str(m.get('cards_yellow', '0')) not in ('0', '', 'CrdY'):
            print(f"YC: {m['date']} vs {m.get('opponent')} | comp={m.get('comp')} | venue={m.get('venue')}")

    # ── last_updated_fbref su ScoutingPlayer ─────────────────────
    player.last_updated_fbref = datetime.now(timezone.utc)

    db.flush()  # rende disponibili gli ID prima del commit

    # ── PlayerScoutingIndex ───────────────────────────────────────
    compute_scouting_index(db, player)
    log.info(f"   scouting index ricalcolato ✓")

    db.commit()
    return True


# ═════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════

def run_import(filename: str | None = None) -> None:
    """
    Importa tutti i JSON da DATA_DIR oppure solo quello specificato.

    Args:
        filename: nome file opzionale, es. "spinazzola_complete.json".
                  Se None, elabora tutti i *_complete.json nella directory.
    """
    if not DATA_DIR.exists():
        log.error(f"❌ Directory non trovata: {DATA_DIR}")
        return

    if filename:
        files = [DATA_DIR / filename]
    else:
        files = sorted(DATA_DIR.glob("*_complete.json"))

    if not files:
        log.warning(f"⚠️  Nessun file *_complete.json trovato in {DATA_DIR}")
        return

    log.info(f"🚀 Avvio importazione — {len(files)} file trovati")

    db = SessionLocal()
    ok, ko = 0, 0
    try:
        for path in files:
            log.info(f"📂 Elaborazione: {path.name}")
            success = import_file(db, path)
            if success:
                ok += 1
            else:
                ko += 1
    finally:
        db.close()

    log.info(f"🏁 Importazione completata — {ok} ok, {ko} errori")


if __name__ == "__main__":
    run_import()