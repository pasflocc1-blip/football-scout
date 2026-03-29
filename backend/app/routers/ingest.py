"""
routers/ingest.py — versione con logs[], cancel via threading.Event, stop_event
"""
import asyncio, os, sys, threading
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from app.services.sources.kaggle_source import import_from_kaggle_csv
from app.services.sources.api_football_source import fetch_from_api_football
from app.services.sources.statsbomb_source import fetch_from_statsbomb, list_competitions as sb_list
from app.services.sources.fbref_source import scrape_standard_stats, FBREF_LEAGUES
from app.services.sources.football_data_source import sync_player_clubs, fetch_competitions as fd_list, COMPETITION_CODES
# apro db solo per check
from app.database import SessionLocal
from app.models.models import ScoutingPlayer
from app.services.sources.understat_source import (
    fetch_from_understat,
    list_understat_leagues
)
router = APIRouter(prefix="/ingest", tags=["ingest"])

_ALL_SOURCES = ["kaggle","api_football","statsbomb","fbref","football_data","understat","all"]
_job_status: dict[str,dict] = {}
_cancel_events: dict[str,threading.Event] = {s: threading.Event() for s in _ALL_SOURCES}

class _LogCapture:
    def __init__(self,source):
        self._s=source; self._real=None; self._buf=""; self._lock=threading.Lock()
    def write(self,text):
        with self._lock:
            self._buf+=text
            while "\n" in self._buf:
                line,self._buf=self._buf.split("\n",1)
                line=line.rstrip()
                if line:
                    logs=_job_status.get(self._s,{}).get("logs")
                    if logs is not None: logs.append(line)
            self._real.write(text)
    def flush(self):
        with self._lock:
            r=self._buf.strip()
            if r:
                logs=_job_status.get(self._s,{}).get("logs")
                if logs is not None: logs.append(r)
                self._buf=""
        self._real.flush()
    def __enter__(self): self._real=sys.stdout; sys.stdout=self; return self
    def __exit__(self,*_): self.flush(); sys.stdout=self._real

def _set_running(s):
    _cancel_events[s].clear()
    _job_status[s]={"status":"running","started_at":datetime.utcnow().isoformat(),"finished_at":None,"result":None,"error":None,"progress":None,"progress_total":None,"logs":[]}

"""
PATCH ingest.py — auto-trigger ricalcolo score
-----------------------------------------------
Sostituisci le funzioni _set_done e _set_done nel file ingest.py
esistente con questa versione aggiornata.

CAMBIAMENTO: quando un job termina con successo (_set_done),
viene automaticamente avviato il ricalcolo Fase 2+3+4 in un
thread separato — senza bloccare il job corrente.

NON modificare il resto di ingest.py.
"""
def _set_done(s, result):
    """
    Versione aggiornata di _set_done.
    Dopo aver marcato il job come 'done', avvia il ricalcolo score
    in background (Fase 2+3+4) se il job è una sorgente dati.
    """
    from datetime import datetime
    import threading

    if s in _job_status:
        _job_status[s].update({
            "status":      "done",
            "finished_at": datetime.utcnow().isoformat(),
            "result":      result,
            "progress":    None,
            "progress_total": None,
        })
        # Aggiungi messaggio nel log
        logs = _job_status[s].get("logs")
        if logs is not None:
            logs.append("✅ Import completato. Avvio ricalcolo score (Fase 2+3+4)…")

    # Avvia ricalcolo in un thread separato
    # (non blocca il job corrente, non usa BackgroundTasks per semplicità)
    def _recalc():
        from app.database import SessionLocal
        from app.services.scoring import recalculate_all
        from app.services.percentiles import recalculate_percentiles

        _db = SessionLocal()
        try:
            n = recalculate_all(_db)
            pct = recalculate_percentiles(_db)
            print(
                f"  → [auto-recalc after {s}] "
                f"{n} score, {pct.get('players_updated', 0)} percentili"
            )
            # Aggiorna log con il risultato
            if s in _job_status:
                logs = _job_status[s].get("logs")
                if logs is not None:
                    logs.append(
                        f"✅ Score ricalcolati: {n} giocatori, "
                        f"{pct.get('players_updated', 0)} percentili aggiornati"
                    )
        except Exception as e:
            print(f"  → [auto-recalc] errore: {e}")
        finally:
            print("✅ Score ricalcolati: completato")
            _db.close()

    threading.Thread(target=_recalc, daemon=True).start()

