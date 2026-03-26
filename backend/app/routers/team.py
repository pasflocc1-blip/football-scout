from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import MyTeam, TeamTrait
from app.schemas.schemas import TeamCreate, TeamOut, TeamUpdate, TraitCreate, TraitOut

router = APIRouter(prefix="/teams", tags=["Squadra"], redirect_slashes=False)


@router.post("/", response_model=TeamOut, status_code=201)
def create_team(team: TeamCreate, db: Session = Depends(get_db)):
    db_team = MyTeam(**team.model_dump())
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team


@router.get("/", response_model=list[TeamOut])
def list_teams(db: Session = Depends(get_db)):
    return db.query(MyTeam).all()


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(MyTeam).filter(MyTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Squadra non trovata")
    return team


@router.put("/{team_id}", response_model=TeamOut)
def update_team(team_id: int, data: TeamUpdate, db: Session = Depends(get_db)):
    team = db.query(MyTeam).filter(MyTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Squadra non trovata")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(team, key, val)
    db.commit()
    db.refresh(team)
    return team


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(MyTeam).filter(MyTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Squadra non trovata")
    db.delete(team)
    db.commit()


# ── Traits (caratteristiche positive / negative) ─────────────────

@router.post("/{team_id}/traits", response_model=TraitOut, status_code=201)
def add_trait(team_id: int, trait: TraitCreate, db: Session = Depends(get_db)):
    team = db.query(MyTeam).filter(MyTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Squadra non trovata")
    db_trait = TeamTrait(team_id=team_id, **trait.model_dump())
    db.add(db_trait)
    db.commit()
    db.refresh(db_trait)
    return db_trait


@router.delete("/{team_id}/traits/{trait_id}", status_code=204)
def delete_trait(team_id: int, trait_id: int, db: Session = Depends(get_db)):
    trait = db.query(TeamTrait).filter(
        TeamTrait.id == trait_id,
        TeamTrait.team_id == team_id
    ).first()
    if not trait:
        raise HTTPException(status_code=404, detail="Caratteristica non trovata")
    db.delete(trait)
    db.commit()