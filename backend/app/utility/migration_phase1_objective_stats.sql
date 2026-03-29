-- ================================================================
-- migration_phase1_objective_stats.sql
-- ================================================================
-- Fase 1 del pipeline di scouting oggettivo.
-- Aggiunge tutte le colonne di statistiche raw necessarie per
-- calcolare gli score oggettivi nelle fasi successive.
--
-- Applicazione:
--   docker exec -i football_db psql -U football -d football_scout \
--     < migration_phase1_objective_stats.sql
--
-- Sicuro da rieseguire: tutte le colonne usano IF NOT EXISTS.
-- ================================================================

-- ── 1. IDENTIFICATORI ESTERNI ────────────────────────────────────
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS understat_id VARCHAR(20) UNIQUE;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS sofascore_id VARCHAR(20) UNIQUE;

-- ── 2. STATISTICHE OFFENSIVE ─────────────────────────────────────
-- Valori assoluti stagione corrente
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS goals_season       INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS assists_season      INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS minutes_season      INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS games_season        INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS shots_season        INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS shots_on_target_season INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS key_passes_season   INTEGER;

-- xG / xA avanzati (Understat + StatsBomb)
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS npxg_per90          DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS xgchain_per90       DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS xgbuildup_per90     DOUBLE PRECISION;

-- ── 3. STATISTICHE DI PROGRESSIONE ──────────────────────────────
-- FBref: azioni che spostano il pallone verso la porta avversaria
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS progressive_carries  INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS progressive_passes_received INTEGER;
-- Nota: progressive_passes esiste già nel modello originale

-- ── 4. STATISTICHE DIFENSIVE ─────────────────────────────────────
-- FBref: pressing e contrasti
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS pressures_season     INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS pressure_regains_season INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS tackles_season        INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS interceptions_season  INTEGER;

-- API-Football: duelli (sostituisce aerial_duels_won_pct generico)
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS duels_total_season   INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS duels_won_season     INTEGER;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS duels_won_pct        DOUBLE PRECISION;
-- aerial_duels_won_pct esiste già

-- ── 5. PASSAGGI ──────────────────────────────────────────────────
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS pass_accuracy_pct   DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS touches_att_pen_season INTEGER;

-- ── 6. TIMESTAMP PER SORGENTE ────────────────────────────────────
-- Permette di sapere quale sorgente ha aggiornato ogni campo e quando
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS last_updated_understat    TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS last_updated_fbref        TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS last_updated_api_football TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS last_updated_statsbomb    TIMESTAMP WITHOUT TIME ZONE;

-- ── 7. SCORE OGGETTIVI (placeholder per Fase 3) ──────────────────
-- Creati ora vuoti, verranno popolati da recalculate_objective_scores()
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS finishing_score     DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS creativity_score    DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS pressing_score      DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS carrying_score      DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS defending_obj_score DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS buildup_obj_score   DOUBLE PRECISION;

-- Score come percentile per ruolo (Fase 4)
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS finishing_pct       DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS creativity_pct      DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS pressing_pct        DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS carrying_pct        DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS defending_pct       DOUBLE PRECISION;
ALTER TABLE scouting_players ADD COLUMN IF NOT EXISTS buildup_pct         DOUBLE PRECISION;

-- ── 8. INDICI ─────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sp_understat_id
    ON scouting_players (understat_id) WHERE understat_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sp_minutes
    ON scouting_players (minutes_season) WHERE minutes_season IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sp_finishing
    ON scouting_players (finishing_pct) WHERE finishing_pct IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sp_position
    ON scouting_players (position) WHERE position IS NOT NULL;

-- ── 9. COMMENTI ──────────────────────────────────────────────────
COMMENT ON COLUMN scouting_players.npxg_per90 IS
    'Non-penalty expected goals per 90. Fonte: Understat/FBref.';
COMMENT ON COLUMN scouting_players.xgchain_per90 IS
    'xG generato da ogni azione in cui il giocatore tocca la palla. Fonte: StatsBomb.';
COMMENT ON COLUMN scouting_players.xgbuildup_per90 IS
    'xG generato dal build-up (esclude il tocco finale). Fonte: StatsBomb.';
COMMENT ON COLUMN scouting_players.finishing_score IS
    'Score 0-100 calcolato da npxG/90 + conversione. Sostituisce shooting FIFA.';
COMMENT ON COLUMN scouting_players.finishing_pct IS
    'Percentile finishing_score tra giocatori dello stesso ruolo.';

-- ── 10. VERIFICA RAPIDA ──────────────────────────────────────────
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'scouting_players'
  AND column_name IN (
      'goals_season','assists_season','minutes_season',
      'npxg_per90','xgchain_per90','xgbuildup_per90',
      'pressures_season','progressive_carries',
      'finishing_score','finishing_pct',
      'understat_id','last_updated_understat'
  )
ORDER BY column_name;