# fbref_single_rpa_2.py
# I file Json scaricati sono salvati in: D:\Progetti\football-scout\backend\app\data\fbref
# Per eseguirlo lanciare: 3-(.venv) PS D:\Progetti\football-scout\backend\app\rpa> py fbref_single_rpa_2.py
#
import json
import asyncio
import os
import random
import re
import logging
from datetime import datetime
from playwright.async_api import async_playwright

# --- GESTIONE PERCORSI RELATIVI (Cross-Platform) ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(CURRENT_DIR, '..', 'data', 'fbref'))
LOG_DIR = os.path.normpath(os.path.join(CURRENT_DIR, 'log'))

for path in [DATA_DIR, LOG_DIR]:
    if not os.path.exists(path):
        os.makedirs(path)

# --- CONFIGURAZIONE LOGGING ---
log_filename = f"fbref_scout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_path = os.path.join(LOG_DIR, log_filename)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("FBRefScraper")


# ──────────────────────────────────────────────────────────────────────────────
# JS di estrazione — definito come costante Python (stringa con virgolette
# doppie esterne) per evitare qualsiasi conflitto con i backtick JavaScript.
#
# FIX v3 rispetto alla versione precedente:
#   - Il regex usava template literals JS (`${baseId}`) dentro una stringa
#     Python, causando output corrotto tipo: id="(` + '`' + `${baseId}...)"
#   - Ora il pattern è costruito con concatenazione JS pura ("id=\\"(" + baseId)
#     senza alcun backtick, compatibile con qualsiasi wrapper Python.
#   - La ricerca nei commenti usa querySelector dopo innerHTML invece di
#     cercare la table come primo figlio diretto (FBref wrappa in <div id="div_...">).
# ──────────────────────────────────────────────────────────────────────────────
EXTRACT_JS = """
() => {

    // 1. Raccoglie tutti i testi dei commenti HTML (una volta sola)
    var collectComments = function() {
        var texts = [];
        var it = document.createNodeIterator(document.body, NodeFilter.SHOW_COMMENT);
        var n;
        while (n = it.nextNode()) { texts.push(n.textContent); }
        return texts;
    };
    var commentTexts = collectComments();

    // 2. Cerca la tabella con id che inizia per baseId
    //    Prima nel DOM visibile, poi nei commenti HTML.
    var findTable = function(baseId) {

        // DOM diretto
        var direct = document.querySelector('table[id^="' + baseId + '"]');
        if (direct) return direct;

        // Nei commenti: regex costruito con concatenazione (NO template literals)
        var patternStr = 'id="(' + baseId + '[^"]*)"';
        var pattern = new RegExp(patternStr);

        var bestText = null;
        var bestLen  = 9999;

        for (var i = 0; i < commentTexts.length; i++) {
            var m = commentTexts[i].match(pattern);
            if (m && m[1].length < bestLen) {
                bestLen  = m[1].length;
                bestText = commentTexts[i];
            }
        }

        if (!bestText) return null;

        // Parsa l'HTML del commento — la table puo' essere dentro un div wrapper
        var wrapper = document.createElement('div');
        wrapper.innerHTML = bestText;
        return wrapper.querySelector('table[id^="' + baseId + '"]');
    };

    // 3. Estrae la riga dati dalla tabella (lega principale piu' recente)
    //
    // FIX v4: il bug era che il loop usava "break" appena trovava la prima
    // riga con top league. FBref ordina le righe dalla stagione piu' vecchia
    // alla piu' recente, quindi il break prendeva sempre la stagione piu' vecchia
    // (es. 2022-2023 invece di 2025-2026 per Gatti).
    //
    // Soluzione: eliminato il "break" esterno. Il loop continua sempre fino alla
    // fine, sovrascrivendo targetRow ad ogni match. L'ultima riga che matcha una
    // top league vince, che e' sempre la stagione piu' recente.
    //
    // Gestione giocatori con prestito (due top league nella stessa stagione):
    // viene presa la riga con year_id piu' alto tra le candidate, a parita'
    // di year_id si preferisce quella con piu' minuti giocati.
    var getRowData = function(baseId) {
        var t = findTable(baseId);
        if (!t) return null;

        var allRows = Array.from(t.querySelectorAll('tbody tr'));
        var rows = allRows.filter(function(r) {
            return !r.classList.contains('spacer') &&
                   !r.classList.contains('thead') &&
                   !r.classList.contains('partial_table') &&
                   !r.classList.contains('stat_total');
        });

        var targetRow = null;

        if (rows.length > 0) {
            var topLeagues = [
                /1\\.\\s*Serie A/i, /1\\.\\s*La Liga/i, /1\\.\\s*Bundesliga/i,
                /1\\.\\s*Ligue 1/i, /1\\.\\s*Premier/i, /Eredivisie/i
            ];

            // Raccoglie tutte le righe che corrispondono a una top league
            var candidates = [];
            for (var j = 0; j < rows.length; j++) {
                var cell = rows[j].querySelector('[data-stat="comp_level"]');
                if (cell) {
                    var comp = cell.innerText.trim();
                    for (var k = 0; k < topLeagues.length; k++) {
                        if (topLeagues[k].test(comp)) {
                            candidates.push(rows[j]);
                            break;  // break solo sul loop delle leghe, NON sul loop delle righe
                        }
                    }
                }
            }

            if (candidates.length > 0) {
                // Tra i candidati: preferisce year_id piu' alto (stagione piu' recente).
                // A parita' di year_id preferisce piu' minuti (caso prestito).
                var bestYearId = '';
                var bestMinutes = -1;
                for (var c = 0; c < candidates.length; c++) {
                    var yearCell = candidates[c].querySelector('[data-stat="year_id"]');
                    var minCell  = candidates[c].querySelector('[data-stat="minutes"]');
                    var yearVal  = yearCell ? yearCell.innerText.trim() : '';
                    var minVal   = minCell  ? parseInt(minCell.innerText.replace(/,/g, '')) || 0 : 0;
                    if (yearVal > bestYearId || (yearVal === bestYearId && minVal > bestMinutes)) {
                        bestYearId  = yearVal;
                        bestMinutes = minVal;
                        targetRow   = candidates[c];
                    }
                }
            }

            // Fallback: nessuna top league trovata → ultima riga disponibile
            if (!targetRow) targetRow = rows[rows.length - 1];
        } else {
            targetRow = t.querySelector('tfoot tr');
        }

        if (!targetRow) return null;

        var data = {};
        var cells = Array.from(targetRow.querySelectorAll('td, th'));
        cells.forEach(function(c) {
            var s = c.getAttribute('data-stat');
            if (s) data[s] = c.innerText.trim();
        });
        return Object.keys(data).length > 0 ? data : null;
    };

    // 4. Struttura risultato
    var h1 = document.querySelector('h1');
    var res = {
        name: h1 ? h1.innerText.split('Stats')[0].trim() : 'Unknown',
        tables: {}
    };

    ['standard', 'passing', 'defense', 'gca', 'shooting', 'possession', 'misc'].forEach(function(k) {
        res.tables[k] = getRowData('stats_' + k);
    });

    // 5. Match logs
    var mlTable = document.getElementById('matchlogs_all');
    if (mlTable) {
        res.match_logs = Array.from(
            mlTable.querySelectorAll('tbody tr:not(.unused_sub)')
        ).map(function(r) {
            var d = {};
            Array.from(r.querySelectorAll('td, th')).forEach(function(c) {
                var s = c.getAttribute('data-stat');
                if (s) d[s] = c.innerText.trim();
            });
            return d;
        }).filter(function(m) { return m.date; });
    }

    return res;
}
"""


