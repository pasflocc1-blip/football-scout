from .models import Base, ScoutingPlayer, PlayerNationalStats, PlayerCareer, PlayerMatch, PlayerHeatmap
from .fbref_models import PlayerFbrefStats, PlayerFbrefMatchLog, PlayerScoutingIndex
from .sofascore_models import PlayerSofascoreStats

# Questo rende tutte le classi visibili a SQLAlchemy nello stesso momento
__all__ = [
    "Base",
    "ScoutingPlayer",
    "PlayerNationalStats",
    "PlayerCareer",
    "PlayerMatch",
    "PlayerHeatmap",
    "PlayerFbrefStats",
    "PlayerFbrefMatchLog",
    "PlayerScoutingIndex",
    "PlayerSofascoreStats"
]