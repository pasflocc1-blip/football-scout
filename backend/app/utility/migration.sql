-- ════════════════════════════════════════════════════════════════
-- FIX_4_migration.sql
-- Rimozione colonne FIFA soggettive dalla tabella scouting_players
-- ════════════════════════════════════════════════════════════════
--
-- Esegui nel container con:
--   docker compose exec db psql -U football -d football_scout -f /path/to/migration.sql
-- oppure dal DB Explorer incollando le istruzioni una per volta.
--
-- ATTENZIONE: questa operazione è IRREVERSIBILE.
-- Fai un backup prima: docker compose exec db pg_dump -U football football_scout > backup.sql
-- ────────────────────────────────────────────────────────────────

-- 1. Verifica che le colonne esistano prima di rimuoverle
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'scouting_players'
  AND column_name IN ('pace', 'shooting', 'passing', 'dribbling', 'defending', 'physical')
ORDER BY column_name;

-- 2. Rimozione colonne FIFA (esegui solo se il SELECT sopra le trova)
ALTER TABLE scouting_players DROP COLUMN IF EXISTS pace;
ALTER TABLE scouting_players DROP COLUMN IF EXISTS shooting;
ALTER TABLE scouting_players DROP COLUMN IF EXISTS passing;
ALTER TABLE scouting_players DROP COLUMN IF EXISTS dribbling;
ALTER TABLE scouting_players DROP COLUMN IF EXISTS defending;
ALTER TABLE scouting_players DROP COLUMN IF EXISTS physical;

-- 3. Verifica finale: le colonne FIFA non devono più essere presenti
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'scouting_players'
  AND column_name IN ('pace', 'shooting', 'passing', 'dribbling', 'defending', 'physical');
-- → Deve ritornare 0 righe

-- 4. Conferma che i campi oggettivi sono presenti
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'scouting_players'
  AND column_name IN (
    'finishing_score', 'creativity_score', 'pressing_score',
    'carrying_score', 'defending_obj_score', 'buildup_obj_score',
    'finishing_pct', 'creativity_pct', 'pressing_pct',
    'carrying_pct', 'defending_pct', 'buildup_pct'
  )
ORDER BY column_name;
-- → Deve ritornare 12 righe