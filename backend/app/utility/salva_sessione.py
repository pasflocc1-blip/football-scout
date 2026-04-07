import json
import asyncio
from playwright.async_api import async_playwright


async def run(player_name):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        # Caricamento cookie
        with open('app/rpa/cookies.json', 'r') as f:
            cookies = json.load(f)
            await context.add_cookies(cookies)

        page = await context.new_page()
        await page.goto("https://fbref.com/en/")

        # Carichiamo i cookie dal file esportato manualmente
        with open('app/rpa/cookies.json', 'r') as f:
            cookies = json.load(f)
            await context.add_cookies(cookies)

        page = await context.new_page()

        # Ora vai direttamente alla pagina, Cloudflare dovrebbe leggerti come "già verificato"
        try:
            print(f"🚀 Accesso diretto con cookie per: {player_name}")
            search_url = f"https://fbref.com/en/search/search.fcgi?search={player_name.replace(' ', '+')}"
            await page.goto(search_url, wait_until="domcontentloaded")

            # ... resto della tua logica di estrazione ...
            print(f"✅ Pagina caricata: {page.url}")

        finally:
            await browser.close()