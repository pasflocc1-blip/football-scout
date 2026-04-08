"""
app/models/models.py — v2.0  (ristrutturazione DB Fase 2)

MODIFICHE rispetto alla v1:
  - scouting_players: rimossi tutti i campi statistici (ora in tabelle dedicate)
    Mantenuti: anagrafica, identificatori provider, market_value, contract_until,
               score oggettivi 0-100, percentili, timestamp per sorgente.
    Rinominati (senza impatto su altri servizi — verificato):
      rating_sofascore   → sofascore_rating    (era usato solo dall'RPA)
      heatmap_data       → rimosso (ora in player_heatmap)

  NUOVE TABELLE:
    - PlayerSeasonStats  — statistiche stagionali (una riga per player+season+league)
    - PlayerMatch        — storico partite (una riga per partita)
    - PlayerHeatmap      — punti heatmap stagionali (JSON, una riga per player+season+league)
    - PlayerCareer       — storico trasferimenti (una riga per trasferimento)
    - PlayerNationalStats — statistiche con la nazionale
    (PlayerScores già esiste come colonne in scouting_players — manteniamo per ora,
     sarà separata in Fase 3 se necessario)

  COMPATIBILITÀ:
    - Nessuna colonna usata da API-Football, FBref, Understat rinominata.
    - I campi rimossi da scouting_players (goals_season, assists_season, ecc.) erano
      scritti solo da sofascore.py e dall'RPA — aggiornare quei due file.
    - La colonna `sofascore_rating` in scouting_players viene mantenuta come cache
      dell'ultimo rating (utile per la UI senza join) ma la fonte di verità è
      PlayerSeasonStats.sofascore_rating.
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
# ENUM & LOOKUP
# ══════════════════════════════════════════════════════════════════

class TraitType(str, enum.Enum):
    positive = "positive"
    negative = "negative"


# ══════════════════════════════════════════════════════════════════
# MY TEAM  (invariato)
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
    season = Column(String(20), nullable=True)  # es. "2024-25"

    team = relationship("MyTeam", back_populates="players")


# ══════════════════════════════════════════════════════════════════
# SCOUTING PLAYER  (anagrafica + identificatori + score)
# I campi statistici sono stati spostati nelle tabelle dedicate.
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
    name           = Column(String(100), nullable=False, index=True)
    birth_date     = Column(Date,        index=True,     nullable=True)
    position       = Column(String(20))   # es. "D", "M", "F", "G"
    position_detail = Column(String(50)) # es. "ML,DL" (posizioni dettagliate SofaScore)
    club           = Column(String(100))
    club_id        = Column(Integer, ForeignKey("clubs.id"), nullable=True)
    nationality    = Column(String(50))
    age            = Column(Integer)
    preferred_foot = Column(String(10))
    height         = Column(Integer)     # cm
    weight         = Column(Integer)     # kg
    jersey_number  = Column(Integer)
    gender         = Column(String(5), default='M')

    # ── Valori economici ─────────────────────────────────────────
    market_value     = Column(Float)      # in milioni €
    contract_until   = Column(Date,  nullable=True)
    season_club = Column(String(20), nullable=True)  # stagione corrente del club es. "2024-25"

    # ── Cache ultimo rating (denormalizzata per la UI) ───────────
    # Fonte di verità: PlayerSeasonStats.sofascore_rating
    sofascore_rating = Column(Float, nullable=True)

    # ── Attributi SofaScore (radar chart nella UI) ───────────────
    # Dict piatto scritto da /ingest/sofascore/ocr.
    # Chiavi: attr_attacking, attr_technical, attr_tactical,
    #         attr_defending, attr_creativity, attr_position,
    #         attr_avg_* (opzionali, se SofaScore usa struttura a gruppi)
    sofascore_attributes_raw = Column(JSON, nullable=True)
    sofascore_attributes_avg_raw = Column(JSON, nullable=True)

    # ── Score oggettivi 0-100 (calcolati da scoring.py) ──────────
    finishing_score      = Column(Float)
    creativity_score     = Column(Float)
    pressing_score       = Column(Float)
    carrying_score       = Column(Float)
    defending_obj_score  = Column(Float)
    buildup_obj_score    = Column(Float)

    # ── Percentili per ruolo ──────────────────────────────────────
    finishing_pct    = Column(Float)
    creativity_pct   = Column(Float)
    pressing_pct     = Column(Float)
    carrying_pct     = Column(Float)
    defending_pct    = Column(Float)
    buildup_pct      = Column(Float)

    # ── Score compositi legacy (compatibilità UI) ─────────────────
    heading_score   = Column(Float)
    build_up_score  = Column(Float)
    defensive_score = Column(Float)

    # ── Timestamp per sorgente ────────────────────────────────────
    last_updated_understat    = Column(DateTime)
    last_updated_fbref        = Column(DateTime)
    last_updated_api_football = Column(DateTime)
    last_updated_statsbomb    = Column(DateTime)
    last_updated_sofascore    = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # con il.desc().first() gli stiamo dicendo di prendere solo ed esclusivamente
    # l'ultimo blocco di statistiche disponibile e scartare le stagioni '
    # passate ai fini del calcolo dello score!)
    @property
    def minutes_season(self):
        from sqlalchemy.orm import object_session
        from app.models.models import PlayerSeasonStats

        session = object_session(self)
        if not session:
            return 0

        # ⬇️ GUARDA QUI ⬇️
        # Ordiniamo per l'anno della stagione (dal più grande al più piccolo)
        # anziché per la data di download.
        stats = session.query(PlayerSeasonStats).filter(
            PlayerSeasonStats.player_id == self.id
        ).order_by(PlayerSeasonStats.season.desc()).first()

        if stats and getattr(stats, "minutes_played", None):
            return stats.minutes_played

        return 0

    # --- HELPER PER NON RISCRIVERE LA QUERY MILLE VOLTE ---
    def _get_latest_stat(self, stat_name, default_value=0.0):
        from sqlalchemy.orm import object_session
        from app.models.models import PlayerSeasonStats
        session = object_session(self)
        if not session: return default_value
        stats = session.query(PlayerSeasonStats).filter(
            PlayerSeasonStats.player_id == self.id
        ).order_by(PlayerSeasonStats.id.desc()).first()
        if stats and getattr(stats, stat_name, None) is not None:
            val = getattr(stats, stat_name)
            return float(val) if isinstance(default_value, float) else val
        return default_value

    # --- TUTTE LE STATISTICHE PRINCIPALI ---
    @property
    def npxg_per90(self):
        return self._get_latest_stat("npxg_per90", 0.0)

    @property
    def xg_per90(self):
        return self._get_latest_stat("xg_per90", 0.0)

    @property
    def xa_per90(self):
        return self._get_latest_stat("xa_per90", 0.0)

    @property
    def goals_season(self):
        return self._get_latest_stat("goals", 0)

    @property
    def assists_season(self):
        return self._get_latest_stat("assists", 0)

    @property
    def key_passes_per90(self):
        return self._get_latest_stat("key_passes_per90", 0.0)

    @property
    def successful_dribbles_per90(self):
        return self._get_latest_stat("successful_dribbles_per90", 0.0)

    @property
    def tackles_per90(self):
        return self._get_latest_stat("tackles_per90", 0.0)

    @property
    def interceptions_per90(self):
        return self._get_latest_stat("interceptions_per90", 0.0)

    @property
    def xgchain_per90(self):
        return self._get_latest_stat("xgchain_per90", 0.0)

    @property
    def xbuildup_per90(self):
        return self._get_latest_stat("xbuildup_per90", 0.0)

    @property
    def xgbuildup_per90(self):
        return self._get_latest_stat("xgbuildup_per90", 0.0)

    @property
    def shots_season(self):
        return self._get_latest_stat("shots", 0)

    @property
    def key_passes_season(self):
        return self._get_latest_stat("key_passes", 0)

    @property
    def yellow_cards_season(self):
        return self._get_latest_stat("yellow_cards", 0)

    @property
    def red_cards_season(self):
        return self._get_latest_stat("red_cards", 0)

    @property
    def dribbles_season(self):
        # Di solito SofaScore chiama i dribbling riusciti "successful_dribbles"
        return self._get_latest_stat("successful_dribbles", 0)

    @property
    def progressive_passes(self):
        return self._get_latest_stat("progressive_passes", 0)

    @property
    def progressive_carries(self):
        return self._get_latest_stat("progressive_carries", 0)

    @property
    def touches_att_pen_season(self):
        return self._get_latest_stat("touches_att_pen", 0)

    @property
    def progressive_passes_received_season(self):
        return self._get_latest_stat("progressive_passes_received", 0)

    @property
    def crosses_season(self):
        return self._get_latest_stat("crosses", 0)

    @property
    def crosses_into_pen_area_season(self):
        return self._get_latest_stat("crosses_into_pen_area", 0)

    @property
    def pressures_season(self):
        return self._get_latest_stat("pressures", 0)

    @property
    def successful_pressures_season(self):
        return self._get_latest_stat("successful_pressures", 0)

    @property
    def blocks_season(self):
        return self._get_latest_stat("blocks", 0)

    @property
    def interceptions_season(self):
        return self._get_latest_stat("interceptions", 0)

    @property
    def clearances_season(self):
        return self._get_latest_stat("clearances", 0)

    @property
    def pressure_regains_season(self):
        return self._get_latest_stat("pressure_regains", 0)

    @property
    def dribbled_past_season(self):
        return self._get_latest_stat("dribbled_past", 0)

    @property
    def goal_line_clearances_season(self):
        return self._get_latest_stat("goal_line_clearances", 0)

    @property
    def errors_leading_to_shot_season(self):
        return self._get_latest_stat("errors_leading_to_shot", 0)

    @property
    def tackles_season(self):
        return self._get_latest_stat("tackles", 0)

    @property
    def tackles_won_season(self):
        return self._get_latest_stat("tackles_won", 0)

    @property
    def shots_blocked_season(self):
        return self._get_latest_stat("shots_blocked", 0)

    @property
    def duels_won_pct(self):
        return self._get_latest_stat("duels_won_pct", 0.0)

    @property
    def aerial_duels_won_pct(self):
        return self._get_latest_stat("aerial_duels_won_pct", 0.0)

    @property
    def ground_duels_won_pct(self):
        return self._get_latest_stat("ground_duels_won_pct", 0.0)

    @property
    def pass_accuracy_pct(self):
        return self._get_latest_stat("pass_accuracy_pct", 0.0)

    @property
    def pass_accuracy_opp_half_pct(self):
        return self._get_latest_stat("pass_accuracy_opp_half_pct", 0.0)

    # ── Relazioni ─────────────────────────────────────────────────
    season_stats   = relationship("PlayerSeasonStats", back_populates="player",
                                  cascade="all, delete-orphan")
    matches        = relationship("PlayerMatch",        back_populates="player",
                                  cascade="all, delete-orphan")
    heatmaps       = relationship("PlayerHeatmap",      back_populates="player",
                                  cascade="all, delete-orphan")
    career         = relationship("PlayerCareer",       back_populates="player",
                                  cascade="all, delete-orphan")
    national_stats = relationship("PlayerNationalStats", back_populates="player",
                                  cascade="all, delete-orphan")
    # Questo ti permette di fare: player.club_relation.league_key
    club_relation = relationship("Club", back_populates="players")
    fbref_stats      = relationship("PlayerFbrefStats",    back_populates="player", cascade="all, delete-orphan")
    fbref_match_logs = relationship("PlayerFbrefMatchLog", back_populates="player", cascade="all, delete-orphan")
    scouting_index   = relationship("PlayerScoutingIndex", back_populates="player", uselist=False, cascade="all, delete-orphan")
    sofascore_stats = relationship("PlayerSofascoreStats", back_populates="player", cascade="all, delete-orphan", )

class Club(Base):
    __tablename__ = "clubs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    league_key = Column(String, index=True)
    country = Column(String)

    # Relazione inversa
    players = relationship("ScoutingPlayer", back_populates="club_relation")


# ══════════════════════════════════════════════════════════════════
# PLAYER SEASON STATS
# Una riga per (player_id, season, league, source).
# Raccoglie dati da SofaScore, API-Football, FBref, Understat.
# ══════════════════════════════════════════════════════════════════

class PlayerSeasonStats(Base):
    __tablename__ = "player_season_stats"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    season    = Column(String(10), nullable=False)   # es. "2024-25"
    league    = Column(String(50), nullable=False)   # es. "serie_a"
    source    = Column(String(30), nullable=False)   # "sofascore" | "api_football" | "fbref" | "understat"

    # ── Rating & volume ───────────────────────────────────────────
    sofascore_rating  = Column(Float)
    appearances       = Column(Integer)   # partite giocate (incluse da subentrato)
    matches_started   = Column(Integer)   # titolare
    minutes_played    = Column(Integer)

    # ── Statistiche offensive ─────────────────────────────────────
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

    # ── xG / xA (da Understat / FBref / SofaScore) ───────────────
    xg                = Column(Float)       # expected goals (stagione totale)
    xa                = Column(Float)       # expected assists (stagione totale)
    xg_per90          = Column(Float)
    xa_per90          = Column(Float)
    npxg_per90        = Column(Float)       # non-penalty xG/90 (FBref)
    xgchain_per90     = Column(Float)       # (StatsBomb)
    xgbuildup_per90   = Column(Float)       # (StatsBomb)

    # ── Passaggi ─────────────────────────────────────────────────
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
    pass_to_assist            = Column(Integer)   # passaggi che portano direttamente all'assist
    chipped_passes            = Column(Integer)

    # ── Progressione (FBref) ─────────────────────────────────────
    progressive_passes          = Column(Integer)
    progressive_carries         = Column(Integer)
    progressive_passes_received = Column(Integer)
    touches_att_pen             = Column(Integer)   # tocchi in area avversaria

    # ── Dribbling ─────────────────────────────────────────────────
    successful_dribbles     = Column(Integer)
    dribble_success_pct     = Column(Float)
    dribbled_past           = Column(Integer)   # volte dribblato dall'avversario
    dispossessed            = Column(Integer)   # palla persa con pressione

    # ── Duelli ───────────────────────────────────────────────────
    ground_duels_won        = Column(Integer)
    ground_duels_won_pct    = Column(Float)
    aerial_duels_won        = Column(Integer)
    aerial_duels_lost       = Column(Integer)
    aerial_duels_won_pct    = Column(Float)
    total_duels_won         = Column(Integer)
    total_duels_won_pct     = Column(Float)
    total_contest           = Column(Integer)   # duelli totali SofaScore

    # ── Difesa ───────────────────────────────────────────────────
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

    # ── Pressing (FBref) ─────────────────────────────────────────
    pressures           = Column(Integer)
    pressure_regains    = Column(Integer)

    # ── Possesso ─────────────────────────────────────────────────
    touches             = Column(Integer)
    possession_lost     = Column(Integer)

    # ── Set piece ────────────────────────────────────────────────
    shot_from_set_piece = Column(Integer)

    # ── Disciplina ───────────────────────────────────────────────
    yellow_cards    = Column(Integer)
    yellow_red_cards = Column(Integer)
    red_cards       = Column(Integer)
    fouls_committed = Column(Integer)
    fouls_won       = Column(Integer)   # was_fouled
    offsides        = Column(Integer)
    hit_woodwork    = Column(Integer)

    # ── Portiere ─────────────────────────────────────────────────
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

    # ── Fantacalcio ─────────────────────────────────────────────
    # Dati aggregati di fantacalcio (fonte: esterna, es. Fantacalcio.it)
    fanta_media         = Column(Float)   # media voto
    fanta_media_mv      = Column(Float)   # media modificata
    fanta_gol           = Column(Integer)
    fanta_assist        = Column(Integer)
    fanta_ammonizioni   = Column(Integer)
    fanta_espulsioni    = Column(Integer)
    fanta_rigori_segnati = Column(Integer)
    fanta_rigori_sbagliati = Column(Integer)
    fanta_autogol       = Column(Integer)
    fanta_presenze      = Column(Integer)

    # ── Meta ─────────────────────────────────────────────────────
    tournament_id = Column(Integer, nullable=True)   # id SofaScore tournament
    season_id     = Column(Integer, nullable=True)   # id SofaScore season
    fetched_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="season_stats")

    __table_args__ = (
        UniqueConstraint('player_id', 'season', 'league', 'source',
                         name='uq_player_season_league_source'),
        Index('ix_season_stats_player_season', 'player_id', 'season'),
    )


# ══════════════════════════════════════════════════════════════════
# PLAYER MATCH  — storico partite per giocatore
# ══════════════════════════════════════════════════════════════════

class PlayerMatch(Base):
    __tablename__ = "player_matches"

    id         = Column(Integer, primary_key=True, index=True)
    player_id  = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    event_id   = Column(Integer, nullable=True, index=True)   # id SofaScore event
    date       = Column(DateTime, nullable=True, index=True)  # timestamp Unix → datetime
    season     = Column(String(10), nullable=True)            # es. "2024-25"
    tournament = Column(String(100), nullable=True)           # "Serie A", "UCL", ...

    home_team  = Column(String(100))
    away_team  = Column(String(100))
    home_score = Column(Integer)
    away_score = Column(Integer)

    # Performance individuale nella partita
    rating         = Column(Float)
    minutes_played = Column(Integer)
    goals          = Column(Integer, default=0)
    assists        = Column(Integer, default=0)
    yellow_card    = Column(Integer, default=0)   # 0/1
    red_card       = Column(Integer, default=0)   # 0/1

    source     = Column(String(20), default='sofascore')
    fetched_at = Column(DateTime, default=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="matches")

    __table_args__ = (
        UniqueConstraint('player_id', 'event_id', name='uq_player_event'),
        Index('ix_player_match_player_date', 'player_id', 'date'),
    )


# ══════════════════════════════════════════════════════════════════
# PLAYER HEATMAP  — punti heatmap stagionali
# ══════════════════════════════════════════════════════════════════

class PlayerHeatmap(Base):
    __tablename__ = "player_heatmap"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    season    = Column(String(10), nullable=False)
    league    = Column(String(50), nullable=False)

    # Lista di punti {x: float, y: float} — coordinate normalizzate 0-1
    # Ogni punto rappresenta una posizione sul campo in cui il giocatore
    # ha toccato il pallone durante la stagione.
    points      = Column(JSON, nullable=True)   # [{x: 0.3, y: 0.7}, ...]
    point_count = Column(Integer, default=0)

    position_played = Column(String(20), nullable=True)   # posizione giocata
    source          = Column(String(20), default='sofascore')
    fetched_at      = Column(DateTime, default=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="heatmaps")

    __table_args__ = (
        UniqueConstraint('player_id', 'season', 'league', 'source',
                         name='uq_heatmap_player_season_league'),
    )


# ══════════════════════════════════════════════════════════════════
# PLAYER CAREER  — storico trasferimenti
# ══════════════════════════════════════════════════════════════════

class PlayerCareer(Base):
    __tablename__ = "player_career"

    id        = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                       nullable=False, index=True)

    from_team     = Column(String(100))
    to_team       = Column(String(100))
    transfer_date = Column(DateTime, nullable=True)
    fee           = Column(Float, nullable=True)        # milioni €, nullable se sconosciuta
    transfer_type = Column(String(30), nullable=True)  # "Transfer" | "Loan" | "Free" | "Youth"
    season        = Column(String(10), nullable=True)

    source     = Column(String(20), default='sofascore')
    fetched_at = Column(DateTime, default=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="career")


# ══════════════════════════════════════════════════════════════════
# PLAYER NATIONAL STATS  — statistiche con la nazionale
# ══════════════════════════════════════════════════════════════════

class PlayerNationalStats(Base):
    __tablename__ = "player_national_stats"

    id            = Column(Integer, primary_key=True, index=True)
    player_id     = Column(Integer, ForeignKey("scouting_players.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    national_team = Column(String(100), nullable=True)
    season = Column(String(10), nullable=True)  # es. "2024-25"

    appearances   = Column(Integer)
    minutes       = Column(Integer)
    goals         = Column(Integer)
    assists       = Column(Integer)
    rating        = Column(Float)
    yellow_cards  = Column(Integer)
    red_cards     = Column(Integer)

    # JSON grezzo per eventuali campi aggiuntivi non mappati
    raw_data      = Column(JSON, nullable=True)

    source     = Column(String(20), default='sofascore')
    fetched_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player = relationship("ScoutingPlayer", back_populates="national_stats")

    __table_args__ = (
        # Include season nel constraint: permette di tenere più stagioni per stessa nazionale
        UniqueConstraint('player_id', 'national_team', 'season', 'source',
                         name='uq_national_player_team_season'),
    )