def _set_error(s,error):
    if s in _job_status: _job_status[s].update({"status":"error","finished_at":datetime.utcnow().isoformat(),"error":error,"progress":None,"progress_total":None})

def _set_cancelled(s):
    if s in _job_status:
        _job_status[s].update({"status":"cancelled","finished_at":datetime.utcnow().isoformat(),"progress":None,"progress_total":None})
        logs=_job_status[s].get("logs")
        if logs is not None: logs.append("Operazione interrotta dall'utente.")

def _is_cancelled(s): return _cancel_events[s].is_set()

def _run_async(coro):
    loop=asyncio.new_event_loop()
    try: return loop.run_until_complete(coro)
    finally: loop.close()


# Models
class KaggleRequest(BaseModel):
    file_path: str = "/app/data/players_22.csv"
    limit: int = 2000

class ApiFootballRequest(BaseModel):
    league_id: int = 135
    season: int = 2024
    team_id: Optional[int] = None

class StatsBombRequest(BaseModel):
    competition_id: int = 12
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
    understat_league: str = "serie_a"
    understat_season: int = 2024
    football_data_comp: str = "SA"

class UnderstatRequest(BaseModel):
    league_key: str = "serie_a"
    season: int = 2024

# Cancel
@router.post("/{source}/cancel")
def cancel_job(source: str):
    key = source.replace("-","_")
    if key not in _cancel_events:
        raise HTTPException(404, f"Source '{source}' non trovata")
    job = _job_status.get(key, {})
    if job.get("status") != "running":
        return {"detail":"Nessun job in esecuzione","status":job.get("status","idle")}
    _cancel_events[key].set()
    logs=_job_status.get(key,{}).get("logs")
    if logs is not None: logs.append("Richiesta interruzione inviata...")
    return {"detail":"Interruzione richiesta","status":"cancelling"}

@router.get("/env-status")
def env_status():
    keys=["API_FOOTBALL_KEY","FOOTBALL_DATA_KEY","DATABASE_URL","POSTGRES_USER","POSTGRES_PASSWORD"]
    return {k: bool(os.getenv(k)) for k in keys}

@router.get("/status")
def get_status():
    return _job_status


# Kaggle
@router.post("/kaggle")
def run_kaggle(req: KaggleRequest, background_tasks: BackgroundTasks):
    if _job_status.get("kaggle",{}).get("status")=="running":
        raise HTTPException(409,"Job Kaggle gia in esecuzione")
    _set_running("kaggle")
    def _task():
        from app.database import SessionLocal
        db=SessionLocal()
        try:
            with _LogCapture("kaggle"):
                def _pg(imported):
                    if _is_cancelled("kaggle"): raise InterruptedError
                    _job_status["kaggle"]["progress"]=imported
                n=import_from_kaggle_csv(db,req.file_path,limit=req.limit,progress_cb=_pg)
            if _is_cancelled("kaggle"): _set_cancelled("kaggle")
            else: _set_done("kaggle",{"imported":n})
        except InterruptedError: _set_cancelled("kaggle")
        except Exception as e:
            if _is_cancelled("kaggle"): _set_cancelled("kaggle")
            else: _set_error("kaggle",str(e))
        finally: db.close()
    background_tasks.add_task(_task)
    return {"message":"Job Kaggle avviato"}

