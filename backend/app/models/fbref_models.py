"""
app/models/fbref_models.py

Tre nuove tabelle dedicate ai dati FBref:
  - PlayerFbrefStats     : statistiche stagionali aggregate (standard, shooting,
                           passing, defense, gca, possession, misc)
  - PlayerFbrefMatchLog  : match log partita per partita
  - PlayerScoutingIndex  : parametri intelligenti calcolati dall'algoritmo multi-fonte

Come collegarlo a models.py esistente
──────────────────────────────────────
Aggiungere in ScoutingPlayer le tre relationship:

    fbref_stats      = relationship("PlayerFbrefStats",    back_populates="player", cascade="all, delete-orphan")
    fbref_match_logs = relationship("PlayerFbrefMatchLog", back_populates="player", cascade="all, delete-orphan")
    scouting_index   = relationship("PlayerScoutingIndex", back_populates="player", uselist=False, cascade="all, delete-orphan")

Poi importare questo modulo in alembic/env.py o dove carichi i modelli:
    from app.models import fbref_models  # noqa
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float,
    ForeignKey, DateTime, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


# ══════════════════════════════════════════════════════════════════
# PLAYER FBREF STATS
# Una riga per (player_id, season, league).
# I campi rispecchiano 1:1 le chiavi data-stat di FBref.
# ══════════════════════════════════════════════════════════════════

class PlayerFbrefStats(Base):
    __tablename__ = "player_fbref_stats"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    season    = Column(String(10), nullable=False)   # es. "2025-2026"
    league    = Column(String(80), nullable=False)   # es. "Serie A"

    # ── Standard ─────────────────────────────────────────────────
    appearances        = Column(Integer)    # games
    starts             = Column(Integer)    # games_starts
    minutes            = Column(Integer)
    goals              = Column(Integer)
    assists            = Column(Integer)
    goals_pens         = Column(Integer)
    pens_made          = Column(Integer)
    pens_att           = Column(Integer)
    yellow_cards       = Column(Integer)
    red_cards          = Column(Integer)
    xg                 = Column(Float)
    npxg               = Column(Float)
    xa                 = Column(Float)
    npxg_xa            = Column(Float)
    goals_per90        = Column(Float)
    assists_per90      = Column(Float)
    xg_per90           = Column(Float)
    xa_per90           = Column(Float)
    npxg_per90         = Column(Float)

    # ── Shooting ─────────────────────────────────────────────────
    shots              = Column(Integer)
    shots_on_target    = Column(Integer)
    shots_on_target_pct = Column(Float)
    shots_per90        = Column(Float)
    sot_per90          = Column(Float)
    goals_per_shot     = Column(Float)
    goals_per_sot      = Column(Float)
    avg_shot_distance  = Column(Float)
    npxg_per_shot      = Column(Float)
    xg_net             = Column(Float)
    npxg_net           = Column(Float)

    # ── Passing ──────────────────────────────────────────────────
    passes_completed       = Column(Integer)
    passes_attempted       = Column(Integer)
    pass_completion_pct    = Column(Float)
    passes_total_dist      = Column(Float)
    passes_prog_dist       = Column(Float)
    passes_short_pct       = Column(Float)
    passes_medium_pct      = Column(Float)
    passes_long_completed  = Column(Integer)
    passes_long_attempted  = Column(Integer)
    passes_long_pct        = Column(Float)
    key_passes             = Column(Integer)
    passes_final_third     = Column(Integer)
    passes_penalty_area    = Column(Integer)
    crosses_penalty_area   = Column(Integer)
    progressive_passes     = Column(Integer)
    xa_pass                = Column(Float)

    # ── GCA ──────────────────────────────────────────────────────
    sca                = Column(Integer)
    sca_per90          = Column(Float)
    sca_pass_live      = Column(Integer)
    sca_pass_dead      = Column(Integer)
    sca_take_on        = Column(Integer)
    sca_shot           = Column(Integer)
    gca                = Column(Integer)
    gca_per90          = Column(Float)
    gca_pass_live      = Column(Integer)
    gca_take_on        = Column(Integer)

    # ── Defense ──────────────────────────────────────────────────
    tackles            = Column(Integer)
    tackles_won        = Column(Integer)
    tackles_def_3rd    = Column(Integer)
    tackles_mid_3rd    = Column(Integer)
    tackles_att_3rd    = Column(Integer)
    challenge_tackles  = Column(Integer)
    challenges         = Column(Integer)
    challenge_tackles_pct = Column(Float)
    blocks             = Column(Integer)
    blocked_shots      = Column(Integer)
    blocked_passes     = Column(Integer)
    interceptions      = Column(Integer)
    tkl_int            = Column(Integer)
    clearances         = Column(Integer)
    errors             = Column(Integer)

    # ── Possession ───────────────────────────────────────────────
    touches            = Column(Integer)
    touches_def_pen    = Column(Integer)
    touches_def_3rd    = Column(Integer)
    touches_mid_3rd    = Column(Integer)
    touches_att_3rd    = Column(Integer)
    touches_att_pen    = Column(Integer)
    take_ons_att       = Column(Integer)
    take_ons_succ      = Column(Integer)
    take_ons_succ_pct  = Column(Float)
    take_ons_tackled   = Column(Integer)
    carries            = Column(Integer)
    carries_prog_dist  = Column(Float)
    progressive_carries = Column(Integer)
    carries_final_third = Column(Integer)
    carries_penalty_area = Column(Integer)
    miscontrols        = Column(Integer)
    dispossessed       = Column(Integer)
    progressive_passes_received = Column(Integer)

    # ── Misc ─────────────────────────────────────────────────────
    fouls_committed    = Column(Integer)
    fouls_drawn        = Column(Integer)
    offsides           = Column(Integer)
    crosses            = Column(Integer)
    pens_won           = Column(Integer)
    pens_conceded      = Column(Integer)
    own_goals          = Column(Integer)
    ball_recoveries    = Column(Integer)
    aerials_won        = Column(Integer)
    aerials_lost       = Column(Integer)
    aerials_won_pct    = Column(Float)

    # ── Meta ─────────────────────────────────────────────────────
    fbref_player_id    = Column(String(20), nullable=True)
    fetched_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="fbref_stats")

    __table_args__ = (
        UniqueConstraint('player_id', 'season', 'league',
                         name='uq_fbref_player_season_league'),
        Index('ix_fbref_stats_player_season', 'player_id', 'season'),
    )


# ══════════════════════════════════════════════════════════════════
# PLAYER FBREF MATCH LOG
# Una riga per partita. Rispecchia le chiavi del match log FBref.
# ══════════════════════════════════════════════════════════════════

class PlayerFbrefMatchLog(Base):
    __tablename__ = "player_fbref_match_logs"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    season    = Column(String(10), nullable=True)

    date        = Column(String(20), nullable=True, index=True)
    dayofweek   = Column(String(10), nullable=True)
    comp        = Column(String(80), nullable=True)
    round       = Column(String(40), nullable=True)
    venue       = Column(String(10), nullable=True)
    result      = Column(String(15), nullable=True)
    team        = Column(String(80), nullable=True)
    opponent    = Column(String(80), nullable=True)
    game_started = Column(String(5), nullable=True)
    position    = Column(String(10), nullable=True)
    minutes     = Column(Integer, nullable=True)
    goals       = Column(Integer, nullable=True)
    assists     = Column(Integer, nullable=True)
    pens_made   = Column(Integer, nullable=True)
    pens_att    = Column(Integer, nullable=True)
    shots       = Column(Integer, nullable=True)
    shots_on_target = Column(Integer, nullable=True)
    yellow_card = Column(Integer, nullable=True)
    red_card    = Column(Integer, nullable=True)
    fouls_committed = Column(Integer, nullable=True)
    fouls_drawn = Column(Integer, nullable=True)
    offsides    = Column(Integer, nullable=True)
    crosses     = Column(Integer, nullable=True)
    tackles_won = Column(Integer, nullable=True)
    interceptions = Column(Integer, nullable=True)
    own_goals   = Column(Integer, nullable=True)
    pens_won    = Column(String(5), nullable=True)
    pens_conceded = Column(String(5), nullable=True)

    fetched_at  = Column(DateTime, default=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="fbref_match_logs")

    __table_args__ = (
        UniqueConstraint('player_id', 'date', 'comp',
                         name='uq_fbref_matchlog_player_date_comp'),
        Index('ix_fbref_matchlog_player_date', 'player_id', 'date'),
    )


# ══════════════════════════════════════════════════════════════════
# PLAYER SCOUTING INDEX
# Parametri intelligenti calcolati dall'algoritmo multi-fonte.
# Una riga per (player_id, season) — si ricalcola ogni importazione.
#
# ALGORITMO — logica dei 6 indici (0-100, percentile per ruolo):
# ─────────────────────────────────────────────────────────────────
# finishing_index  : goals_per_shot, shots_on_target_pct, xg_net,
#                    npxg_per90  (FBref Shooting + Standard)
# creativity_index : key_passes/90, xa_per90, sca_per90, gca_per90,
#                    progressive_passes/90  (FBref Passing + GCA)
# pressing_index   : tackles_won, interceptions/90, ball_recoveries,
#                    fouls_drawn  (FBref Defense + Misc)
# carrying_index   : progressive_carries/90, carries_prog_dist,
#                    take_ons_succ_pct, touches_att_pen  (FBref Possession)
# defending_index  : challenge_tackles_pct, interceptions/90,
#                    clearances/90, aerials_won_pct  (FBref Defense)
# buildup_index    : pass_completion_pct, passes_long_pct,
#                    progressive_passes_received/90, xa  (FBref Passing)
# overall_index    : media pesata per ruolo dei 6 indici sopra
# ─────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

class PlayerScoutingIndex(Base):
    __tablename__ = "player_scouting_index"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    season    = Column(String(10), nullable=False)
    position_group = Column(String(5), nullable=True)  # "GK"|"DEF"|"MID"|"FWD"

    # ── Indici 0-100 (percentile nel gruppo-ruolo) ────────────────
    finishing_index   = Column(Float, nullable=True)
    creativity_index  = Column(Float, nullable=True)
    pressing_index    = Column(Float, nullable=True)
    carrying_index    = Column(Float, nullable=True)
    defending_index   = Column(Float, nullable=True)
    buildup_index     = Column(Float, nullable=True)
    overall_index     = Column(Float, nullable=True)

    # ── Valori grezzi usati nel calcolo (tracciabilità) ───────────
    xg_per90                  = Column(Float, nullable=True)
    xa_per90                  = Column(Float, nullable=True)
    npxg_per90                = Column(Float, nullable=True)
    sca_per90                 = Column(Float, nullable=True)
    gca_per90                 = Column(Float, nullable=True)
    progressive_carries_per90 = Column(Float, nullable=True)
    progressive_passes_per90  = Column(Float, nullable=True)
    tackles_won_per90         = Column(Float, nullable=True)
    interceptions_per90       = Column(Float, nullable=True)
    aerials_won_pct           = Column(Float, nullable=True)
    take_ons_succ_pct         = Column(Float, nullable=True)
    pass_completion_pct       = Column(Float, nullable=True)
    goals_per_shot            = Column(Float, nullable=True)
    ball_recoveries_per90     = Column(Float, nullable=True)
    crosses_per90             = Column(Float, nullable=True)

    # ── Metadati calcolo ──────────────────────────────────────────
    sources_used      = Column(JSON, nullable=True)   # ["fbref", "sofascore"]
    data_confidence   = Column(Float, nullable=True)  # 0.0 – 1.0
    minutes_sample    = Column(Integer, nullable=True)

    computed_at = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="scouting_index")

    __table_args__ = (
        UniqueConstraint('player_id', 'season',
                         name='uq_scouting_index_player_season'),
    )