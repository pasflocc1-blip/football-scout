from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from app.models.models import TraitType


# ── TeamTrait ────────────────────────────────────────────────────
class TraitCreate(BaseModel):
    trait_type: TraitType
    description: str
    priority: int = 1


class TraitOut(TraitCreate):
    id: int
    team_id: int

    class Config:
        from_attributes = True


# ── MyTeam ───────────────────────────────────────────────────────
class TeamCreate(BaseModel):
    name: str
    formation: Optional[str] = None
    league: Optional[str] = None
    season: Optional[str] = None
    coach: Optional[str] = None
    budget: Optional[float] = None
    notes: Optional[str] = None


class TeamUpdate(TeamCreate):
    pass


class TeamOut(TeamCreate):
    id: int
    created_at: datetime
    traits: List[TraitOut] = []

    class Config:
        from_attributes = True


# ── MyPlayer ─────────────────────────────────────────────────────
class PlayerCreate(BaseModel):
    name: str
    position: Optional[str] = None
    age: Optional[int] = None
    preferred_foot: Optional[str] = None
    rating: Optional[float] = None


class PlayerOut(PlayerCreate):
    id: int
    team_id: int

    class Config:
        from_attributes = True


# ── ScoutingPlayer ───────────────────────────────────────────────
class ScoutingPlayerOut(BaseModel):
    id: int
    name: str
    position: Optional[str]
    club: Optional[str]
    nationality: Optional[str]
    age: Optional[int]
    preferred_foot: Optional[str]
    pace: Optional[int]
    shooting: Optional[int]
    passing: Optional[int]
    dribbling: Optional[int]
    defending: Optional[int]
    physical: Optional[int]
    heading_score: Optional[float]
    build_up_score: Optional[float]
    defensive_score: Optional[float]
    xg_per90: Optional[float]
    xa_per90: Optional[float]

    class Config:
        from_attributes = True
