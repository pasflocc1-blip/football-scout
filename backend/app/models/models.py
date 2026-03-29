"""
app/models/models.py — aggiornato per Fase 1 pipeline oggettivo

Cambiamenti rispetto alla versione precedente:
  - Rimossi pace/shooting/passing/dribbling/defending/physical
    (erano valori FIFA soggettivi — ora sostituiti da score oggettivi)
  - Aggiunge tutte le colonne raw di statistiche reali
  - Aggiunge colonne score oggettivi (Fase 3) e percentile (Fase 4)
  - Aggiunge timestamp per sorgente
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, Enum, Date
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class TraitType(str, enum.Enum):
    positive = "positive"
    negative = "negative"


class MyTeam(Base):
    __tablename__ = "my_team"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False)
    formation   = Column(String(20))
    league      = Column(String(100))
    season      = Column(String(20))
    coach       = Column(String(100))
    budget      = Column(Float)
    notes       = Column(Text)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    traits  = relationship("TeamTrait", back_populates="team", cascade="all, delete")
    players = relationship("MyPlayer",  back_populates="team", cascade="all, delete")


class TeamTrait(Base):
    __tablename__ = "team_traits"

    id          = Column(Integer, primary_key=True, index=True)
    team_id     = Column(Integer, ForeignKey("my_team.id", ondelete="CASCADE"), nullable=False)
    trait_type  = Column(Enum(TraitType), nullable=False)
    description = Column(Text, nullable=False)
    priority    = Column(Integer, default=1)

    team = relationship("MyTeam", back_populates="traits")


class MyPlayer(Base):
    __tablename__ = "my_players"

    id             = Column(Integer, primary_key=True, index=True)
    team_id        = Column(Integer, ForeignKey("my_team.id", ondelete="CASCADE"))
    name           = Column(String(100), nullable=False)
    position       = Column(String(20))
    age            = Column(Integer)
    preferred_foot = Column(String(10))
    rating         = Column(Float)

    team = relationship("MyTeam", back_populates="players")


class ScoutingPlayer(Base):
    __tablename__ = "scouting_players"

    id = Column(Integer, primary_key=True, index=True)

    # ── Identificatori provider ──────────────────────────────────
    api_football_id  = Column(Integer,     unique=True, index=True, nullable=True)
    transfermarkt_id = Column(String(50),  unique=True, index=True, nullable=True)
    fbref_id         = Column(String(50),  unique=True, index=True, nullable=True)
    understat_id     = Column(String(20),  unique=True, index=True, nullable=True)

    # ── Anagrafica ───────────────────────────────────────────────
    name           = Column(String(100), nullable=False)
    birth_date     = Column(Date, index=True, nullable=True)
    position       = Column(String(20))
    club           = Column(String(100))
    nationality    = Column(String(50))
    age            = Column(Integer)
    preferred_foot = Column(String(10))

    # ── Statistiche offensive — valori assoluti stagione ─────────
    goals_season            = Column(Integer)    # gol segnati
    assists_season          = Column(Integer)    # assist
    minutes_season          = Column(Integer)    # minuti giocati
    games_season            = Column(Integer)    # partite giocate
    shots_season            = Column(Integer)    # tiri totali
    shots_on_target_season  = Column(Integer)    # tiri in porta
    key_passes_season       = Column(Integer)    # passaggi chiave

    # ── xG / xA — valori per 90 min ──────────────────────────────
    xg_per90       = Column(Float)   # expected goals/90 (Understat/FBref)
    xa_per90       = Column(Float)   # expected assists/90
    npxg_per90     = Column(Float)   # non-penalty xG/90 (più affidabile per i centravanti)
    xgchain_per90  = Column(Float)   # xG di ogni azione con tocco del giocatore (StatsBomb)
    xgbuildup_per90= Column(Float)   # xG del build-up escluso il tocco finale (StatsBomb)

    # ── Progressione (FBref) ─────────────────────────────────────
    progressive_passes          = Column(Integer)  # passaggi che avanzano verso la porta
    progressive_carries         = Column(Integer)  # conduzioni progressive
    progressive_passes_received = Column(Integer)  # ricezioni progressive
    touches_att_pen_season      = Column(Integer)  # tocchi in area avversaria

    # ── Pressing e difesa (FBref) ────────────────────────────────
    pressures_season        = Column(Integer)   # pressioni totali
    pressure_regains_season = Column(Integer)   # pressioni riuscite (palla recuperata)
    tackles_season          = Column(Integer)   # tackle
    interceptions_season    = Column(Integer)   # intercetti

    # ── Duelli (API-Football + FBref) ────────────────────────────
    duels_total_season   = Column(Integer)
    duels_won_season     = Column(Integer)
    duels_won_pct        = Column(Float)    # % duelli vinti
    aerial_duels_won_pct = Column(Float)    # % duelli aerei vinti

    # ── Passaggi (API-Football) ───────────────────────────────────
    pass_accuracy_pct = Column(Float)       # % precisione passaggi

    # ── Score oggettivi 0-100 (calcolati da recalculate_objective_scores) ──
    # Sostituiscono pace/shooting/passing/dribbling/defending/physical (FIFA)
    finishing_score     = Column(Float)   # npxG/90 + conversione gol/xG
    creativity_score    = Column(Float)   # xA/90 + PrgP/90 + key passes/90
    pressing_score      = Column(Float)   # pressioni riuscite/90 + regains/90
    carrying_score      = Column(Float)   # PrgC/90 + tocchi area/90
    defending_obj_score = Column(Float)   # duelli vinti % + aerei % + tackle/90
    buildup_obj_score   = Column(Float)   # xGChain/90 + xGBuildup/90

    # ── Percentile per ruolo (calcolati da recalculate_percentiles) ─
    finishing_pct     = Column(Float)   # posizione percentile tra giocatori stesso ruolo
    creativity_pct    = Column(Float)
    pressing_pct      = Column(Float)
    carrying_pct      = Column(Float)
    defending_pct     = Column(Float)
    buildup_pct       = Column(Float)

    # ── Score compositi legacy (mantenuti per compatibilità UI) ──
    # Verranno ricalcolati su base oggettiva da scoring.py aggiornato
    heading_score    = Column(Float)   # → sarà = defending_obj_score * aerial_duels_won_pct
    build_up_score   = Column(Float)   # → sarà = buildup_obj_score
    defensive_score  = Column(Float)   # → sarà = defending_obj_score

    # ── Timestamp per sorgente ───────────────────────────────────
    last_updated_understat     = Column(DateTime)
    last_updated_fbref         = Column(DateTime)
    last_updated_api_football  = Column(DateTime)
    last_updated_statsbomb     = Column(DateTime)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)