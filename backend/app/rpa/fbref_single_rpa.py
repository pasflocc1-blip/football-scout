import json
import asyncio
import os
import random
from playwright.async_api import async_playwright


class FBRefFullScraper:
    def __init__(self):
        # Cartella salvataggio
        self.output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    async def extract_all_tables(self, page):
        """Estrae tutte le tabelle, incluse quelle nascoste nei commenti."""
        return await page.evaluate('''() => {
            const results = {
                name: (document.querySelector('h1') || {innerText: 'Unknown'}).innerText.split('Stats')[0].trim(),
                scraped_at: new Date().toISOString(),
                tables: {}
            };

            const tableIds = [
                'stats_standard_dom_lg', 'stats_passing_dom_lg', 
                'stats_passing_types_dom_lg', 'stats_defense_dom_lg', 
                'stats_gca_dom_lg', 'stats_shooting_dom_lg', 
                'stats_possession_dom_lg', 'stats_misc_dom_lg',
                'stats_playing_time_dom_lg'
            ];

            const parseTable = (id) => {
                let table = document.getElementById(id);

                // SE LA TABELLA È NASCOSTA NEI COMMENTI
                if (!table) {
                    const iterator = document.createNodeIterator(document.body, NodeFilter.SHOW_COMMENT);
                    let node;
                    while (node = iterator.nextNode()) {
                        if (node.textContent.includes(`id="${id}"`)) {
                            const tempDiv = document.createElement('div');
                            tempDiv.innerHTML = node.textContent;
                            table = tempDiv.querySelector('table');
                            break;
                        }
                    }
                }

                if (!table) return null;

                // Prendi l'ultima riga (totale stagione attuale)
                const rows = table.querySelectorAll('tbody tr:not(.spacer)');
                const lastRow = rows[rows.length - 1];
                if (!lastRow) return null;

                const data = {};
                Array.from(lastRow.querySelectorAll('td, th')).forEach(cell => {
                    const stat = cell.getAttribute('data-stat');
                    if (stat) data[stat] = cell.innerText.trim();
                });
                return data;
            };

            // Estrai ogni tabella della lista
            tableIds.forEach(id => {
                const shortName = id.replace('stats_', '').replace('_dom_lg', '');
                results.tables[shortName] = parseTable(id);
            });

            // Estrazione Match Logs (se siamo nella pagina corretta)
            const mlTable = document.getElementById('matchlogs_all');
            if (mlTable) {
                results.match_logs = Array.from(mlTable.querySelectorAll('tbody tr:not(.unused_sub)')).map(r => {
                    const rowData = {};
                    Array.from(r.querySelectorAll('td, th')).forEach(c => {
                        const stat = c.getAttribute('data-stat');
                        if (stat) rowData[stat] = c.innerText.trim();
                    });
                    return rowData;
                }).filter(m => m.date);
            }

            return results;
        }''')

    async def run(self, player_id, player_slug):
        async with async_playwright() as p:
            # Connessione al Chrome già aperto (porta 9222)
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            page = await context.new_page()

            try:
                # 1. Pagina Profilo (per tutte le tabelle statistiche)
                profile_url = f"https://fbref.com/en/players/{player_id}/{player_slug}"
                print(f"🌍 Navigazione Profilo: {profile_url}")
                await page.goto(profile_url, wait_until="commit")

                print("🕵️ Attesa Checkbox/Caricamento... Fai uno scroll se necessario.")
                await asyncio.sleep(5)

                # Scroll per forzare il rendering delle tabelle lazy
                await page.mouse.wheel(0, 3000)
                await asyncio.sleep(2)

                full_data = await self.extract_all_tables(page)

                # 2. Pagina Match Logs
                match_url = f"https://fbref.com/en/players/{player_id}/matchlogs/2025-2026/summary/{player_slug}-Match-Logs"
                print(f"📅 Navigazione Match Logs: {match_url}")
                await asyncio.sleep(random.randint(3, 6))  # Pausa umana
                await page.goto(match_url, wait_until="commit")
                await asyncio.sleep(5)

                match_data = await self.extract_all_tables(page)
                full_data['match_logs'] = match_data.get('match_logs', [])

                # 3. Salvataggio Finale
                filename = f"{player_slug.lower().replace('-', '_')}_full_stats.json"
                path = os.path.join(self.output_dir, filename)
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(full_data, f, indent=4, ensure_ascii=False)

                print(f"✅ SUCCESSO! File salvato: {filename}")
                print(f"📊 Tabelle estratte: {', '.join([k for k, v in full_data['tables'].items() if v])}")

            except Exception as e:
                print(f"❌ Errore: {e}")
            finally:
                await page.close()


if __name__ == "__main__":
    # Usa l'ID che hai scoperto funzionare (18dd3219 per Gatti)
    ID_GIOCATORE = "18dd3219"
    SLUG_GIOCATORE = "Federico-Gatti"

    scraper = FBRefFullScraper()
    asyncio.run(scraper.run(ID_GIOCATORE, SLUG_GIOCATORE))