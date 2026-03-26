"""
routers/ingest.py
-----------------
Endpoint REST per triggerare i job di ingestion dal frontend.
Usa BackgroundTasks di FastAPI per eseguire i job in modo asincrono.

Endpoints:
  POST /ingest/kaggle          → importa CSV Kaggle
  POST /ingest/api-football    → importa da API-Football
  POST /ingest/statsbomb       → arricchisce con StatsBomb open data
  POST /ingest/fbref           → arricchisce con FBref scraping
  POST /ingest/football-data   → sincronizza club da Football-Data.org
  POST /ingest/all             → esegue tutte le sorgenti
  GET  /ingest/status          → stato degli ultimi job
  GET  /ingest/statsbomb/competitions → lista competizioni StatsBomb disponibili
  GET  /ingest/football-data/competitions → lista competizioni Football-Data.org
"""

import asyncio
import threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.sources.kaggle_source import import_from_kaggle_csv
from app.services.sources.api_football_source import fetch_from_api_football
from app.services.sources.statsbomb_source import fetch_from_statsbomb, list_competitions as sb_list
from app.services.sources.fbref_source import scrape_standard_stats, FBREF_LEAGUES
from app.services.sources.football_data_source import (
    sync_player_clubs,
    fetch_competitions as fd_list,
    COMPETITION_CODES,
)
from app.services.ingest import run_all  # mantenuto per compatibilità CLI

router = APIRouter(prefix="/ingest", tags=["ingest"])

# ── In-memory job status store ────────────────────────────────────
# { source_key: { status, started_at, finished_at, result, error } }
_job_status: dict[str, dict] = {}


def _set_running(source: str):
    _job_status[source] = {
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
        "result": None,
        "error": None,
        "progress": None,        # contatore avanzamento (es. giocatori processati)
        "progress_total": None,  # totale se noto (es. partite StatsBomb)
    }


def _set_done(source: str, result):
    if source in _job_status:
        _job_status[source].update({
            "status": "done",
            "finished_at": datetime.utcnow().isoformat(),
            "result": result,
            "progress": None,
            "progress_total": None,
        })


def _set_error(source: str, error: str):
    if source in _job_status:
        _job_status[source].update({
            "status": "error",
            "finished_at": datetime.utcnow().isoformat(),
            "error": error,
            "progress": None,
            "progress_total": None,
        })


# ── Request models ────────────────────────────────────────────────

class KaggleRequest(BaseModel):
    file_path: str = "/app/data/players_22.csv"
    limit: int = 2000


class ApiFootballRequest(BaseModel):
    league_id: int = 135   # 135=Serie A, 39=PL, 140=La Liga
    season: int = 2024


class StatsBombRequest(BaseModel):
    competition_id: int = 12   # 12=Serie A
    season_id: int = 27
    max_matches: int = 50


class FBrefRequest(BaseModel):
    league_key: str = "serie_a"
    season: str = "2023-2024"


class FootballDataRequest(BaseModel):
    competition_code: str = "SA"
    season: int = 2024


class RunAllRequest(BaseModel):
    kaggle_file: Optional[str] = None
    kaggle_limit: int = 2000
    api_league: int = 135
    season: int = 2024
    statsbomb_comp: int = 12
    statsbomb_season_id: int = 27
    statsbomb_max_matches: int = 50
    fbref_league: str = "serie_a"
    fbref_season: str = "2023-2024"
    football_data_comp: str = "SA"


# ── Helper per eseguire coroutine in background thread ────────────

def _run_async_in_thread(coro):
    """Esegue una coroutine in un nuovo event loop in un thread separato."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/env-status", tags=["ingest"])
def env_status():
    """Ritorna quali variabili d'ambiente critiche sono configurate."""
    import os
    keys = ["API_FOOTBALL_KEY", "FOOTBALL_DATA_KEY", "DATABASE_URL",
            "POSTGRES_USER", "POSTGRES_PASSWORD"]
    return {k: bool(os.getenv(k)) for k in keys}

@router.get("/status")
def get_status():
    """Ritorna lo stato di tutti i job di ingestion."""
    return _job_status


@router.post("/kaggle")
def run_kaggle(req: KaggleRequest, background_tasks: BackgroundTasks):
    """Importa giocatori da CSV Kaggle FIFA."""
    if _job_status.get("kaggle", {}).get("status") == "running":
        raise HTTPException(409, "Job Kaggle già in esecuzione")

    # ✅ FIX: _set_running PRIMA di add_task — il client vede subito "running"
    _set_running("kaggle")

    def _task():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            # ✅ FIX: progress_cb aggiorna il contatore in tempo reale
            def _progress(imported: int):
                if "kaggle" in _job_status:
                    _job_status["kaggle"]["progress"] = imported

            n = import_from_kaggle_csv(db, req.file_path, limit=req.limit, progress_cb=_progress)
            _set_done("kaggle", {"imported": n})
        except Exception as e:
            _set_error("kaggle", str(e))
        finally:
            db.close()

    background_tasks.add_task(_task)
    return {"message": "Job Kaggle avviato", "file": req.file_path}


