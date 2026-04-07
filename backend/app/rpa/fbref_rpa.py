import json
import asyncio
import os
import random
from playwright.async_api import async_playwright, Error as PlaywrightError


class FBRefAutopilot:
    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    async def safe_evaluate(self, page, script, retries=3):
        for attempt in range(retries):
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                return await page.evaluate(script)
            except PlaywrightError as e:
                if "Execution context was destroyed" in str(e) and attempt < retries - 1:
                    await asyncio.sleep(2)
                    continue
                raise
        return None

    async def extract_profile_data(self, page):
        """Estrae le tabelle statistiche dalla pagina profilo."""
        try:
            return await self.safe_evaluate(page, '''() => {
                const getTable = (id) => {
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
                    const row = t.querySelector('tbody tr:last-child');
                    if (!row) return null;
                    const res = {};
                    Array.from(row.querySelectorAll('td, th')).forEach(c => {
                        const s = c.getAttribute('data-stat');
                        if (s) res[s] = c.innerText.trim();
                    });
                    return res;
                };

                let name = (document.querySelector('h1') || {}).innerText || "Unknown";
                name = name.split('Stats')[0].trim();

                return {
                    name: name,
                    tables: {
                        standard: getTable('stats_standard_dom_lg'),
                        passing: getTable('stats_passing_dom_lg'),
                        defense: getTable('stats_defense_dom_lg'),
                        gca: getTable('stats_gca_dom_lg')
                    }
                };
            }''')
        except Exception as e:
            print(f"  ⚠️  Errore estrazione profilo: {e}")
            return None

    async def extract_match_logs(self, page):
        """Estrae i match logs dalla pagina match logs."""
        try:
            return await self.safe_evaluate(page, '''() => {
                const t = document.getElementById('matchlogs_all');
                if (!t) return null;
                return Array.from(t.querySelectorAll('tbody tr:not(.unused_sub)')).map(r => {
                    const s = {};
                    Array.from(r.querySelectorAll('td, th')).forEach(c => {
                        const n = c.getAttribute('data-stat');
                        if (n) s[n] = c.innerText.trim();
                    });
                    return s;
                }).filter(m => m.date);
            }''')
        except Exception as e:
            print(f"  ⚠️  Errore estrazione match logs: {e}")
            return None

    async def wait_for_user_navigation(self, page, expected_url_fragment, description, timeout_s=180):
        """
        Aspetta che l'utente navighi manualmente nel browser alla pagina giusta.
        Controlla ogni 2 secondi se l'URL corrente contiene expected_url_fragment
        e che la pagina sia caricata (niente Cloudflare).
        """
        print(f"\n  👉  Naviga manualmente nel browser a:")
        print(f"      {description}")
        print(f"  ⏳  Aspetto fino a {timeout_s} secondi...")

        for _ in range(timeout_s // 2):
            await asyncio.sleep(2)
            try:
                current_url = page.url
                if expected_url_fragment not in current_url:
                    continue

                # URL giusto — verifica che non sia Cloudflare
                status = await self.safe_evaluate(page, '''() => {
                    if (document.querySelector('.cf-turnstile') ||
                        document.getElementById('turnstile-wrapper') ||
                        document.title.includes('Just a moment'))
                        return 'CLOUDFLARE';
                    if (document.querySelector('h1'))
                        return 'READY';
                    return 'LOADING';
                }''')

                if status == 'READY':
                    print(f"  ✅  Pagina rilevata e pronta!")
                    return True
                elif status == 'CLOUDFLARE':
                    print(f"  🔒  Cloudflare attivo — risolvi il captcha nel browser...")

            except PlaywrightError:
                pass  # Navigazione ancora in corso

        print(f"  ❌  Timeout: pagina non raggiunta entro {timeout_s} secondi.")
        return False

    async def get_match_logs_url(self, page, profile_url):
        """Ricava l'URL dei match logs: prima cerca un link nella pagina, poi lo costruisce."""
        try:
            match_url = await self.safe_evaluate(page, '''() => {
                const link = document.querySelector('a[href*="matchlogs/2025-2026/summary/"]');
                return link ? link.href : null;
            }''')
            if match_url:
                return match_url
        except Exception:
            pass

        # Fallback: costruzione dall'URL del profilo
        parts = profile_url.rstrip('/').split('/')
        p_id = parts[5]
        p_name = parts[6].split('?')[0]
        return f"https://fbref.com/en/players/{p_id}/matchlogs/2025-2026/summary/{p_name}-Match-Logs"

    async def run(self, player_urls):
        async with async_playwright() as p:
            print("🚀 Ghost Mode Attiva — MODALITÀ MANUALE")
            print("=" * 60)
            print("Lo script NON naviga da solo per evitare Cloudflare.")
            print("Per ogni giocatore ti dirà quale URL aprire nel browser.")
            print("=" * 60)

            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            page = await context.new_page()

            for url in player_urls:
                player_name = url.rstrip('/').split('/')[-1].replace('-', ' ')
                player_id = url.rstrip('/').split('/')[-2]

                print(f"\n{'='*60}")
                print(f"👤  GIOCATORE: {player_name}")
                print(f"{'='*60}")

                try:
                    # ── STEP 1: Pagina profilo ───────────────────────────────
                    # Aspetta che l'utente navighi manualmente alla pagina del giocatore
                    ready = await self.wait_for_user_navigation(
                        page,
                        expected_url_fragment=player_id,
                        description=url,
                        timeout_s=180
                    )
                    if not ready:
                        print(f"❌ Salto {player_name}.")
                        continue

                    await asyncio.sleep(2)
                    data = await self.extract_profile_data(page)

                    if not data or not data.get('tables', {}).get('standard'):
                        print("  ⚠️  Tabelle non trovate. Sei sulla pagina giusta?")
                        data = data or {'name': player_name, 'tables': {}}
                    else:
                        print(f"  📋  Profilo estratto: {data.get('name')}")

                    # ── STEP 2: Match Logs ───────────────────────────────────
                    match_logs_url = await self.get_match_logs_url(page, url)
                    print(f"\n  URL match logs trovato: {match_logs_url}")

                    ready = await self.wait_for_user_navigation(
                        page,
                        expected_url_fragment="matchlogs",
                        description=match_logs_url,
                        timeout_s=180
                    )

                    match_logs = None
                    if ready:
                        await asyncio.sleep(2)
                        match_logs = await self.extract_match_logs(page)
                        if match_logs:
                            print(f"  ✅  {len(match_logs)} match logs estratti.")
                        else:
                            print("  ⚠️  Nessun match log trovato.")

                    data['match_logs'] = match_logs or []

                    # ── STEP 3: Salvataggio ──────────────────────────────────
                    p_name_save = url.rstrip('/').split('/')[-1].lower()
                    filename = f"{p_name_save.replace('-', '_')}_complete.json"
                    path = os.path.join(self.output_dir, filename)
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    print(f"\n  💾  File salvato: {filename}")

                    # ── STEP 4: Pausa tra giocatori ──────────────────────────
                    if url != player_urls[-1]:
                        wait = random.randint(10, 20)
                        print(f"\n  😴  Pausa di {wait}s prima del prossimo giocatore...")
                        await asyncio.sleep(wait)

                except Exception as e:
                    print(f"❌ Errore critico per {player_name}: {e}")

            await page.close()
            print("\n🏁 Processo completato. Chrome è rimasto attivo.")


if __name__ == "__main__":
    urls = [
        "https://fbref.com/en/players/da2f397e/Federico-Gatti",
        "https://fbref.com/en/players/44662efc/Bremer"
    ]
    asyncio.run(FBRefAutopilot().run(urls))