# fbref_debug_visual.py
# Apre la pagina di Barella, aspetta 10 secondi (tempo per vedere cosa succede
# nel browser), poi fa uno screenshot + dump del titolo e di tutti gli ID presenti.
# Eseguire: py fbref_debug_visual.py
# Output: log/fbref_screenshot.png  +  log/fbref_debug_visual.json

import json
import asyncio
import os
import logging
from playwright.async_api import async_playwright

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.normpath(os.path.join(CURRENT_DIR, 'log'))
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger("FBRefVisual")

PLAYER_URL = "https://fbref.com/en/players/6928979a/Nicolo-Barella"

# JS che raccoglie tutto quello che e' nella pagina
FULL_SCAN_JS = """
() => {
    var res = {
        page_title:      document.title,
        h1:              '',
        final_url:       window.location.href,
        all_ids:         [],          // tutti gli id presenti nel DOM
        table_ids:       [],          // solo tabelle
        all_text_sample: '',          // primi 500 chars di testo visibile
        link_hrefs:      []           // tutti i link della pagina
    };

    var h1 = document.querySelector('h1');
    res.h1 = h1 ? (h1.innerText || '') : '';

    // Tutti gli elementi con id
    document.querySelectorAll('[id]').forEach(function(el) {
        var id = el.id;
        if (id) res.all_ids.push(id);
    });

    // Solo tabelle
    document.querySelectorAll('table[id]').forEach(function(t) {
        res.table_ids.push(t.id);
    });

    // Testo visibile (body)
    var body = document.body;
    res.all_text_sample = body ? (body.innerText || '').substring(0, 800).replace(/\\s+/g, ' ') : '';

    // Link
    document.querySelectorAll('a[href]').forEach(function(a) {
        var href = a.href || '';
        if (href.indexOf('fbref.com') !== -1 && href.indexOf('/players/') !== -1) {
            if (res.link_hrefs.length < 30) res.link_hrefs.push(href);
        }
    });

    return res;
}
"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        page = await context.new_page()

        log.info(f"Navigazione verso: {PLAYER_URL}")
        await page.goto(PLAYER_URL, wait_until="networkidle", timeout=45000)

        log.info("Attesa 10 secondi — guarda il browser per vedere cosa viene caricato...")
        await asyncio.sleep(10)

        # Screenshot per vedere cosa c'e' a schermo
        screenshot_path = os.path.join(LOG_DIR, "fbref_screenshot.png")
        await page.screenshot(path=screenshot_path, full_page=False)
        log.info(f"Screenshot salvato: {screenshot_path}")

        # Scroll lento
        for _ in range(8):
            await page.mouse.wheel(0, 800)
            await asyncio.sleep(1)
        await asyncio.sleep(3)

        data = await page.evaluate(FULL_SCAN_JS)

        log.info(f"URL finale caricata:   {data['final_url']}")
        log.info(f"Titolo pagina:         {data['page_title']}")
        log.info(f"H1:                    {data['h1']}")
        log.info(f"Tabelle con ID:        {data['table_ids']}")
        log.info(f"Tutti gli ID (primi 30): {data['all_ids'][:30]}")
        log.info(f"Testo pagina (primi 300 chars): {data['all_text_sample'][:300]}")

        out_path = os.path.join(LOG_DIR, "fbref_debug_visual.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info(f"Dump salvato: {out_path}")

        await page.close()


asyncio.run(main())