@router.post("/api-football")
def run_api_football(req: ApiFootballRequest, background_tasks: BackgroundTasks):
    """Importa giocatori da API-Football."""
    if _job_status.get("api_football", {}).get("status") == "running":
        raise HTTPException(409, "Job API-Football già in esecuzione")

    # ✅ FIX
    _set_running("api_football")

    def _task():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            def _progress(imported: int):
                if "api_football" in _job_status:
                    _job_status["api_football"]["progress"] = imported

            n = _run_async_in_thread(
                fetch_from_api_football(db, req.league_id, req.season, progress_cb=_progress)
            )
            _set_done("api_football", {"imported": n})
        except Exception as e:
            _set_error("api_football", str(e))
        finally:
            db.close()

    background_tasks.add_task(_task)
    return {"message": "Job API-Football avviato", "league": req.league_id, "season": req.season}


@router.post("/statsbomb")
def run_statsbomb(req: StatsBombRequest, background_tasks: BackgroundTasks):
    """Arricchisce giocatori con StatsBomb open data (xG/xA)."""
    if _job_status.get("statsbomb", {}).get("status") == "running":
        raise HTTPException(409, "Job StatsBomb già in esecuzione")

    # ✅ FIX
    _set_running("statsbomb")

    def _task():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            def _progress(done: int, total: int):
                if "statsbomb" in _job_status:
                    _job_status["statsbomb"]["progress"] = done
                    _job_status["statsbomb"]["progress_total"] = total

            result = _run_async_in_thread(
                fetch_from_statsbomb(
                    db, req.competition_id, req.season_id, req.max_matches,
                    progress_cb=_progress,
                )
            )
            _set_done("statsbomb", result)
        except Exception as e:
            _set_error("statsbomb", str(e))
        finally:
            db.close()

    background_tasks.add_task(_task)
    return {
        "message": "Job StatsBomb avviato",
        "competition_id": req.competition_id,
        "season_id": req.season_id,
    }


@router.post("/fbref")
def run_fbref(req: FBrefRequest, background_tasks: BackgroundTasks):
    """Arricchisce giocatori con FBref scraping (xG/xA)."""
    if req.league_key not in FBREF_LEAGUES:
        raise HTTPException(400, f"league_key non valido. Disponibili: {list(FBREF_LEAGUES.keys())}")
    if _job_status.get("fbref", {}).get("status") == "running":
        raise HTTPException(409, "Job FBref già in esecuzione")

    # ✅ FIX
    _set_running("fbref")

    def _task():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            result = scrape_standard_stats(db, req.league_key, req.season)
            _set_done("fbref", result)
        except Exception as e:
            _set_error("fbref", str(e))
        finally:
            db.close()

    background_tasks.add_task(_task)
    return {"message": "Job FBref avviato", "league": req.league_key, "season": req.season}


@router.post("/football-data")
def run_football_data(req: FootballDataRequest, background_tasks: BackgroundTasks):
    """Sincronizza club dei giocatori da Football-Data.org."""
    if _job_status.get("football_data", {}).get("status") == "running":
        raise HTTPException(409, "Job Football-Data già in esecuzione")

    # ✅ FIX
    _set_running("football_data")

    def _task():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            def _progress(done: int, total: int):
                if "football_data" in _job_status:
                    _job_status["football_data"]["progress"] = done
                    _job_status["football_data"]["progress_total"] = total

            result = _run_async_in_thread(
                sync_player_clubs(db, req.competition_code, req.season, progress_cb=_progress)
            )
            _set_done("football_data", result)
        except Exception as e:
            _set_error("football_data", str(e))
        finally:
            db.close()

    background_tasks.add_task(_task)
    return {
        "message": "Job Football-Data avviato",
        "competition": req.competition_code,
        "season": req.season,
    }


