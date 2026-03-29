-- ================================================================
-- dedup_and_timezone.sql
-- ================================================================
-- 1. Rimuove i duplicati da scouting_players mantenendo il record
--    più completo (quello con più campi non-null)
-- 2. Imposta il timezone di PostgreSQL su Europe/Rome
-- ================================================================

-- ── PARTE 1: DIAGNOSI DUPLICATI ──────────────────────────────────
-- Mostra quanti duplicati ci sono e quale record mantenere
SELECT
    name,
    COUNT(*) as n_duplicati,
    array_agg(id ORDER BY
        -- Priorità: record con più dati = score più alto
        (CASE WHEN minutes_season IS NOT NULL THEN 3 ELSE 0 END +
         CASE WHEN xg_per90      IS NOT NULL THEN 2 ELSE 0 END +
         CASE WHEN club          IS NOT NULL THEN 1 ELSE 0 END)
        DESC
    ) as ids_in_priority_order
FROM scouting_players
GROUP BY name
HAVING COUNT(*) > 1
ORDER BY name;

-- ── PARTE 2: RIMOZIONE DUPLICATI ─────────────────────────────────
-- Strategia: per ogni gruppo di duplicati, mantieni l'id più basso
-- tra quelli con il massimo score di completezza (più dati non-null).
-- Gli altri vengono eliminati.

BEGIN;

-- Crea tabella temporanea con gli id DA ELIMINARE
CREATE TEMP TABLE _ids_to_delete AS
SELECT id
FROM (
    SELECT
        id,
        name,
        ROW_NUMBER() OVER (
            PARTITION BY name
            ORDER BY
                -- Mantieni prima il record con più dati
                (CASE WHEN minutes_season IS NOT NULL THEN 8 ELSE 0 END +
                 CASE WHEN xg_per90       IS NOT NULL THEN 4 ELSE 0 END +
                 CASE WHEN npxg_per90     IS NOT NULL THEN 2 ELSE 0 END +
                 CASE WHEN club           IS NOT NULL THEN 2 ELSE 0 END +
                 CASE WHEN birth_date     IS NOT NULL THEN 1 ELSE 0 END)
                DESC,
                -- In caso di parità, mantieni l'id più basso (il più vecchio)
                id ASC
        ) AS rn
    FROM scouting_players
) ranked
WHERE rn > 1;

-- Mostra cosa verrà eliminato
SELECT sp.id, sp.name, sp.club, sp.minutes_season, sp.xg_per90
FROM scouting_players sp
JOIN _ids_to_delete d ON sp.id = d.id
ORDER BY sp.name;

-- Esegui la cancellazione
DELETE FROM scouting_players
WHERE id IN (SELECT id FROM _ids_to_delete);

-- Report finale
SELECT 'Eliminati: ' || COUNT(*) || ' duplicati' as risultato
FROM _ids_to_delete;

COMMIT;

-- Verifica che non ci siano più duplicati
SELECT name, COUNT(*) as n
FROM scouting_players
GROUP BY name
HAVING COUNT(*) > 1;

-- ── PARTE 3: TIMEZONE ────────────────────────────────────────────
-- Imposta il timezone dell'utente PostgreSQL su Europe/Rome
-- (UTC+1 in inverno, UTC+2 in estate — DST automatico)

ALTER ROLE football SET timezone = 'Europe/Rome';

-- Per la sessione corrente (effetto immediato senza riavvio)
SET timezone = 'Europe/Rome';

-- Verifica
SELECT
    NOW()                          AS ora_corrente,
    NOW() AT TIME ZONE 'UTC'       AS ora_utc,
    current_setting('timezone')    AS timezone_attivo;

-- ── NOTA per docker-compose ──────────────────────────────────────
-- Aggiungere questa variabile al servizio db in docker-compose.yml:
--   PGTZ: Europe/Rome
-- Oppure al servizio backend:
--   TZ: Europe/Rome
-- Questo garantisce che il timezone persista dopo il riavvio del container.