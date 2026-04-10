# MIGRATION GUIDE — Refactoring SofaScore → player_sofascore_stats
# ═══════════════════════════════════════════════════════════════════

## PANORAMICA

Obiettivo: disaccoppiare i dati grezzi (fonti) dai dati elaborati (algoritmo).

| Prima                        | Dopo                                  |
|------------------------------|---------------------------------------|
| scouting_players (tutto)     | scouting_players (solo anagrafica)    |
| player_season_stats (sofas.) | player_sofascore_stats (dedicata)     |
| scoring.py solo SofaScore    | scoring_sofascore.py multi-fonte      |
| Frontend tab unica           | Tab: Scheda / Algoritmo / Fonti       |

---

## 1. NUOVI FILE (già pronti nell'output)

```
app/models/sofascore_models.py        ← nuova tabella PlayerSofascoreStats
app/services/sources/sofascore_source.py  ← riscritta (_upsert_sofascore_stats)
app/routers/scoring_sofascore.py      ← algoritmo multi-fonte
frontend/PlayerDetailView.vue         ← 3 tab: Scheda / Algoritmo / Fonti
```

---

## 2. PATCH app/main.py

Aggiungere dopo `from app.models import fbref_models`:

```python
from app.models import sofascore_models  # noqa — registra player_sofascore_stats
```

Aggiungere nel blocco router:

```python
from app.routers import scoring_sofascore
app.include_router(scoring_sofascore.router)
```

---

## 3. PATCH app/models/models.py — ScoutingPlayer

Aggiungere la relationship mancante (dopo fbref_stats e scouting_index):

```python
sofascore_stats = relationship(
    "PlayerSofascoreStats",
    back_populates="player",
    cascade="all, delete-orphan",
)
```

---

## 4. MIGRAZIONE DB — Alembic (o script diretto)

### Opzione A — Alembic (consigliata in prod)
```bash
alembic revision --autogenerate -m "add_player_sofascore_stats"
alembic upgrade head
```

### Opzione B — Script diretto (dev/Docker)
La tabella viene creata automaticamente al riavvio del backend perché
`Base.metadata.create_all(bind=engine)` è già in main.py e
`sofascore_models` è ora importato.
Basta **riavviare il container**.

### Cosa NON cambia
- `player_season_stats` rimane invariata (dati API-Football, FBref CSV legacy)
- `scouting_players` rimane invariata (non si toccano le colonne esistenti)
- `PlayerScoutingIndex` rimane invariata (ora viene scritta da scoring_sofascore.py)

---

## 5. PATCH app/routers/player_detail_final.py

La funzione `_stats_to_dict` che legge da `PlayerSeasonStats` (SofaScore)
deve puntare alla **nuova** tabella. Sostituire il blocco SofaScore:

```python
# PRIMA (legge da player_season_stats filtrando source='sofascore')
from app.models.models import PlayerSeasonStats
sofascore_stats = (
    db.query(PlayerSeasonStats)
    .filter_by(player_id=player_id, source="sofascore")
    .order_by(PlayerSeasonStats.season.desc())
    .all()
)
# serializzazione con _stats_to_dict

# DOPO (legge dalla nuova tabella dedicata)
from app.models.sofascore_models import PlayerSofascoreStats
sofascore_stats = (
    db.query(PlayerSofascoreStats)
    .filter_by(player_id=player_id)
    .order_by(PlayerSofascoreStats.season.desc())
    .all()
)
# serializzazione con _sofascore_stats_to_dict (vedi sotto)
```

Aggiungere la funzione di serializzazione:

