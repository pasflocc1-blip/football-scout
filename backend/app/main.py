from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import fbref_models  # noqa — registra le tabelle con Base
from app.database import engine, Base

from app.routers import global_scouting as global_scouting_router
from app.routers import ingest as ingest_router
from app.routers import db_explorer as db_explorer_router
from app.routers import sofascore as sofascore_router
from app.routers import player_detail_final
from app.routers import team, players, scouting, admin, ingest_fbref_csv
from app.models import sofascore_models  # noqa — registra player_sofascore_stats
from app.routers import scoring_sofascore

# Crea tutte le tabelle all'avvio (in prod usa Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Football Scout API",
    description="API per la gestione e lo scouting della squadra",
    version="2.0.0",
    redirect_slashes=False,
)

# ── CORS ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "http://frontend:5173",
        "http://192.168.1.186:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router ──────────────────────────────────────────────────────
# ORDINE CRITICO: FastAPI usa la PRIMA rotta registrata che fa match.
# player_detail_final registra GET /players/{id} con struttura nuova
# (sources.fbref.stats, sources.sofascore.stats, heatmaps...).
# players.router registra anch'esso GET /players/{id} con struttura vecchia:
# se viene prima sovrascrive e sources.fbref.stats sarà sempre vuoto.

app.include_router(player_detail_final.router)  # ← PRIMO: vince su GET /players/{id}

app.include_router(scouting.router)
app.include_router(global_scouting_router.router)
app.include_router(admin.router)
app.include_router(ingest_router.router)
app.include_router(db_explorer_router.router)
app.include_router(ingest_fbref_csv.router)
app.include_router(sofascore_router.router)
app.include_router(team.router)
app.include_router(players.router)              # ← DOPO: le rotte /players/{id} vengono ignorate
app.include_router(scoring_sofascore.router)


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "message": "Football Scout API v2.0 attiva"}