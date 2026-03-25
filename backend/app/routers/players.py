from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import MyPlayer
from app.schemas.schemas import PlayerCreate, PlayerOut

router = APIRouter(prefix="/teams", tags=["Rosa"])


@router.post("/{team_id}/players", response_model=PlayerOut, status_code=201)
def add_player(team_id: int, player: PlayerCreate, db: Session = Depends(get_db)):
    db_player = MyPlayer(team_id=team_id, **player.model_dump())
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player


@router.get("/{team_id}/players", response_model=list[PlayerOut])
def list_players(team_id: int, db: Session = Depends(get_db)):
    return db.query(MyPlayer).filter(MyPlayer.team_id == team_id).all()


@router.delete("/{team_id}/players/{player_id}", status_code=204)
def remove_player(team_id: int, player_id: int, db: Session = Depends(get_db)):
    player = db.query(MyPlayer).filter(
        MyPlayer.id == player_id,
        MyPlayer.team_id == team_id
    ).first()
    if not player:
        raise HTTPException(status_code=404, detail="Giocatore non trovato")
    db.delete(player)
    db.commit()
