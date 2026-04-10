"""
app/models/sofascore_models.py — v2.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DIFFERENZE rispetto a v1 (file allegato)
────────────────────────────────────────
Aggiunte 3 colonne che erano su scouting_players:
  + attributes_raw      (JSON)  — ex sofascore_attributes_raw
  + attributes_avg_raw  (JSON)  — ex sofascore_attributes_avg_raw
  + season_club         (str)   — ex season_club

Tutto il resto è invariato.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, JSON,
    ForeignKey, DateTime, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


class PlayerSofascoreStats(Base):
    """
    Statistiche stagionali SofaScore.
    Una riga per (player_id, season, league).
    """
    __tablename__ = "player_sofascore_stats"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(
        Integer,
        ForeignKey("scouting_players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    season = Column(String(10), nullable=False)   # es. "2025-26"
    league = Column(String(80), nullable=False)   # es. "Serie A"

    # ── Rating & volume ─────────────────────────────────────────────
    sofascore_rating  = Column(Float)
    appearances       = Column(Integer)
    matches_started   = Column(Integer)
    minutes_played    = Column(Integer)

    # ── Attacco ─────────────────────────────────────────────────────
    goals                 = Column(Integer)
    assists               = Column(Integer)
    goals_assists_sum     = Column(Integer)
    shots_total           = Column(Integer)
    shots_on_target       = Column(Integer)
    shots_off_target      = Column(Integer)
    big_chances_created   = Column(Integer)
    big_chances_missed    = Column(Integer)
    goal_conversion_pct   = Column(Float)
    headed_goals          = Column(Integer)
    penalty_goals         = Column(Integer)
    penalty_won           = Column(Integer)

    # ── xG / xA ─────────────────────────────────────────────────────
    xg        = Column(Float)
    xa        = Column(Float)
    xg_per90  = Column(Float)
    xa_per90  = Column(Float)

    # ── Passaggi ────────────────────────────────────────────────────
    accurate_passes             = Column(Integer)
    inaccurate_passes           = Column(Integer)
    total_passes                = Column(Integer)
    pass_accuracy_pct           = Column(Float)
    accurate_long_balls         = Column(Integer)
    long_ball_accuracy_pct      = Column(Float)
    total_long_balls            = Column(Integer)
    accurate_crosses            = Column(Integer)
    cross_accuracy_pct          = Column(Float)
    total_crosses               = Column(Integer)
    key_passes                  = Column(Integer)
    accurate_own_half_passes    = Column(Integer)
    accurate_opp_half_passes    = Column(Integer)
    accurate_final_third_passes = Column(Integer)

    # ── Dribbling ───────────────────────────────────────────────────
    successful_dribbles    = Column(Integer)
    dribble_attempts       = Column(Integer)
    dribble_success_pct    = Column(Float)
    dribbled_past          = Column(Integer)
    dispossessed           = Column(Integer)

    # ── Duelli ──────────────────────────────────────────────────────
    ground_duels_won       = Column(Integer)
    ground_duels_won_pct   = Column(Float)
    aerial_duels_won       = Column(Integer)
    aerial_duels_lost      = Column(Integer)
    aerial_duels_won_pct   = Column(Float)
    total_duels_won        = Column(Integer)
    total_duels_won_pct    = Column(Float)
    total_contest          = Column(Integer)

    # ── Difesa ──────────────────────────────────────────────────────
    tackles                  = Column(Integer)
    tackles_won              = Column(Integer)
    tackles_won_pct          = Column(Float)
    interceptions            = Column(Integer)
    clearances               = Column(Integer)
    blocked_shots            = Column(Integer)
    errors_led_to_goal       = Column(Integer)
    errors_led_to_shot       = Column(Integer)
    ball_recovery            = Column(Integer)
    possession_won_att_third = Column(Integer)

    # ── Possesso ────────────────────────────────────────────────────
    touches         = Column(Integer)
    possession_lost = Column(Integer)

    # ── Disciplina ──────────────────────────────────────────────────
    yellow_cards     = Column(Integer)
    yellow_red_cards = Column(Integer)
    red_cards        = Column(Integer)
    fouls_committed  = Column(Integer)
    fouls_won        = Column(Integer)
    offsides         = Column(Integer)
    hit_woodwork     = Column(Integer)

    # ── Portiere ────────────────────────────────────────────────────
    saves           = Column(Integer)
    goals_conceded  = Column(Integer)
    clean_sheets    = Column(Integer)
    penalty_saved   = Column(Integer)
    penalty_faced   = Column(Integer)
    high_claims     = Column(Integer)
    punches         = Column(Integer)

    # ── Meta SofaScore ──────────────────────────────────────────────
    tournament_id = Column(Integer, nullable=True)
    season_id     = Column(Integer, nullable=True)

    # ── NUOVO v2: spostati da scouting_players ───────────────────────
    # Club del giocatore nella stagione/lega (ex scouting_players.season_club)
    season_club = Column(String(80), nullable=True)

    # Attributi radar SofaScore (dict piatto scritto dall'RPA).
    # Ex scouting_players.sofascore_attributes_raw / ..._avg_raw.
    # Vengono scritti sulla riga con più minuti per il giocatore.
    # Il frontend li legge come: player.sources.sofascore.attributes
    attributes_raw     = Column(JSON, nullable=True)
    attributes_avg_raw = Column(JSON, nullable=True)

    # ── Timestamp ────────────────────────────────────────────────────
    fetched_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="sofascore_stats")

    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", "league",
            name="uq_sofascore_player_season_league",
        ),
        Index("ix_sofascore_stats_player_season", "player_id", "season"),
    )

    def __repr__(self):
        return (f"<PlayerSofascoreStats player_id={self.player_id} "
                f"season={self.season!r} league={self.league!r} "
                f"mins={self.minutes_played}>")