@router.post("/all")
def run_all_sources(req: RunAllRequest, background_tasks: BackgroundTasks):
    """Esegue tutte le sorgenti in sequenza."""
    if _job_status.get("all", {}).get("status") == "running":
        raise HTTPException(409, "Job 'all' già in esecuzione")

    # ✅ FIX: stato visibile immediatamente al client
    _set_running("all")
    # Segna anche i singoli job come "pending" così le card si aggiornano
    for key in ("kaggle", "api_football", "statsbomb", "fbref", "football_data"):
        _job_status[key] = {
            "status": "pending",
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
            "progress": None,
            "progress_total": None,
        }

    def _task():
        results = {}

        # ── 1. Kaggle ──
        import os
        from app.database import SessionLocal
        kaggle_file = req.kaggle_file or "/app/data/players_22.csv"
        if os.path.exists(kaggle_file):
            _set_running("kaggle")
            db = SessionLocal()
            try:
                def _kprogress(n: int):
                    _job_status["kaggle"]["progress"] = n
                n = import_from_kaggle_csv(db, kaggle_file, limit=req.kaggle_limit, progress_cb=_kprogress)
                _set_done("kaggle", {"imported": n})
                results["kaggle"] = {"status": "ok", "imported": n}
            except Exception as e:
                _set_error("kaggle", str(e))
                results["kaggle"] = {"status": "error", "error": str(e)}
            finally:
                db.close()
        else:
            _job_status["kaggle"]["status"] = "skipped"
            results["kaggle"] = {"status": "skipped", "reason": f"file non trovato: {kaggle_file}"}

        # ── 2. API-Football ──
        if os.getenv("API_FOOTBALL_KEY"):
            _set_running("api_football")
            db = SessionLocal()
            try:
                def _aprogress(n: int):
                    _job_status["api_football"]["progress"] = n
                n = _run_async_in_thread(
                    fetch_from_api_football(db, req.api_league, req.season, progress_cb=_aprogress)
                )
                _set_done("api_football", {"imported": n})
                results["api_football"] = {"status": "ok", "imported": n}
            except Exception as e:
                _set_error("api_football", str(e))
                results["api_football"] = {"status": "error", "error": str(e)}
            finally:
                db.close()
        else:
            _job_status["api_football"]["status"] = "skipped"
            results["api_football"] = {"status": "skipped", "reason": "API_FOOTBALL_KEY mancante"}

        # ── 3. StatsBomb ──
        _set_running("statsbomb")
        db = SessionLocal()
        try:
            def _sbprogress(done: int, total: int):
                _job_status["statsbomb"]["progress"] = done
                _job_status["statsbomb"]["progress_total"] = total
            sb_result = _run_async_in_thread(
                fetch_from_statsbomb(
                    db, req.statsbomb_comp, req.statsbomb_season_id,
                    req.statsbomb_max_matches, progress_cb=_sbprogress,
                )
            )
            _set_done("statsbomb", sb_result)
            results["statsbomb"] = {"status": "ok", **sb_result}
        except Exception as e:
            _set_error("statsbomb", str(e))
            results["statsbomb"] = {"status": "error", "error": str(e)}
        finally:
            db.close()

        # ── 4. FBref ──
        _set_running("fbref")
        db = SessionLocal()
        try:
            fb_result = scrape_standard_stats(db, req.fbref_league, req.fbref_season)
            _set_done("fbref", fb_result)
            results["fbref"] = {"status": "ok", **fb_result}
        except Exception as e:
            _set_error("fbref", str(e))
            results["fbref"] = {"status": "error", "error": str(e)}
        finally:
            db.close()

        # ── 5. Football-Data.org ──
        if os.getenv("FOOTBALL_DATA_KEY"):
            _set_running("football_data")
            db = SessionLocal()
            try:
                def _fdprogress(done: int, total: int):
                    _job_status["football_data"]["progress"] = done
                    _job_status["football_data"]["progress_total"] = total
                fd_result = _run_async_in_thread(
                    sync_player_clubs(
                        db, req.football_data_comp, req.season, progress_cb=_fdprogress
                    )
                )
                _set_done("football_data", fd_result)
                results["football_data"] = {"status": "ok", **fd_result}
            except Exception as e:
                _set_error("football_data", str(e))
                results["football_data"] = {"status": "error", "error": str(e)}
            finally:
                db.close()
        else:
            _job_status["football_data"]["status"] = "skipped"
            results["football_data"] = {"status": "skipped", "reason": "FOOTBALL_DATA_KEY mancante"}

        # ── Completato ──
        _set_done("all", {"sources": results})

    background_tasks.add_task(_task)
    return {"message": "Job 'all' avviato — tutte le sorgenti in sequenza"}


# ── Utilità: lista competizioni ───────────────────────────────────

@router.get("/statsbomb/competitions")
async def get_statsbomb_competitions():
    """Lista competizioni/stagioni disponibili in StatsBomb Open Data."""
    try:
        return await sb_list()
    except Exception as e:
        raise HTTPException(500, f"Errore StatsBomb: {e}")


@router.get("/football-data/competitions")
async def get_football_data_competitions():
    """Lista competizioni Football-Data.org disponibili nel piano attivo."""
    try:
        return await fd_list()
    except Exception as e:
        raise HTTPException(500, f"Errore Football-Data: {e}")


@router.get("/fbref/leagues")
def get_fbref_leagues():
    """Lista campionati supportati da FBref."""
    return [
        {"key": k, "fbref_id": v["id"], "slug": v["slug"]}
        for k, v in FBREF_LEAGUES.items()
    ]