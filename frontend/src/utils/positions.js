/**
 * src/utils/positions.js
 * Dizionario centralizzato ruoli calcio — italiano.
 * Importato da PlayerCard, TeamRoster, GlobalScoutingView, ScoutingSearch.
 *
 * Gestisce ENTRAMBI i formati:
 *   - Codici FIFA: "ST", "CM", "CB", "GK", ...
 *   - Categorie API-Football: "Attacker", "Midfielder", "Defender", "Goalkeeper"
 */

export const POSITION_LABELS = {
  // ── Portieri ──────────────────────────────────────────────────
  GK:         'Portiere',
  Goalkeeper: 'Portiere',

  // ── Difensori ─────────────────────────────────────────────────
  CB:       'Difensore Centrale',
  'Centre-Back': 'Difensore centrale',
  LB:       'Terzino Sinistro',
  'Left-Back': 'Terzino Sinistro',
  RB:       'Terzino Destro',
  LWB:      'Quinto Sinistro',
  RWB:      'Quinto Destro',
  SW:       'Libero',
  DF:       'Difensore',
  Defender: 'Difensore',
  Defence: 'Difensore',
  'Right-Back': 'Terzino destro',

  // ── Centrocampisti ────────────────────────────────────────────
  DM:         'Mediano Difensivo',
  CDM:        'Mediano Difensivo',
  CM:         'Centrocampista',
  'Central Midfield': 'Centrocampista',
  AM:         'Trequartista',
  CAM:        'Trequartista',
  LM:         'Mezzala Sinistra',
  RM:         'Mezzala Destra',
  MF:         'Centrocampista',
  Midfielder: 'Centrocampista',

  // ── Attaccanti ────────────────────────────────────────────────
  LW:       'Ala Sinistra',
  'Left Winger': 'Ala sinistra',
  RW:       'Ala Destra',
  SS:       'Seconda Punta',
  CF:       'Prima Punta',
  ST:       'Centravanti',
  'Centre-Forward': 'Centravanti',
  FW:       'Attaccante',
  Attacker: 'Attaccante',

}

/**
 * Restituisce l'etichetta italiana per un codice posizione.
 * Se il codice non è in mappa, ritorna il codice stesso.
 */
export function posLabel(code) {
  if (!code) return '—'
  return POSITION_LABELS[code] ?? code
}

/**
 * Array di opzioni per <select> con codice + descrizione italiana.
 * Include sia i codici FIFA che le categorie API-Football.
 */
export const posOptions = [
  { value: '',         label: 'Tutti i ruoli' },
  // Portiere
  { value: 'GK',       label: 'GK — Portiere' },
  // Difensori
  { value: 'CB',       label: 'CB — Difensore Centrale' },
  { value: 'LB',       label: 'LB — Terzino Sinistro' },
  { value: 'RB',       label: 'RB — Terzino Destro' },
  { value: 'LWB',      label: 'LWB — Quinto Sinistro' },
  { value: 'RWB',      label: 'RWB — Quinto Destro' },
  // Centrocampisti
  { value: 'DM',       label: 'DM — Mediano Difensivo' },
  { value: 'CM',       label: 'CM — Centrocampista' },
  { value: 'AM',       label: 'AM — Trequartista' },
  { value: 'LM',       label: 'LM — Mezzala Sinistra' },
  { value: 'RM',       label: 'RM — Mezzala Destra' },
  // Attaccanti
  { value: 'LW',       label: 'LW — Ala Sinistra' },
  { value: 'RW',       label: 'RW — Ala Destra' },
  { value: 'CF',       label: 'CF — Prima Punta' },
  { value: 'ST',       label: 'ST — Centravanti' },
  { value: 'SS',       label: 'SS — Seconda Punta' },
  // Categorie API-Football (per giocatori importati da API-Football)
  { value: 'Attacker',    label: 'Attaccante (API-Football)' },
  { value: 'Midfielder',  label: 'Centrocampista (API-Football)' },
  { value: 'Defender',    label: 'Difensore (API-Football)' },
  { value: 'Goalkeeper',  label: 'Portiere (API-Football)' },
]