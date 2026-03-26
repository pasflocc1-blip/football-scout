from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class TraitType(str, enum.Enum):
    positive = "positive"
    negative = "negative"


class MyTeam(Base):
    __tablename__ = "my_team"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    formation = Column(String(20))            # es. "4-3-3"
    league = Column(String(100))
    season = Column(String(20))              # es. "2024/2025"
    coach = Column(String(100))
    budget = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    traits = relationship("TeamTrait", back_populates="team", cascade="all, delete")
    players = relationship("MyPlayer", back_populates="team", cascade="all, delete")


class TeamTrait(Base):
    __tablename__ = "team_traits"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("my_team.id", ondelete="CASCADE"), nullable=False)
    trait_type = Column(Enum(TraitType), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(Integer, default=1)

    team = relationship("MyTeam", back_populates="traits")


class MyPlayer(Base):
    __tablename__ = "my_players"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("my_team.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False)
    position = Column(String(20))
    age = Column(Integer)
    preferred_foot = Column(String(10))
    rating = Column(Float)

    team = relationship("MyTeam", back_populates="players")


class ScoutingPlayer(Base):
    __tablename__ = "scouting_players"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(50), unique=True, index=True)
    fbref_id = Column(String(50), unique=True, index=True, nullable=True)
    name = Column(String(100), nullable=False)
    position = Column(String(20))
    club = Column(String(100))
    nationality = Column(String(50))
    age = Column(Integer)
    preferred_foot = Column(String(10))

    # Stats base (stile FIFA/FBref)
    pace = Column(Integer)
    shooting = Column(Integer)
    passing = Column(Integer)
    dribbling = Column(Integer)
    defending = Column(Integer)
    physical = Column(Integer)

    # Stats avanzate (da StatsBomb / API-Football)
    xg_per90 = Column(Float)
    xa_per90 = Column(Float)
    progressive_passes = Column(Integer)
    aerial_duels_won_pct = Column(Float)

    # Scores calcolati dalla nostra logica
    heading_score = Column(Float)
    build_up_score = Column(Float)
    defensive_score = Column(Float)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