# API-Football
@router.post("/api-football")
def run_api_football(req: ApiFootballRequest, background_tasks: BackgroundTasks):
    if _job_status.get("api_football",{}).get("status")=="running":
        raise HTTPException(409,"Job API-Football gia in esecuzione")
    _set_running("api_football")
    def _task():
        from app.database import SessionLocal
        db=SessionLocal()
        try:
            with _LogCapture("api_football"):
                n=_run_async(fetch_from_api_football(db=db,league_id=req.league_id,season=req.season,team_id=req.team_id,stop_event=_cancel_events["api_football"]))
            if _is_cancelled("api_football"): _set_cancelled("api_football")
            else: _set_done("api_football",{"imported":n})
        except Exception as e:
            if _is_cancelled("api_football"): _set_cancelled("api_football")
            else: _set_error("api_football",str(e))
        finally: db.close()
    background_tasks.add_task(_task)
    return {"message":"Job API-Football avviato"}

# StatsBomb
@router.post("/statsbomb")
def run_statsbomb(req: StatsBombRequest, background_tasks: BackgroundTasks):
    if _job_status.get("statsbomb",{}).get("status")=="running":
        raise HTTPException(409,"Job StatsBomb gia in esecuzione")
    _set_running("statsbomb")
    def _task():
        from app.database import SessionLocal
        db=SessionLocal()
        try:
            with _LogCapture("statsbomb"):
                def _pg(done,total):
                    _job_status["statsbomb"]["progress"]=done
                    _job_status["statsbomb"]["progress_total"]=total
                r=_run_async(fetch_from_statsbomb(db,req.competition_id,req.season_id,req.max_matches,progress_cb=_pg,stop_event=_cancel_events["statsbomb"]))
            if _is_cancelled("statsbomb"): _set_cancelled("statsbomb")
            else: _set_done("statsbomb",r)
        except Exception as e:
            if _is_cancelled("statsbomb"): _set_cancelled("statsbomb")
            else: _set_error("statsbomb",str(e))
        finally: db.close()
    background_tasks.add_task(_task)
    return {"message":"Job StatsBomb avviato"}

# FBref
@router.post("/fbref")
def run_fbref(req: FBrefRequest, background_tasks: BackgroundTasks):
    if req.league_key not in FBREF_LEAGUES:
        raise HTTPException(400,f"league_key non valido: {list(FBREF_LEAGUES.keys())}")
    if _job_status.get("fbref",{}).get("status")=="running":
        raise HTTPException(409,"Job FBref gia in esecuzione")
    _set_running("fbref")
    def _task():
        from app.database import SessionLocal
        db=SessionLocal()
        try:
            with _LogCapture("fbref"):
                r=scrape_standard_stats(db,req.league_key,req.season,stop_event=_cancel_events["fbref"])
            if _is_cancelled("fbref"): _set_cancelled("fbref")
            else: _set_done("fbref",r)
        except Exception as e:
            if _is_cancelled("fbref"): _set_cancelled("fbref")
            else: _set_error("fbref",str(e))
        finally: db.close()
    background_tasks.add_task(_task)
    return {"message":"Job FBref avviato"}

# Football-Data
@router.post("/football-data")
def run_football_data(req: FootballDataRequest, background_tasks: BackgroundTasks):
    if _job_status.get("football_data",{}).get("status")=="running":
        raise HTTPException(409,"Job Football-Data gia in esecuzione")
    _set_running("football_data")
    def _task():
        from app.database import SessionLocal
        db=SessionLocal()
        try:
            with _LogCapture("football_data"):
                def _pg(done,total):
                    _job_status["football_data"]["progress"]=done
                    _job_status["football_data"]["progress_total"]=total
                r=_run_async(sync_player_clubs(db,req.competition_code,req.season,progress_cb=_pg,stop_event=_cancel_events["football_data"]))
            if _is_cancelled("football_data"): _set_cancelled("football_data")
            else: _set_done("football_data",r)
        except Exception as e:
            if _is_cancelled("football_data"): _set_cancelled("football_data")
            else: _set_error("football_data",str(e))
        finally: db.close()
    background_tasks.add_task(_task)
    return {"message":"Job Football-Data avviato"}


