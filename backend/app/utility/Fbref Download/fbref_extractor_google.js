(function() {
  'use strict';

  // Configurazione tabelle per tutti i tuoi link (Standard, Portieri, Tiri, ecc.)
  const TARGET_TABLES = [
    'stats_standard',
    'stats_keeper',
    'stats_shooting',
    'stats_playing_time',
    'stats_misc'
  ];

  function findTable(id) {
    // 1. Cerca prima nel DOM visibile
    let tbl = document.getElementById(id);
    if (tbl) return tbl;

    // 2. Cerca nei commenti HTML (tecnica usata da FBref per il lazy load)
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_COMMENT, null, false);
    let node;
    while (node = walker.nextNode()) {
      if (node.textContent.includes(`id="${id}"`)) {
        const tmp = document.createElement('div');
        tmp.innerHTML = node.textContent;
        // FIX: Usiamo querySelector invece di getElementById sull'elemento temporaneo
        return tmp.querySelector(`#${id}`);
      }
    }
    return null;
  }

  // Funzione per pulire il CSV dai duplicati delle intestazioni
  function tableToCSV(table) {
    const rows = Array.from(table.querySelectorAll('tr'));
    return rows
      .filter(row => !row.classList.contains('over_header') && !row.classList.contains('thead'))
      .map(row => {
        return Array.from(row.querySelectorAll('th, td'))
          .map(cell => `"${cell.innerText.replace(/"/g, '""').trim()}"`)
          .join(',');
      }).join('\n');
  }

  // Esecuzione
  let found = 0;
  TARGET_TABLES.forEach(id => {
    const table = findTable(id);
    if (table) {
      const csv = tableToCSV(table);
      const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `fbref_${id}.csv`;
      link.click();
      found++;
      console.log(`✅ Scaricata tabella: ${id}`);
    }
  });

  if (found === 0) alert("Nessuna tabella trovata. Assicurati di essere su una pagina statistiche di FBref.");
})();