class FBRefFullScraper:
    def __init__(self):
        self.output_dir = DATA_DIR

    async def get_player_id_and_slug(self, page, player_name):
        log.info(f"🔍 Ricerca automatica ID per: {player_name}...")
        search_url = f"https://fbref.com/search/search.fcgi?search={player_name.replace(' ', '+')}"

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            current_url = page.url
            if "search.fcgi" in current_url:
                log.warning(f"⚠️ Risultati multipli per {player_name}, scelgo il primo...")
                first_link = await page.wait_for_selector(
                    "div.search-item a[href*='/players/']", timeout=5000
                )
                relative_url = await first_link.get_attribute("href")
                current_url = f"https://fbref.com{relative_url}"

            match = re.search(r'players/([^/]+)/([^/]+)', current_url)
            if match:
                p_id = match.group(1)
                p_slug = match.group(2).split('?')[0]
                return p_id, p_slug
        except Exception as e:
            log.error(f"❌ Errore durante la ricerca di {player_name}: {e}")

        return None, None

    async def run(self, player_name, counter_info, manual_id=None):
        async with async_playwright() as p:
            try:
                log.info(f"⏳ {counter_info} | Elaborazione calciatore: {player_name}")

                browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                context = browser.contexts[0]
                page = await context.new_page()

                if manual_id:
                    p_id = manual_id
                    p_slug = player_name.replace(" ", "-")
                else:
                    p_id, p_slug = await self.get_player_id_and_slug(page, player_name)

                if not p_id:
                    log.error(f"🛑 {counter_info} | Salto {player_name}: ID non recuperabile.")
                    return

                # Carica pagina profilo
                profile_url = f"https://fbref.com/en/players/{p_id}/{p_slug}"
                await page.goto(profile_url, wait_until="networkidle", timeout=45000)

                # Scroll progressivo per forzare rendering dei commenti
                for _ in range(5):
                    await page.mouse.wheel(0, 1000)
                    await asyncio.sleep(1)
                await asyncio.sleep(3)

                final_data = await page.evaluate(EXTRACT_JS)

                # Log diagnostico
                found   = [k for k, v in final_data.get('tables', {}).items() if v is not None]
                missing = [k for k, v in final_data.get('tables', {}).items() if v is None]
                log.info(f"   📊 Tabelle trovate:  {found}")
                if missing:
                    log.warning(f"   ⚠️  Tabelle mancanti: {missing}")

                # Match Logs stagione corrente
                match_url = (
                    f"https://fbref.com/en/players/{p_id}/matchlogs/2025-2026/summary/"
                    f"{p_slug}-Match-Logs"
                )
                await asyncio.sleep(random.randint(4, 7))
                await page.goto(match_url, wait_until="networkidle", timeout=45000)
                await asyncio.sleep(4)

                logs_data = await page.evaluate(EXTRACT_JS)
                final_data['match_logs'] = logs_data.get('match_logs', [])
                log.info(f"   📋 Match logs: {len(final_data['match_logs'])} partite")

                # Salvataggio
                filename  = f"{p_slug.lower().replace('-', '_')}_complete.json"
                save_path = os.path.join(self.output_dir, filename)
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(final_data, f, indent=4, ensure_ascii=False)

                log.info(f"✅ {counter_info} | Dati salvati in: {filename}")

            except Exception as e:
                log.error(f"❌ {counter_info} | Errore critico per {player_name}: {e}")
            finally:
                await page.close()