# All sources
@router.post("/all")
def run_all_sources(req: RunAllRequest, background_tasks: BackgroundTasks):
    if _job_status.get("all", {}).get("status") == "running":
        raise HTTPException(409, "Job 'all' gia in esecuzione")

    _set_running("all")

    # inizializza tutte le sorgenti
    for k in ("kaggle","api_football","statsbomb","fbref","football_data","understat"):
        _job_status[k] = {
            "status": "pending",
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
            "progress": None,
            "progress_total": None,
            "logs": []
        }

    def _task():
        results = {}

        def _cancelled(k):
            return _cancel_events["all"].is_set() or _cancel_events[k].is_set()

        # ─────────────────────────────────────────
        # 1. KAGGLE
        # ─────────────────────────────────────────
        kaggle_file = req.kaggle_file or "/app/data/players_22.csv"

        if os.path.exists(kaggle_file) and not _cancelled("kaggle"):
            _set_running("kaggle")
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                with _LogCapture("kaggle"):
                    n = import_from_kaggle_csv(db, kaggle_file, limit=req.kaggle_limit)
                _set_done("kaggle", {"imported": n})
                results["kaggle"] = {"status": "ok", "imported": n}
            except Exception as e:
                _set_error("kaggle", str(e))
                results["kaggle"] = {"status": "error", "error": str(e)}
            finally:
                db.close()
        else:
            _job_status["kaggle"]["status"] = "skipped"
            results["kaggle"] = {"status": "skipped"}

        # ─────────────────────────────────────────
        # 2. API-FOOTBALL
        # ─────────────────────────────────────────
        if os.getenv("API_FOOTBALL_KEY") and not _cancelled("api_football"):
            _set_running("api_football")
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                with _LogCapture("api_football"):
                    n = _run_async(fetch_from_api_football(
                        db=db,
                        league_id=req.api_league,
                        season=req.season,
                        stop_event=_cancel_events["all"]
                    ))
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

        # ─────────────────────────────────────────
        # 3. STATSBOMB
        # ─────────────────────────────────────────
        if not _cancelled("statsbomb"):
            _set_running("statsbomb")
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                with _LogCapture("statsbomb"):
                    def _sbp(d, t):
                        _job_status["statsbomb"]["progress"] = d
                        _job_status["statsbomb"]["progress_total"] = t

                    r = _run_async(fetch_from_statsbomb(
                        db,
                        req.statsbomb_comp,
                        req.statsbomb_season_id,
                        req.statsbomb_max_matches,
                        progress_cb=_sbp,
                        stop_event=_cancel_events["all"]
                    ))

                _set_done("statsbomb", r)
                results["statsbomb"] = {"status": "ok", **r}

            except Exception as e:
                _set_error("statsbomb", str(e))
                results["statsbomb"] = {"status": "error", "error": str(e)}
            finally:
                db.close()

        # ─────────────────────────────────────────
        # 4. FBREF
        # ─────────────────────────────────────────
        if not _cancelled("fbref"):
            _set_running("fbref")
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                with _LogCapture("fbref"):
                    r = scrape_standard_stats(
                        db,
                        req.fbref_league,
                        req.fbref_season,
                        stop_event=_cancel_events["all"]
                    )

                _set_done("fbref", r)
                results["fbref"] = {"status": "ok", **r}

            except Exception as e:
                _set_error("fbref", str(e))
                results["fbref"] = {"status": "error", "error": str(e)}
            finally:
                db.close()

        # ─────────────────────────────────────────
        # 5. FOOTBALL-DATA
        # ─────────────────────────────────────────
        if os.getenv("FOOTBALL_DATA_KEY") and not _cancelled("football_data"):
            _set_running("football_data")
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                with _LogCapture("football_data"):
                    def _fdp(d, t):
                        _job_status["football_data"]["progress"] = d
                        _job_status["football_data"]["progress_total"] = t

                    r = _run_async(sync_player_clubs(
                        db,
                        req.football_data_comp,
                        req.season,
                        progress_cb=_fdp,
                        stop_event=_cancel_events["all"]
                    ))

                _set_done("football_data", r)
                results["football_data"] = {"status": "ok", **r}

            except Exception as e:
                _set_error("football_data", str(e))
                results["football_data"] = {"status": "error", "error": str(e)}
            finally:
                db.close()
        else:
            _job_status["football_data"]["status"] = "skipped"
            results["football_data"] = {"status": "skipped", "reason": "FOOTBALL_DATA_KEY mancante"}

        # ─────────────────────────────────────────
        # 6. UNDERSTAT (SMART)
        # ─────────────────────────────────────────
        from app.database import SessionLocal
        from app.models.models import ScoutingPlayer

        db_check = SessionLocal()
        try:
            players_exist = db_check.query(ScoutingPlayer).count() > 0
        finally:
            db_check.close()

        if players_exist and not _cancelled("understat"):
            _set_running("understat")

            db = SessionLocal()
            try:
                with _LogCapture("understat"):
                    def _usp(d, t):
                        _job_status["understat"]["progress"] = d
                        _job_status["understat"]["progress_total"] = t

                    r = _run_async(fetch_from_understat(
                        db=db,
                        league_key=req.understat_league,
                        season=req.understat_season,
                        progress_cb=_usp,
                        stop_event=_cancel_events["all"]
                    ))

                _set_done("understat", r)
                results["understat"] = {"status": "ok", **r}

            except Exception as e:
                _set_error("understat", str(e))
                results["understat"] = {"status": "error", "error": str(e)}
            finally:
                db.close()

        else:
            _job_status["understat"]["status"] = "skipped"
            results["understat"] = {
                "status": "skipped",
                "reason": "DB vuoto o job cancellato"
            }

        # ─────────────────────────────────────────
        # FINE
        # ─────────────────────────────────────────
        if _cancel_events["all"].is_set():
            _set_cancelled("all")
        else:
            _set_done("all", {"sources": results})

    background_tasks.add_task(_task)
    return {"message": "Job 'all' avviato"}

