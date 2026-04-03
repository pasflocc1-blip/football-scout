"""
Script standalone per dumpare il DOM di SofaScore e capire la struttura reale
dei tab e delle chiamate API. Eseguilo nel container:

  docker compose exec backend python app/rpa/dump_sofascore_dom.py

Produce:
  dom_dump.html  — HTML completo della pagina
  dom_tabs.txt   — tutti gli elementi che contengono testo "Stagione/Season/Partite"
  dom_links.txt  — tutti i link href con /player/
  api_calls.txt  — tutte le chiamate a api.sofascore.com catturate in 30s
"""

import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright

try:
    from playwright_stealth import Stealth
    STEALTH = True
except ImportError:
    STEALTH = False

PLAYER_URL = 'https://www.sofascore.com/player/zeki-amdouni/990550'
SCRIPT_DIR = Path(__file__).parent.resolve()
EXTENSION_PATH = SCRIPT_DIR / 'sofascore_extension'


async def main():
    print(f"[dump] playwright-stealth: {'ATTIVO' if STEALTH else 'NON installato'}")
    print(f"[dump] URL: {PLAYER_URL}")

    pw = await async_playwright().start()
    user_data_dir = Path.home() / '.scout_chrome_profile'
    user_data_dir.mkdir(exist_ok=True)

    ext = str(EXTENSION_PATH)
    api_calls = []

    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=str(user_data_dir),
        headless=False,
        args=[
            f'--disable-extensions-except={ext}',
            f'--load-extension={ext}',
            '--no-sandbox', '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--window-size=1920,1080',
        ],
        viewport={'width': 1920, 'height': 1080},
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        ),
        locale='it-IT',
        ignore_https_errors=True,
    )

    if STEALTH:
        stealth = Stealth(navigator_webdriver=True, chrome_runtime=True)
        await stealth.apply_stealth_async(ctx)

    # Cattura TUTTE le chiamate di rete
    def on_response(resp):
        url = resp.url
        if 'sofascore.com' in url:
            api_calls.append({
                'status': resp.status,
                'url': url,
                'time': datetime.now().strftime('%H:%M:%S'),
            })
            if 'api.sofascore.com' in url:
                print(f"  [API] {resp.status} {url[-80:]}")

    ctx.on('response', on_response)

    page = await ctx.new_page()

    print(f"\n[dump] Navigazione verso {PLAYER_URL} ...")
    try:
        await page.goto(PLAYER_URL, wait_until='load', timeout=60000)
    except Exception as e:
        print(f"[dump] goto exception: {e}")

    print(f"[dump] Pagina caricata, attesa banner cookies...")

    # AGGIUNGI QUESTO BLOCCO:
    try:
        # Aspetta che il pulsante "AGREE" o "Accetto" sia cliccabile
        # Usiamo un selettore generico per i testi più comuni
        await asyncio.sleep(3)
        for text in ["AGREE", "Accetto", "Consent", "OK", "I AGREE"]:
            btn = page.get_by_role("button", name=text).first
            if await btn.is_visible():
                await btn.click()
                print(f"[dump] Cookies accettati via pulsante: {text}")
                break
    except Exception as e:
        print(f"[dump] Nessun banner cookies rilevato: {e}")

    # Forza uno scroll per "svegliare" il rendering
    await page.evaluate("window.scrollTo(0, 500)")
    await asyncio.sleep(2)

    print("[dump] Attesa 10s per caricamento completo...")
    await asyncio.sleep(10)

    # ── Salva HTML completo ─────────────────────────────────────
    content = await page.content()
    with open('dom_dump.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[dump] dom_dump.html salvato ({len(content)} chars)")

    # ── Titolo e URL corrente ───────────────────────────────────
    title = await page.title()
    current_url = page.url
    print(f"[dump] Titolo: '{title}'")
    print(f"[dump] URL finale: {current_url}")

    # ── Cerca elementi navigazione/tab ─────────────────────────
    tab_results = await page.evaluate("""
        () => {
            const keywords = ['stagione', 'season', 'partite', 'matches',
                              'carriera', 'career', 'statistiche', 'statistics',
                              'media', 'fantasy', 'transfer'];
            const results = [];

            // Cerca tutti gli elementi con questi testi
            const all = document.querySelectorAll('a, button, [role="tab"], li, span, div');
            for (const el of all) {
                const text = el.innerText?.trim().toLowerCase() || '';
                if (keywords.some(k => text === k || text.startsWith(k))) {
                    results.push({
                        tag: el.tagName,
                        role: el.getAttribute('role'),
                        text: el.innerText?.trim().slice(0, 50),
                        href: el.getAttribute('href'),
                        class: el.className?.slice(0, 100),
                        id: el.id,
                        'aria-selected': el.getAttribute('aria-selected'),
                        'data-tab': el.getAttribute('data-tab'),
                        parent_tag: el.parentElement?.tagName,
                        parent_class: el.parentElement?.className?.slice(0, 80),
                    });
                }
            }
            return results.slice(0, 50);
        }
    """)

    with open('dom_tabs.txt', 'w', encoding='utf-8') as f:
        f.write(f"Titolo pagina: {title}\n")
        f.write(f"URL: {current_url}\n\n")
        f.write(f"Elementi navigazione trovati: {len(tab_results)}\n\n")
        for el in tab_results:
            f.write(json.dumps(el, ensure_ascii=False) + "\n")
    print(f"[dump] dom_tabs.txt: {len(tab_results)} elementi trovati")

    # ── Cerca elementi nav generici (primo livello) ─────────────
    nav_structure = await page.evaluate("""
        () => {
            // Cerca nav, [role="tablist"], ul con link
            const navs = [];
            for (const sel of ['nav', '[role="tablist"]', '[role="navigation"]', 'ul']) {
                for (const el of document.querySelectorAll(sel)) {
                    const children = Array.from(el.children).map(c => ({
                        tag: c.tagName,
                        text: c.innerText?.trim().slice(0, 30),
                        role: c.getAttribute('role'),
                        href: c.querySelector('a')?.getAttribute('href'),
                    }));
                    if (children.length > 0 && children.length < 20) {
                        navs.push({
                            selector: sel,
                            tag: el.tagName,
                            role: el.getAttribute('role'),
                            class: el.className?.slice(0, 80),
                            children_count: children.length,
                            children: children,
                        });
                    }
                }
            }
            return navs.slice(0, 20);
        }
    """)

    with open('dom_nav.txt', 'w', encoding='utf-8') as f:
        f.write(f"Struttura navigazione:\n\n")
        for nav in nav_structure:
            f.write(json.dumps(nav, ensure_ascii=False, indent=2) + "\n\n")
    print(f"[dump] dom_nav.txt: {len(nav_structure)} elementi nav trovati")

    # ── Screenshot ──────────────────────────────────────────────
    await page.screenshot(path='dom_screenshot.png', full_page=False)
    print(f"[dump] dom_screenshot.png salvato")

    # ── API calls catturate ──────────────────────────────────────
    with open('api_calls.txt', 'w', encoding='utf-8') as f:
        f.write(f"Totale richieste sofascore.com: {len(api_calls)}\n")
        api_only = [c for c in api_calls if 'api.sofascore.com' in c['url']]
        f.write(f"Di cui api.sofascore.com: {len(api_only)}\n\n")
        for c in api_calls:
            f.write(f"[{c['time']}] {c['status']} {c['url']}\n")
    print(f"[dump] api_calls.txt: {len(api_calls)} richieste ({sum(1 for c in api_calls if 'api.sofascore.com' in c['url'])} API)")

    print("\n[dump] Premi Ctrl+C per chiudere il browser, oppure attendi 5s")
    await asyncio.sleep(5)
    await ctx.close()
    await pw.stop()
    print("[dump] Completato. File prodotti:")
    for f in ['dom_dump.html', 'dom_tabs.txt', 'dom_nav.txt', 'dom_screenshot.png', 'api_calls.txt']:
        p = Path(f)
        print(f"  {f}: {p.stat().st_size if p.exists() else 'NON TROVATO'} bytes")


if __name__ == '__main__':
    asyncio.run(main())