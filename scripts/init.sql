-- Script eseguito automaticamente al primo avvio del container PostgreSQL
-- Inserisce dati di esempio per poter testare subito l'applicazione

-- Inserisce una squadra di esempio
INSERT INTO my_team (name, formation, league, season, coach, notes)
VALUES ('FC Demo', '4-3-3', 'Serie A', '2024/2025', 'Mario Rossi',
        'Squadra di test per sviluppo')
ON CONFLICT DO NOTHING;

-- Inserisce caratteristiche di esempio
INSERT INTO team_traits (team_id, trait_type, description, priority)
VALUES
  (1, 'positive', 'Ottima organizzazione difensiva', 1),
  (1, 'positive', 'Buona velocità sulle fasce', 2),
  (1, 'negative', 'Scarsa efficacia di testa su calcio da fermo', 1),
  (1, 'negative', 'Mancanza di un centravanti fisico', 2)
ON CONFLICT DO NOTHING;

-- Inserisce giocatori di scouting di esempio
INSERT INTO scouting_players (
    external_id, name, position, club, nationality, age, preferred_foot,
    pace, shooting, passing, dribbling, defending, physical,
    xg_per90, xa_per90, aerial_duels_won_pct,
    heading_score, build_up_score, defensive_score
) VALUES
  ('EX001', 'Marco Testa', 'ST', 'AC Esempio', 'Italiana', 27, 'Right',
   72, 80, 65, 70, 40, 85, 0.55, 0.12, 68.0, 82.0, 65.0, 38.0),
  ('EX002', 'Luca Passatore', 'CM', 'FC Test', 'Italiana', 24, 'Left',
   68, 60, 88, 82, 65, 72, 0.15, 0.45, 30.0, 45.0, 80.0, 62.0),
  ('EX003', 'Marco Volante', 'LW', 'SC Veloce', 'Italiana', 22, 'Left',
   92, 75, 78, 88, 42, 70, 0.35, 0.40, 25.0, 38.0, 76.0, 40.0),
  ('EX004', 'Andrea Muro', 'CB', 'US Difesa', 'Italiana', 30, 'Right',
   55, 40, 68, 50, 88, 84, 0.05, 0.05, 75.0, 78.0, 55.0, 88.0)
ON CONFLICT (external_id) DO NOTHING;