if __name__ == "__main__":
    target_scout = [
        {"nome": "Federico Gatti",      "id_manuale": "18dd3219"},
        {"nome": "Leonardo Spinazzola", "id_manuale": None},
        {"nome": "Dusan Vlahovic",      "id_manuale": None},
        {"nome": "Gianluca Mancini",    "id_manuale": None},
        {"nome": "Nicolò Barella",      "id_manuale": None},
        {"nome": "Moise Kean",          "id_manuale": None},
        {"nome": "Lautaro Martínez",    "id_manuale": None},
        {"nome": "Rafael Leão",         "id_manuale": None},
        {"nome": "Lorenzo Pellegrini",  "id_manuale": None},
    ]

    async def main():
        scraper = FBRefFullScraper()
        total = len(target_scout)
        log.info(f"🚀 Avvio sessione RPA FBref - {total} calciatori in coda")

        for index, giocatore in enumerate(target_scout, start=1):
            counter_str = f"Caricamento [{index}/{total}]"
            await scraper.run(giocatore["nome"], counter_str, giocatore["id_manuale"])

            if index < total:
                wait_time = random.randint(15, 25)
                log.info(f"😴 Pausa anti-ban di {wait_time}s...")
                await asyncio.sleep(wait_time)

        log.info("🏁 Sessione completata.")

    asyncio.run(main())