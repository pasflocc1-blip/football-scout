from app.database import SessionLocal
from app.services.scoring import _merge_season_rows, normalize_per90
from app.models.models import ScoutingPlayer, PlayerSeasonStats

db = SessionLocal()
p = db.query(ScoutingPlayer).filter(ScoutingPlayer.name.ilike('%gatti%')).first()

rows = db.query(PlayerSeasonStats).filter(PlayerSeasonStats.player_id == p.id).all()
print('Tutte le righe:')
for r in rows:
    print('  source=%s season=%s league=%s min=%s pressures=%s ball_recovery=%s' % (r.source, r.season, r.league, r.minutes_played, r.pressures, r.ball_recovery))

print()
merged = _merge_season_rows(p)
print('merged pressures:', merged.get('pressures'))
print('merged pressure_regains:', merged.get('pressure_regains'))

v = normalize_per90(p)
print('pressures_p90:', v.get('pressures_p90'))
print('regains_p90:', v.get('regains_p90'))
db.close()
