-- ════════════════════════════════════════════════════════════════
-- FIX_POSITIONS.sql
-- Normalizza le posizioni in formato esteso verso codici standard
-- ════════════════════════════════════════════════════════════════
-- Problema rilevato: il DB contiene posizioni come:
--   "Centre-Forward", "Defensive Midfield", "Central Midfield",
--   "Defence", "Midfield", "Left-Back", "Left Winger", ecc.
-- invece dei codici standard: ST, DM, CM, CB, LB, LW, ecc.
--
-- Questo causa il bug della ricerca semantica: "scarsa in difesa"
-- cerca position IN ('CB','LB','RB') ma i record hanno "Defence" o "Left-Back"
--
-- Esegui questo script dal DB Explorer prima di fare altre ricerche.
-- ────────────────────────────────────────────────────────────────

-- 1. Verifica la distribuzione attuale delle posizioni
SELECT position, COUNT(*) AS n
FROM scouting_players
GROUP BY position
ORDER BY n DESC;

-- 2. Normalizzazione (esegui UPDATE per aggiornare tutti i record)

-- Portieri
UPDATE scouting_players SET position = 'GK' WHERE position IN ('Goalkeeper','goalkeeper','GK','Portiere');

-- Difensori centrali
UPDATE scouting_players SET position = 'CB'
WHERE position IN ('Centre-Back','Centre Back','Center Back','CB','Central Defender',
                   'Defender','Defence','DF','Difensore','Difensore Centrale','Difensori');

-- Terzino sinistro
UPDATE scouting_players SET position = 'LB'
WHERE position IN ('Left-Back','Left Back','LB','Terzino Sinistro');

-- Terzino destro
UPDATE scouting_players SET position = 'RB'
WHERE position IN ('Right-Back','Right Back','RB','Terzino Destro');

-- Quinto sinistro
UPDATE scouting_players SET position = 'LWB'
WHERE position IN ('Left Wing-Back','Left Wingback','LWB');

-- Quinto destro
UPDATE scouting_players SET position = 'RWB'
WHERE position IN ('Right Wing-Back','Right Wingback','RWB');

-- Mediano difensivo
UPDATE scouting_players SET position = 'DM'
WHERE position IN ('Defensive Midfield','Defensive Midfielder','Holding Midfield','DM','CDM',
                   'Mediano Difensivo','Mediano');

-- Centrocampista centrale
UPDATE scouting_players SET position = 'CM'
WHERE position IN ('Central Midfield','Central Midfielder','Midfielder','MF','CM',
                   'Midfield','Centrocampista');

-- Trequartista
UPDATE scouting_players SET position = 'AM'
WHERE position IN ('Attacking Midfield','Attacking Midfielder','Trequartista','AM','CAM');

-- Mezzala sinistra
UPDATE scouting_players SET position = 'LM'
WHERE position IN ('Left Midfield','Left Midfielder','LM','Mezzala Sinistra');

-- Mezzala destra
UPDATE scouting_players SET position = 'RM'
WHERE position IN ('Right Midfield','Right Midfielder','RM','Mezzala Destra');

-- Ala sinistra
UPDATE scouting_players SET position = 'LW'
WHERE position IN ('Left Winger','Left Wing','LW','Ala Sinistra');

-- Ala destra
UPDATE scouting_players SET position = 'RW'
WHERE position IN ('Right Winger','Right Wing','RW','Ala Destra');

-- Seconda punta
UPDATE scouting_players SET position = 'SS'
WHERE position IN ('Second Striker','Seconda Punta','SS');

-- Centravanti / Prima Punta
UPDATE scouting_players SET position = 'ST'
WHERE position IN ('Centre-Forward','Center-Forward','Centre Forward','Center Forward',
                   'Striker','Attacker','Forward','FW','ST','CF','Centravanti',
                   'Prima Punta','Attaccante');

-- Generici che mappano a posizioni approssimate
UPDATE scouting_players SET position = 'CM'
WHERE position IN ('Midfield') AND position != 'CM';

UPDATE scouting_players SET position = 'CB'
WHERE position IN ('Defender','Defence') AND position != 'CB';

UPDATE scouting_players SET position = 'ST'
WHERE position IN ('Attacker','Forward') AND position != 'ST';

-- 3. Verifica il risultato
SELECT position, COUNT(*) AS n
FROM scouting_players
GROUP BY position
ORDER BY n DESC;