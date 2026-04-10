"""
app/models/models.py — v3.0 (pulizia DB completata)

DIFFERENZE rispetto a v2 (file allegato)
─────────────────────────────────────────
ScoutingPlayer: rimosse 18 colonne che appartengono alle tabelle figlie:

  RIMOSSO → player_sofascore_stats:
    season_club, sofascore_attributes_raw, sofascore_attributes_avg_raw

  RIMOSSO → player_scouting_index:
    finishing_score, creativity_score, pressing_score, carrying_score,
    defending_obj_score, buildup_obj_score,
    finishing_pct, creativity_pct, pressing_pct, carrying_pct,
    defending_pct, buildup_pct,
    heading_score, build_up_score, defensive_score

  RIMOSSO definitivamente (duplicati / obsoleti):
    build_up_score   (era alias di buildup_obj_score)
    defensive_score  (era alias di defending_obj_score)

Mantenuto su ScoutingPlayer:
  • Tutta l'anagrafica
  • Tutti gli ID provider
  • sofascore_rating  (cache UI, senza join — fonte di verità: player_sofascore_stats)
  • Tutti i timestamp last_updated_*
  • Tutte le @property (leggono da PlayerSeasonStats — invariate)
  • Tutte le relationship (invariate)

Tutto il resto del file (Club, PlayerSeasonStats, PlayerMatch,
PlayerHeatmap, PlayerCareer, PlayerNationalStats) è INVARIATO.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, ForeignKey,
    DateTime, Enum, Date, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


# ══════════════════════════════════════════════════════════════════
# ENUM & LOOKUP  — invariati
# ══════════════════════════════════════════════════════════════════

class TraitType(str, enum.Enum):
    positive = "positive"
    negative = "negative"


# ══════════════════════════════════════════════════════════════════
# MY TEAM  — invariato
# ══════════════════════════════════════════════════════════════════

class MyTeam(Base):
    __tablename__ = "my_team"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), nullable=False)
    formation  = Column(String(20))
    league     = Column(String(100))
    season     = Column(String(20))
    coach      = Column(String(100))
    budget     = Column(Float)
    notes      = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    season         = Column(String(20), nullable=True)

    team = relationship("MyTeam", back_populates="players")


# ══════════════════════════════════════════════════════════════════
# SCOUTING PLAYER — v3.0
# Solo anagrafica + ID provider + cache rating.
# Score e percentili → player_scouting_index
# Attributi blob    → player_sofascore_stats
# ══════════════════════════════════════════════════════════════════

class ScoutingPlayer(Base):
    __tablename__ = "scouting_players"

    id = Column(Integer, primary_key=True, index=True)

    # ── Identificatori provider ──────────────────────────────────
    api_football_id  = Column(Integer,    unique=True, index=True, nullable=True)
    transfermarkt_id = Column(String(50), unique=True, index=True, nullable=True)
    fbref_id         = Column(String(50), unique=True, index=True, nullable=True)
    understat_id     = Column(String(20), unique=True, index=True, nullable=True)
    sofascore_id     = Column(String(20), unique=True, index=True, nullable=True)

    # ── Anagrafica ───────────────────────────────────────────────
    name            = Column(String(100), nullable=False, index=True)
    birth_date      = Column(Date,        index=True,     nullable=True)
    position        = Column(String(20))
    position_detail = Column(String(50))
    club            = Column(String(100))
    club_id         = Column(Integer, ForeignKey("clubs.id"), nullable=True)
    nationality     = Column(String(50))
    age             = Column(Integer)
    preferred_foot  = Column(String(10))
    height          = Column(Integer)
    weight          = Column(Integer)
    jersey_number   = Column(Integer)
    gender          = Column(String(5), default='M')

    # ── Valori economici ─────────────────────────────────────────
    market_value   = Column(Float, nullable=True)
    contract_until = Column(Date,  nullable=True)

    # ── Cache ultimo rating (denormalizzata per la UI) ───────────
    # Fonte di verità: PlayerSofascoreStats.sofascore_rating
    sofascore_rating = Column(Float, nullable=True)

    # ── Timestamp per sorgente ────────────────────────────────────
    last_updated_understat    = Column(DateTime)
    last_updated_fbref        = Column(DateTime)
    last_updated_api_football = Column(DateTime)
    last_updated_statsbomb    = Column(DateTime)
    last_updated_sofascore    = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── @property (leggono da PlayerSeasonStats) ─────────────────

    @property
    def minutes_season(self):
        from sqlalchemy.orm import object_session
        session = object_session(self)
        if not session:
            return 0
        stats = session.query(PlayerSeasonStats).filter(
            PlayerSeasonStats.player_id == self.id
        ).order_by(PlayerSeasonStats.season.desc()).first()
        if stats and getattr(stats, "minutes_played", None):
            return stats.minutes_played
        return 0

    def _get_latest_stat(self, stat_name, default_value=0.0):
        from sqlalchemy.orm import object_session
        session = object_session(self)
        if not session:
            return default_value
        stats = session.query(PlayerSeasonStats).filter(
            PlayerSeasonStats.player_id == self.id
        ).order_by(PlayerSeasonStats.id.desc()).first()
        if stats and getattr(stats, stat_name, None) is not None:
            val = getattr(stats, stat_name)
            return float(val) if isinstance(default_value, float) else val
        return default_value

    @property
    def npxg_per90(self):               return self._get_latest_stat("npxg_per90", 0.0)
    @property
    def xg_per90(self):                 return self._get_latest_stat("xg_per90", 0.0)
    @property
    def xa_per90(self):                 return self._get_latest_stat("xa_per90", 0.0)
    @property
    def goals_season(self):             return self._get_latest_stat("goals", 0)
    @property
    def assists_season(self):           return self._get_latest_stat("assists", 0)
    @property
    def key_passes_per90(self):         return self._get_latest_stat("key_passes_per90", 0.0)
    @property
    def successful_dribbles_per90(self):return self._get_latest_stat("successful_dribbles_per90", 0.0)
    @property
    def tackles_per90(self):            return self._get_latest_stat("tackles_per90", 0.0)
    @property
    def interceptions_per90(self):      return self._get_latest_stat("interceptions_per90", 0.0)
    @property
    def xgchain_per90(self):            return self._get_latest_stat("xgchain_per90", 0.0)
    @property
    def xbuildup_per90(self):           return self._get_latest_stat("xbuildup_per90", 0.0)
    @property
    def xgbuildup_per90(self):          return self._get_latest_stat("xgbuildup_per90", 0.0)
    @property
    def shots_season(self):             return self._get_latest_stat("shots", 0)
    @property
    def key_passes_season(self):        return self._get_latest_stat("key_passes", 0)
    @property
    def yellow_cards_season(self):      return self._get_latest_stat("yellow_cards", 0)
    @property
    def red_cards_season(self):         return self._get_latest_stat("red_cards", 0)
    @property
    def dribbles_season(self):          return self._get_latest_stat("successful_dribbles", 0)
    @property
    def progressive_passes(self):       return self._get_latest_stat("progressive_passes", 0)
    @property
    def progressive_carries(self):      return self._get_latest_stat("progressive_carries", 0)
    @property
    def touches_att_pen_season(self):   return self._get_latest_stat("touches_att_pen", 0)
    @property
    def progressive_passes_received_season(self): return self._get_latest_stat("progressive_passes_received", 0)
    @property
    def crosses_season(self):           return self._get_latest_stat("crosses", 0)
    @property
    def crosses_into_pen_area_season(self): return self._get_latest_stat("crosses_into_pen_area", 0)
    @property
    def pressures_season(self):         return self._get_latest_stat("pressures", 0)
    @property
    def successful_pressures_season(self): return self._get_latest_stat("successful_pressures", 0)
    @property
    def blocks_season(self):            return self._get_latest_stat("blocks", 0)
    @property
    def interceptions_season(self):     return self._get_latest_stat("interceptions", 0)
    @property
    def clearances_season(self):        return self._get_latest_stat("clearances", 0)
    @property
    def pressure_regains_season(self):  return self._get_latest_stat("pressure_regains", 0)
    @property
    def dribbled_past_season(self):     return self._get_latest_stat("dribbled_past", 0)
    @property
    def goal_line_clearances_season(self): return self._get_latest_stat("goal_line_clearances", 0)
    @property
    def errors_leading_to_shot_season(self): return self._get_latest_stat("errors_leading_to_shot", 0)
    @property
    def tackles_season(self):           return self._get_latest_stat("tackles", 0)
    @property
    def tackles_won_season(self):       return self._get_latest_stat("tackles_won", 0)
    @property
    def shots_blocked_season(self):     return self._get_latest_stat("shots_blocked", 0)
    @property
    def duels_won_pct(self):            return self._get_latest_stat("duels_won_pct", 0.0)
    @property
    def aerial_duels_won_pct(self):     return self._get_latest_stat("aerial_duels_won_pct", 0.0)
    @property
    def ground_duels_won_pct(self):     return self._get_latest_stat("ground_duels_won_pct", 0.0)
    @property
    def pass_accuracy_pct(self):        return self._get_latest_stat("pass_accuracy_pct", 0.0)
    @property
    def pass_accuracy_opp_half_pct(self): return self._get_latest_stat("pass_accuracy_opp_half_pct", 0.0)

    # ── Relazioni ─────────────────────────────────────────────────
    season_stats   = relationship("PlayerSeasonStats",  back_populates="player", cascade="all, delete-orphan")
    matches        = relationship("PlayerMatch",         back_populates="player", cascade="all, delete-orphan")
    heatmaps       = relationship("PlayerHeatmap",       back_populates="player", cascade="all, delete-orphan")
    career         = relationship("PlayerCareer",        back_populates="player", cascade="all, delete-orphan")
    national_stats = relationship("PlayerNationalStats", back_populates="player", cascade="all, delete-orphan")
    club_relation  = relationship("Club",                back_populates="players")
    fbref_stats      = relationship("PlayerFbrefStats",    back_populates="player", cascade="all, delete-orphan")
    fbref_match_logs = relationship("PlayerFbrefMatchLog", back_populates="player", cascade="all, delete-orphan")
    scouting_index   = relationship("PlayerScoutingIndex", back_populates="player", uselist=False, cascade="all, delete-orphan")
    sofascore_stats  = relationship("PlayerSofascoreStats", back_populates="player", cascade="all, delete-orphan")


# ══════════════════════════════════════════════════════════════════
# CLUB  — invariato
# ══════════════════════════════════════════════════════════════════

class Club(Base):
    __tablename__ = "clubs"
    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, unique=True, index=True)
    league_key = Column(String, index=True)
    country    = Column(String)
    players    = relationship("ScoutingPlayer", back_populates="club_relation")


# ══════════════════════════════════════════════════════════════════
# PLAYER SEASON STATS  — invariata
# ══════════════════════════════════════════════════════════════════

class PlayerSeasonStats(Base):
    __tablename__ = "player_season_stats"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    season    = Column(String(10), nullable=False)
    league    = Column(String(50), nullable=False)
    source    = Column(String(30), nullable=False)

    sofascore_rating  = Column(Float)
    appearances       = Column(Integer)
    matches_started   = Column(Integer)
    minutes_played    = Column(Integer)
    goals                  = Column(Integer)
    assists                = Column(Integer)
    goals_assists_sum      = Column(Integer)
    shots_total            = Column(Integer)
    shots_on_target        = Column(Integer)
    shots_off_target       = Column(Integer)
    shots_inside_box       = Column(Integer)
    shots_outside_box      = Column(Integer)
    big_chances_created    = Column(Integer)
    big_chances_missed     = Column(Integer)
    goal_conversion_pct    = Column(Float)
    headed_goals           = Column(Integer)
    left_foot_goals        = Column(Integer)
    right_foot_goals       = Column(Integer)
    goals_inside_box       = Column(Integer)
    goals_outside_box      = Column(Integer)
    free_kick_goals        = Column(Integer)
    penalty_goals          = Column(Integer)
    penalty_taken          = Column(Integer)
    penalty_won            = Column(Integer)
    own_goals              = Column(Integer)
    xg                = Column(Float)
    xa                = Column(Float)
    xg_per90          = Column(Float)
    xa_per90          = Column(Float)
    npxg_per90        = Column(Float)
    xgchain_per90     = Column(Float)
    xgbuildup_per90   = Column(Float)
    accurate_passes           = Column(Integer)
    inaccurate_passes         = Column(Integer)
    total_passes              = Column(Integer)
    pass_accuracy_pct         = Column(Float)
    accurate_own_half_passes  = Column(Integer)
    accurate_opp_half_passes  = Column(Integer)
    accurate_final_third_passes = Column(Integer)
    accurate_long_balls       = Column(Integer)
    long_ball_accuracy_pct    = Column(Float)
    total_long_balls          = Column(Integer)
    accurate_crosses          = Column(Integer)
    cross_accuracy_pct        = Column(Float)
    total_crosses             = Column(Integer)
    key_passes                = Column(Integer)
    pass_to_assist            = Column(Integer)
    chipped_passes            = Column(Integer)
    progressive_passes          = Column(Integer)
    progressive_carries         = Column(Integer)
    progressive_passes_received = Column(Integer)
    touches_att_pen             = Column(Integer)
    successful_dribbles     = Column(Integer)
    dribble_success_pct     = Column(Float)
    dribbled_past           = Column(Integer)
    dispossessed            = Column(Integer)
    ground_duels_won        = Column(Integer)
    ground_duels_won_pct    = Column(Float)
    aerial_duels_won        = Column(Integer)
    aerial_duels_lost       = Column(Integer)
    aerial_duels_won_pct    = Column(Float)
    total_duels_won         = Column(Integer)
    total_duels_won_pct     = Column(Float)
    total_contest           = Column(Integer)
    tackles           = Column(Integer)
    tackles_won       = Column(Integer)
    tackles_won_pct   = Column(Float)
    interceptions     = Column(Integer)
    clearances        = Column(Integer)
    blocked_shots     = Column(Integer)
    errors_led_to_goal = Column(Integer)
    errors_led_to_shot = Column(Integer)
    ball_recovery     = Column(Integer)
    possession_won_att_third = Column(Integer)
    pressures           = Column(Integer)
    pressure_regains    = Column(Integer)
    touches             = Column(Integer)
    possession_lost     = Column(Integer)
    shot_from_set_piece = Column(Integer)
    yellow_cards    = Column(Integer)
    yellow_red_cards = Column(Integer)
    red_cards       = Column(Integer)
    fouls_committed = Column(Integer)
    fouls_won       = Column(Integer)
    offsides        = Column(Integer)
    hit_woodwork    = Column(Integer)
    saves                        = Column(Integer)
    goals_conceded               = Column(Integer)
    goals_conceded_inside_box    = Column(Integer)
    goals_conceded_outside_box   = Column(Integer)
    clean_sheets                 = Column(Integer)
    penalty_saved                = Column(Integer)
    penalty_faced                = Column(Integer)
    high_claims                  = Column(Integer)
    punches                      = Column(Integer)
    runs_out                     = Column(Integer)
    successful_runs_out          = Column(Integer)
    saved_shots_inside_box       = Column(Integer)
    saved_shots_outside_box      = Column(Integer)
    fanta_media         = Column(Float)
    fanta_media_mv      = Column(Float)
    fanta_gol           = Column(Integer)
    fanta_assist        = Column(Integer)
    fanta_ammonizioni   = Column(Integer)
    fanta_espulsioni    = Column(Integer)
    fanta_rigori_segnati = Column(Integer)
    fanta_rigori_sbagliati = Column(Integer)
    fanta_autogol       = Column(Integer)
    fanta_presenze      = Column(Integer)
    tournament_id = Column(Integer, nullable=True)
    season_id     = Column(Integer, nullable=True)
    fetched_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="season_stats")

    __table_args__ = (
        UniqueConstraint('player_id', 'season', 'league', 'source',
                         name='uq_player_season_league_source'),
        Index('ix_season_stats_player_season', 'player_id', 'season'),
    )


# ══════════════════════════════════════════════════════════════════
# PLAYER MATCH  — invariata
# ══════════════════════════════════════════════════════════════════

class PlayerMatch(Base):
    __tablename__ = "player_matches"

    id         = Column(Integer, primary_key=True, index=True)
    player_id  = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    event_id   = Column(Integer, nullable=True, index=True)
    date       = Column(DateTime, nullable=True, index=True)
    season     = Column(String(10), nullable=True)
    tournament = Column(String(100), nullable=True)
    home_team  = Column(String(100))
    away_team  = Column(String(100))
    home_score = Column(Integer)
    away_score = Column(Integer)
    rating         = Column(Float)
    minutes_played = Column(Integer)
    goals          = Column(Integer, default=0)
    assists        = Column(Integer, default=0)
    yellow_card    = Column(Integer, default=0)
    red_card       = Column(Integer, default=0)
    source     = Column(String(20), default='sofascore')
    fetched_at = Column(DateTime, default=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="matches")

    __table_args__ = (
        UniqueConstraint('player_id', 'event_id', name='uq_player_event'),
        Index('ix_player_match_player_date', 'player_id', 'date'),
    )


# ══════════════════════════════════════════════════════════════════
# PLAYER HEATMAP  — invariata
# ══════════════════════════════════════════════════════════════════

class PlayerHeatmap(Base):
    __tablename__ = "player_heatmap"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    season    = Column(String(10), nullable=False)
    league    = Column(String(50), nullable=False)
    points      = Column(JSON, nullable=True)
    point_count = Column(Integer, default=0)
    position_played = Column(String(20), nullable=True)
    source          = Column(String(20), default='sofascore')
    fetched_at      = Column(DateTime, default=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="heatmaps")

    __table_args__ = (
        UniqueConstraint('player_id', 'season', 'league', 'source',
                         name='uq_heatmap_player_season_league'),
    )


# ══════════════════════════════════════════════════════════════════
# PLAYER CAREER  — invariata
# ══════════════════════════════════════════════════════════════════

class PlayerCareer(Base):
    __tablename__ = "player_career"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    from_team     = Column(String(100))
    to_team       = Column(String(100))
    transfer_date = Column(DateTime, nullable=True)
    fee           = Column(Float, nullable=True)
    transfer_type = Column(String(30), nullable=True)
    season        = Column(String(10), nullable=True)
    source     = Column(String(20), default='sofascore')
    fetched_at = Column(DateTime, default=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="career")


# ══════════════════════════════════════════════════════════════════
# PLAYER NATIONAL STATS  — invariata
# ══════════════════════════════════════════════════════════════════

class PlayerNationalStats(Base):
    __tablename__ = "player_national_stats"

    id            = Column(Integer, primary_key=True, index=True)
    player_id     = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    national_team = Column(String(100), nullable=True)
    season        = Column(String(10),  nullable=True)
    appearances   = Column(Integer)
    minutes       = Column(Integer)
    goals         = Column(Integer)
    assists       = Column(Integer)
    rating        = Column(Float)
    yellow_cards  = Column(Integer)
    red_cards     = Column(Integer)
    raw_data      = Column(JSON, nullable=True)
    source     = Column(String(20), default='sofascore')
    fetched_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="national_stats")

    __table_args__ = (
        UniqueConstraint('player_id', 'national_team', 'season', 'source',
                         name='uq_national_player_team_season'),
    )