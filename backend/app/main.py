from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import team, players, scouting, admin, ingest_fbref_csv
from app.routers import global_scouting as global_scouting_router
from app.database import engine, Base
from app.routers import ingest as ingest_router
from app.routers import db_explorer as db_explorer_router
from app.routers import sofascore as sofascore_router
from app.routers import player_detail as player_detail_router  # ← NUOVO

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
app.include_router(team.router)
app.include_router(players.router)
app.include_router(scouting.router)
app.include_router(global_scouting_router.router)
app.include_router(admin.router)
app.include_router(ingest_router.router)
app.include_router(db_explorer_router.router)
app.include_router(ingest_fbref_csv.router)
app.include_router(sofascore_router.router)
app.include_router(player_detail_router.router)  # ← NUOVO: /players/{id}/detail

@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "message": "Football Scout API v2.0 attiva"}