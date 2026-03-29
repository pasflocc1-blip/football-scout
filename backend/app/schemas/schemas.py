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

    # Statistiche avanzate per 90 min (sempre presenti se dati disponibili)
    xg_per90:       Optional[float]
    xa_per90:       Optional[float]
    npxg_per90:     Optional[float]
    xgchain_per90:  Optional[float]
    xgbuildup_per90:Optional[float]

    # Score oggettivi Fase 3 (0-100)
    finishing_score:     Optional[float]
    creativity_score:    Optional[float]
    pressing_score:      Optional[float]
    carrying_score:      Optional[float]
    defending_obj_score: Optional[float]
    buildup_obj_score:   Optional[float]

    # Score legacy — mantenuti per compatibilità con PlayerCard.vue
    heading_score:   Optional[float]
    build_up_score:  Optional[float]
    defensive_score: Optional[float]

    # Dati stagionali (utili per la UI)
    minutes_season:  Optional[int]
    goals_season:    Optional[int]
    assists_season:  Optional[int]

    # % duelli (visibili in scheda)
    aerial_duels_won_pct: Optional[float]
    duels_won_pct:        Optional[float]

    class Config:
        from_attributes = True