@router.get("/statsbomb/competitions")
async def get_statsbomb_competitions():
    try: return await sb_list()
    except Exception as e: raise HTTPException(500,f"Errore: {e}")

@router.get("/football-data/competitions")
async def get_football_data_competitions():
    try: return await fd_list()
    except Exception as e: raise HTTPException(500,f"Errore: {e}")

@router.get("/fbref/leagues")
def get_fbref_leagues():
    return [{"key":k,"fbref_id":v["id"],"slug":v["slug"]} for k,v in FBREF_LEAGUES.items()]

@router.get("/understat/leagues")
def get_understat_leagues():
    return list_understat_leagues()

# Understat
@router.post("/understat")
def run_understat(req: UnderstatRequest, background_tasks: BackgroundTasks):
    if _job_status.get("understat", {}).get("status") == "running":
        raise HTTPException(409, "Job Understat gia in esecuzione")

    _set_running("understat")

    def _task():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            with _LogCapture("understat"):
                def _pg(done, total):
                    _job_status["understat"]["progress"] = done
                    _job_status["understat"]["progress_total"] = total

                r = _run_async(
                    fetch_from_understat(
                        db=db,
                        league_key=req.league_key,
                        season=req.season,
                        progress_cb=_pg,
                        stop_event=_cancel_events["understat"]
                    )
                )

            if _is_cancelled("understat"):
                _set_cancelled("understat")
            else:
                _set_done("understat", r)

        except Exception as e:
            if _is_cancelled("understat"):
                _set_cancelled("understat")
            else:
                _set_error("understat", str(e))
        finally:
            db.close()

    background_tasks.add_task(_task)
    return {"message": "Job Understat avviato"}