import json
import asyncio
import os
import random
import re
import logging
from datetime import datetime
from playwright.async_api import async_playwright

# --- GESTIONE PERCORSI RELATIVI (Cross-Platform) ---
# Ottiene la cartella dove si trova questo script (backend/app/rpa)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Costruisce il percorso verso backend/app/data/fbref
# .os.path.join gestisce correttamente \ (Windows) e / (Mac)
DATA_DIR = os.path.normpath(os.path.join(CURRENT_DIR, '..', 'data', 'fbref'))
LOG_DIR = os.path.normpath(os.path.join(CURRENT_DIR, 'log'))

# Crea le cartelle se non esistono
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


class FBRefFullScraper:
    def __init__(self):
        # Usiamo il percorso dinamico calcolato sopra
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
                first_link = await page.wait_for_selector("div.search-item a[href*='/players/']", timeout=5000)
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

    async def extract_deep_data(self, page):
        """Estrae tabelle dai commenti e match logs via JS injection."""
        return await page.evaluate('''() => {
            const getRowData = (id) => {
                let t = document.getElementById(id);
                if (!t) {
                    const it = document.createNodeIterator(document.body, NodeFilter.SHOW_COMMENT);
                    let n;
                    while (n = it.nextNode()) {
                        if (n.textContent.includes(`id="${id}"`)) {
                            const d = document.createElement('div'); d.innerHTML = n.textContent;
                            t = d.querySelector('table'); break;
                        }
                    }
                }
                if (!t) return null;
                const row = t.querySelector('tbody tr:last-child') || t.querySelector('tfoot tr');
                if (!row) return null;
                const data = {};
                Array.from(row.querySelectorAll('td, th')).forEach(c => {
                    const s = c.getAttribute('data-stat');
                    if (s) data[s] = c.innerText.trim();
                });
                return data;
            };

            const h1 = document.querySelector('h1');
            const res = { 
                name: h1 ? h1.innerText.split('Stats')[0].trim() : "Unknown",
                tables: {} 
            };

            ['standard', 'passing', 'defense', 'gca', 'shooting', 'possession', 'misc'].forEach(k => {
                res.tables[k] = getRowData(`stats_${k}_dom_lg`);
            });

            const mlTable = document.getElementById('matchlogs_all');
            if (mlTable) {
                res.match_logs = Array.from(mlTable.querySelectorAll('tbody tr:not(.unused_sub)')).map(r => {
                    const d = {};
                    Array.from(r.querySelectorAll('td, th')).forEach(c => {
                        const s = c.getAttribute('data-stat');
                        if (s) d[s] = c.innerText.trim();
                    });
                    return d;
                }).filter(m => m.date);
            }
            return res;
        }''')

    async def run(self, player_name, counter_info, manual_id=None):
        async with async_playwright() as p:
            try:
                log.info(f"⏳ {counter_info} | Elaborazione calciatore: {player_name}")

                # Connessione al browser di debug
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

                # Profilo
                profile_url = f"https://fbref.com/en/players/{p_id}/{p_slug}"
                await page.goto(profile_url, wait_until="commit")

                for _ in range(3):
                    await page.mouse.wheel(0, 800)
                    await asyncio.sleep(1)

                final_data = await self.extract_deep_data(page)

                # Match Logs
                match_url = f"https://fbref.com/en/players/{p_id}/matchlogs/2025-2026/summary/{p_slug}-Match-Logs"
                await asyncio.sleep(random.randint(4, 7))
                await page.goto(match_url, wait_until="commit")
                await asyncio.sleep(4)

                logs_data = await self.extract_deep_data(page)
                final_data['match_logs'] = logs_data.get('match_logs', [])

                # Salvataggio
                filename = f"{p_slug.lower().replace('-', '_')}_complete.json"
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
        {"nome": "Federico Gatti", "id_manuale": "18dd3219"},
        {"nome": "Leonardo Spinazzola", "id_manuale": None},
        {"nome": "Dusan Vlahovic", "id_manuale": None}
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