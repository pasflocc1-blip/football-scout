-- ============================================================
-- migration_add_external_ids_and_stats.sql
-- ============================================================
-- Estende scouting_players con:
--   • ID esterni (understat_id, sofascore_id) per match deterministico
--   • Statistiche stagionali assolute (goal, assist, minuti, tiri)
--   • npxg_per90 (non-penalty expected goals)
--   • Metadati di aggiornamento per sorgente
--
-- Applicazione:
--   docker exec -i <postgres_container> psql -U football -d football < migration_add_external_ids_and_stats.sql
--
-- Sicuro da rieseguire: usa ADD COLUMN IF NOT EXISTS.
-- ============================================================

-- ── 1. ID ESTERNI ────────────────────────────────────────────────
-- understat_id: ID numerico di understat.com (stringa perché
--   alcune librerie lo restituiscono come string)
ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS understat_id VARCHAR(20) UNIQUE;

-- sofascore_id: utile se in futuro integri SofaScore
ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS sofascore_id VARCHAR(20) UNIQUE;

-- ── 2. STATISTICHE AVANZATE PER90 ────────────────────────────────
-- npxg_per90: non-penalty expected goals per 90 minuti
--   (più preciso di xg_per90 per i centravanti che tirano rigori)
ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS npxg_per90 DOUBLE PRECISION;

-- ── 3. STATISTICHE ASSOLUTE STAGIONE CORRENTE ────────────────────
-- Utili per filtri scouting ("almeno 10 gol stagione")
-- e per calcolare per90 in frontend senza ricalcolo backend.
ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS goals_season   INTEGER;

ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS assists_season INTEGER;

ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS minutes_season INTEGER;

ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS shots_season   INTEGER;

ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS games_season   INTEGER;

-- ── 4. METADATI AGGIORNAMENTO PER SORGENTE ───────────────────────
-- Permette di sapere quando ogni sorgente ha aggiornato il record
-- e di decidere quale valore di xG/xA è "più fresco".
ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS last_updated_understat  TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS last_updated_fbref       TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS last_updated_api_football TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE public.scouting_players
    ADD COLUMN IF NOT EXISTS last_updated_statsbomb   TIMESTAMP WITHOUT TIME ZONE;

-- ── 5. INDICI ────────────────────────────────────────────────────
-- Velocizza le lookup per understat_id (usato da _find_by_understat_id)
CREATE INDEX IF NOT EXISTS idx_scouting_players_understat_id
    ON public.scouting_players (understat_id)
    WHERE understat_id IS NOT NULL;

-- Indice su club + name: usato dal fuzzy matcher (già funziona,
-- ma l'indice rende la query iniziale più rapida su dataset grandi)
CREATE INDEX IF NOT EXISTS idx_scouting_players_club
    ON public.scouting_players (club)
    WHERE club IS NOT NULL;

-- ── 6. COMMENTI SULLE COLONNE ────────────────────────────────────
COMMENT ON COLUMN public.scouting_players.understat_id IS
    'ID numerico understat.com. Match deterministico per fetch futuri.';

COMMENT ON COLUMN public.scouting_players.npxg_per90 IS
    'Non-penalty xG per 90 minuti. Fonte: Understat.';

COMMENT ON COLUMN public.scouting_players.goals_season IS
    'Goal segnati nella stagione corrente (valore assoluto).';

COMMENT ON COLUMN public.scouting_players.assists_season IS
    'Assist nella stagione corrente (valore assoluto).';

COMMENT ON COLUMN public.scouting_players.minutes_season IS
    'Minuti giocati nella stagione corrente.';

COMMENT ON COLUMN public.scouting_players.last_updated_understat IS
    'Timestamp ultimo aggiornamento dati da Understat.';

-- ── 7. AGGIORNA init.sql (dati di esempio) ───────────────────────
-- Aggiunge valori plausibili ai 4 giocatori di esempio già inseriti.
UPDATE public.scouting_players SET
    npxg_per90      = 0.48,
    goals_season    = 12,
    assists_season  = 3,
    minutes_season  = 1980,
    shots_season    = 62,
    games_season    = 22
WHERE api_football_id = 1001;  -- Marco Testa, ST

UPDATE public.scouting_players SET
    npxg_per90      = 0.08,
    goals_season    = 4,
    assists_season  = 9,
    minutes_season  = 2340,
    shots_season    = 18,
    games_season    = 26
WHERE api_football_id = 1002;  -- Luca Passatore, CM

UPDATE public.scouting_players SET
    npxg_per90      = 0.29,
    goals_season    = 7,
    assists_season  = 8,
    minutes_season  = 1710,
    shots_season    = 44,
    games_season    = 19
WHERE api_football_id = 1003;  -- Marco Volante, LW

UPDATE public.scouting_players SET
    npxg_per90      = 0.03,
    goals_season    = 1,
    assists_season  = 1,
    minutes_season  = 2520,
    shots_season    = 8,
    games_season    = 28
WHERE api_football_id = 1004;  -- Andrea Muro, CB