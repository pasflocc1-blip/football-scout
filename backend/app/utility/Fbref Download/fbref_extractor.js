/**
 * fbref_extractor.js
 * ==================
 * Bookmarklet avanzato per estrarre TUTTE le tabelle statistiche
 * da una pagina FBref e scaricarle come file CSV.
 *
 * UTILIZZO:
 *   Opzione A — Bookmarklet (più comodo):
 *     1. Crea un nuovo preferito nel browser
 *     2. Come URL incolla tutto il contenuto di questo file
 *        preceduto da "javascript:" (vedi sezione BOOKMARKLET sotto)
 *     3. Vai sulla pagina FBref che ti interessa
 *     4. Clicca il preferito
 *     5. Il CSV viene scaricato automaticamente
 *
 *   Opzione B — Console del browser:
 *     1. Vai sulla pagina FBref
 *     2. Apri DevTools (F12) → Console
 *     3. Incolla e premi Invio
 *
 * TABELLE ESTRATTE (in ordine di priorità):
 *   - stats_standard   → xG, xA, gol, assist, minuti
 *   - stats_shooting   → tiri, tiri in porta
 *   - stats_passing    → passaggi chiave, passaggi progressivi
 *   - stats_defense    → tackle, pressioni
 *   - stats_possession → conduzioni progressive, tocchi area
 *
 * OUTPUT:
 *   Un file per ogni tabella trovata, scaricato automaticamente.
 *   Nome file: fbref_{tabella}_{lega}_{stagione}.csv
 */

(function() {
  'use strict';

  // ── Configurazione ──────────────────────────────────────────────
  const TARGET_TABLES = [
	'stats_standard',     // Per il link /stats/
	'stats_keeper',       // AGGIUNTO: Per il link /keepers/
	'stats_shooting',     // Per il link /shooting/
	'stats_playing_time', // AGGIUNTO: Per il link /playingtime/
	'stats_passing_types',
	'stats_misc',         // Per il link /misc/
	'stats_passing',
	'stats_defense',
	'stats_possession'
  ];

  // ── Estrai info pagina dall'URL ─────────────────────────────────
  function getPageInfo() {
    const url   = window.location.href;
    const parts = url.split('/');
    // URL tipo: /en/comps/11/2024-2025/stats/2024-2025-Serie-A-Stats
    const season = parts.find(p => /^\d{4}-\d{4}$/.test(p)) || 'unknown';
    const slug   = (parts[parts.length - 1] || '').replace('-Stats', '');
    return { season, slug, url };
  }

  // ── Trova tabella (incluse quelle in commenti HTML) ─────────────
  function findTable(tableId) {
    let table = document.getElementById(tableId);
    if (table) return table;

    // FBref spesso nasconde le tabelle dentro commenti HTML
    const allNodes = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_COMMENT,
      null
    );
    let node;
    while ((node = allNodes.nextNode())) {
      const tmp = document.createElement('div');
      tmp.innerHTML = node.nodeValue;
      const found = tmp.getElementById(tableId);
      if (found) return found;
    }
    return null;
  }

  // ── Converti tabella HTML in CSV ─────────────────────────────────
  function tableToCSV(table) {
    const rows = Array.from(table.querySelectorAll('tr'));

    // Salta righe di intestazione duplicate (classe "thead")
    // e righe sommario (classe "over_header")
    const dataRows = rows.filter(row => {
      const classes = row.className || '';
      return !classes.includes('over_header') &&
             !classes.includes('spacer');
    });

    const csvLines = dataRows.map(row => {
      const cells = Array.from(row.querySelectorAll('th, td'));
      return cells.map(cell => {
        // Rimuovi link e mantieni solo il testo
        let text = cell.innerText
          .replace(/\n/g, ' ')
          .replace(/\r/g, '')
          .trim();

        // Escape per CSV: se contiene virgola, virgolette o newline
        if (text.includes(',') || text.includes('"') || text.includes('\n')) {
          text = '"' + text.replace(/"/g, '""') + '"';
        }
        return text;
      }).join(',');
    }).filter(line => line.replace(/,/g, '').trim().length > 0);

    return csvLines.join('\n');
  }

  // ── Scarica un file ─────────────────────────────────────────────
  function downloadFile(content, filename) {
    const BOM  = '\uFEFF';  // BOM UTF-8 per Excel
    const blob = new Blob([BOM + content], { type: 'text/csv;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── Main ────────────────────────────────────────────────────────
  const { season, slug } = getPageInfo();
  let found = 0;
  const results = [];

  TARGET_TABLES.forEach(tableId => {
    const table = findTable(tableId);
    if (!table) {
      results.push(`⬜ ${tableId}: non trovata`);
      return;
    }

    const csv      = tableToCSV(table);
    const rowCount = csv.split('\n').length - 1;  // escludi header

    if (rowCount < 2) {
      results.push(`⚠️ ${tableId}: trovata ma vuota (${rowCount} righe)`);
      return;
    }

    // Nome file: fbref_stats_standard_Serie-A_2024-2025.csv
    const tableName = tableId.replace('stats_', '');
    const filename  = `fbref_${tableName}_${slug}_${season}.csv`;

    // Ritarda ogni download di 300ms per evitare blocchi del browser
    setTimeout(() => downloadFile(csv, filename), found * 350);
    found++;
    results.push(`✅ ${tableId}: ${rowCount} giocatori → ${filename}`);
  });

  // ── Report visivo ───────────────────────────────────────────────
  const panel = document.createElement('div');
  panel.style.cssText = [
    'position:fixed', 'top:20px', 'right:20px', 'z-index:99999',
    'background:#1e293b', 'color:#f1f5f9', 'border:2px solid #3b82f6',
    'border-radius:12px', 'padding:16px 20px', 'font-family:monospace',
    'font-size:13px', 'max-width:420px', 'box-shadow:0 8px 32px rgba(0,0,0,.5)',
  ].join(';');

  panel.innerHTML = `
    <div style="font-weight:bold;font-size:15px;margin-bottom:10px;color:#3b82f6">
      ⚽ FBref CSV Extractor
    </div>
    <div style="margin-bottom:8px;color:#94a3b8">
      Stagione: ${season} · Lega: ${slug}
    </div>
    ${results.map(r => `<div style="margin:3px 0">${r}</div>`).join('')}
    <div style="margin-top:12px;padding-top:10px;border-top:1px solid #334155;color:#64748b;font-size:11px">
      ${found} file scaricati · Chiudi con ESC
    </div>
  `;

  document.body.appendChild(panel);

  // Chiudi con ESC
  document.addEventListener('keydown', function handler(e) {
    if (e.key === 'Escape') {
      panel.remove();
      document.removeEventListener('keydown', handler);
    }
  });

  // Auto-chiudi dopo 15 secondi
  setTimeout(() => { if (panel.parentNode) panel.remove(); }, 15000);

  console.log(`FBref Extractor: ${found} tabelle scaricate`);
  if (found === 0) {
    alert(
      '⚠️ Nessuna tabella trovata.\n\n' +
      'Assicurati di essere su una pagina statistiche FBref,\n' +
      'ad esempio:\nhttps://fbref.com/en/comps/11/stats/Serie-A-Stats\n\n' +
      'La pagina deve aver finito di caricare.'
    );
  }
})();