```python
def _sofascore_stats_to_dict(s: PlayerSofascoreStats) -> dict:
    return {
        "source":            "sofascore",
        "season":            s.season,
        "league":            s.league,
        "sofascore_rating":  _fmt(s.sofascore_rating, 2),
        "appearances":       s.appearances,
        "matches_started":   s.matches_started,
        "minutes_played":    s.minutes_played,
        "goals":             s.goals,
        "assists":           s.assists,
        "shots_total":       s.shots_total,
        "shots_on_target":   s.shots_on_target,
        "big_chances_created": s.big_chances_created,
        "xg":                _fmt(s.xg, 2),
        "xa":                _fmt(s.xa, 2),
        "xg_per90":          _fmt(s.xg_per90, 3),
        "xa_per90":          _fmt(s.xa_per90, 3),
        "goal_conversion_pct": _fmt(s.goal_conversion_pct, 1),
        "accurate_passes":   s.accurate_passes,
        "total_passes":      s.total_passes,
        "pass_accuracy_pct": _fmt(s.pass_accuracy_pct, 1),
        "key_passes":        s.key_passes,
        "accurate_crosses":  s.accurate_crosses,
        "accurate_long_balls": s.accurate_long_balls,
        "successful_dribbles": s.successful_dribbles,
        "dribble_success_pct": _fmt(s.dribble_success_pct, 1),
        "aerial_duels_won":  s.aerial_duels_won,
        "aerial_duels_won_pct": _fmt(s.aerial_duels_won_pct, 1),
        "total_duels_won_pct": _fmt(s.total_duels_won_pct, 1),
        "tackles":           s.tackles,
        "tackles_won_pct":   _fmt(s.tackles_won_pct, 1),
        "interceptions":     s.interceptions,
        "clearances":        s.clearances,
        "ball_recovery":     s.ball_recovery,
        "yellow_cards":      s.yellow_cards,
        "red_cards":         s.red_cards,
        "fouls_committed":   s.fouls_committed,
        "fouls_won":         s.fouls_won,
        "saves":             s.saves,
        "goals_conceded":    s.goals_conceded,
        "clean_sheets":      s.clean_sheets,
    }
```

E nella risposta dell'endpoint:

```python
sources = {
    "fbref": {
        "stats":      [_fbref_stats_to_dict(s) for s in fbref_stats_rows],
        "match_logs": [_fbref_log_to_dict(m) for m in fbref_match_logs],
    },
    "sofascore": {
        "stats":   [_sofascore_stats_to_dict(s) for s in sofascore_stats],
        "matches": [_match_to_dict(m) for m in sofa_matches],
    },
}
```

---

## 6. FLUSSO OPERATIVO DOPO LA MIGRAZIONE

```
1. Import FBref CSV      → player_fbref_stats
2. Import SofaScore RPA  → player_sofascore_stats  (NON più scouting_players)
3. POST /scoring/run     → legge entrambe le tabelle, scrive PlayerScoutingIndex
4. Frontend              → Tab Scheda (SofaScore raw) / Algoritmo (indici) / Fonti (tutto)
```

---

## 7. COMPATIBILITÀ CON IL VECCHIO SOFASCORE RPA (router/sofascore.py)

Il router `app/routers/sofascore.py` (RPA v8, endpoint `/sofascore/ocr`)
usa ancora `_upsert_season_stats_v8()` che scrive su `player_season_stats`.

**Opzione rapida (compatibilità)**: lasciare il vecchio router com'è e
aggiungere in `_upsert_season_stats_v8()` una chiamata parallela a
`_upsert_sofascore_stats()` della nuova tabella.

**Opzione definitiva**: aggiornare il router RPA per scrivere direttamente
su `player_sofascore_stats` tramite la funzione già presente in
`sofascore_source.py`.

---

## 8. CHECKLIST

- [ ] Copiare i 4 file dall'output nelle posizioni corrette
- [ ] Patch main.py (2 righe)
- [ ] Patch models.py (1 relationship)
- [ ] Riavviare il backend (crea la tabella automaticamente)
- [ ] Eseguire import SofaScore per popolare player_sofascore_stats
- [ ] POST /scoring/run per calcolare gli indici
- [ ] Verificare tab Algoritmo nel frontend