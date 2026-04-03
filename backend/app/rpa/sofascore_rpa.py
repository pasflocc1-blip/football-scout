"""
rpa/sofascore_rpa.py  — v9.5-fast
-----------------------------------
OTTIMIZZAZIONE TEMPI rispetto a v9.0:

  PROBLEMA:
    I sleep fissi nelle Fasi 3 e 4 sommano 32-38 secondi SEMPRE,
    anche quando SofaScore risponde in 1-2 secondi.

  SOLUZIONE — wait_for_capture():
    Sostituisce asyncio.sleep() ciechi con un'attesa condizionale:
      - Controlla captured ogni 300ms
      - Ritorna appena il dato cercato è presente
      - Esce comunque al timeout (sicurezza anti-blocco)

  RISULTATO ATTESO:
    Giocatori veloci (rispondono subito):   ~20-25s  (era ~60s)
    Giocatori lenti (rete lenta / bot check): ~35-40s (era ~60s)
    Nessuna regressione: se il dato non arriva, escala al fallback JS fetch

  MODIFICHE SPECIFICHE:
    - Fase 3: sleep(5)+sleep(3)+sleep(6) → wait_for_capture('attribute-overviews', timeout=10)
    - Fase 4: sleep(5)+sleep(4)+loop_scroll+sleep(2) → wait_for_capture('heatmap', timeout=9)
              Lo scroll loop 5×1s è ridotto a 3 scroll con 0.4s tra l'uno e l'altro
    - Fase 7 heatmap nav: sleep(3)+sleep(3) → wait_for_capture per tid/sid, timeout=5
    - Sleep tra competizioni: da random(0.7,1.3) a random(0.3,0.7)
    - Sleep post-fase 7: da 2s a 1s
    - Sleep tra endpoint Fase 5: da random(0.6,1.2) a random(0.3,0.6)

  INVARIATO:
    - Tutta la logica di intercettazione, fallback, iniezione JS
    - Fase 1 (homepage): rimane 2s — necessaria per cookie/sessione
    - Fase 2 (profilo/slug): rimane 0.5s — attesa minima post-fetch
    - Tutti i timeout di sicurezza
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
import time
import random
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f'rpa_sofascore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
            encoding='utf-8'
        ),
    ]
)
log = logging.getLogger(__name__)

SOFA_BASE = 'https://www.sofascore.com'
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')

DELAY_BETWEEN_PLAYERS = 5.0
MAX_RETRIES = 2
PAGE_TIMEOUT_MS = 35_000
INTERCEPT_WAIT_MS = 10_000

LEAGUES = {
    'serie_a': {'tournament_id': 23, 'season_id': 63515},
    'premier_league': {'tournament_id': 17, 'season_id': 61627},
    'la_liga': {'tournament_id': 8, 'season_id': 61643},
    'bundesliga': {'tournament_id': 35, 'season_id': 63609},
    'ligue_1': {'tournament_id': 34, 'season_id': 63684},
    'champions_league': {'tournament_id': 7, 'season_id': 61657},
    'eredivisie': {'tournament_id': 37, 'season_id': 63646},
    'primeira_liga': {'tournament_id': 238, 'season_id': 63751},
    'championship': {'tournament_id': 18, 'season_id': 63516},
}

INTERCEPT_PATTERNS = [
    r'/api/v1/player/\d+$',
    r'/api/v1/player/\d+/attribute-overviews',
    r'/api/v1/player/\d+/unique-tournament/\d+/season/\d+/statistics',
    r'/api/v1/player/\d+/heatmap/',
    r'/api/v1/player/\d+/events/',
    r'/api/v1/player/\d+/transfer-history',
    r'/api/v1/player/\d+/national-team-statistics',
    r'/api/v1/player/\d+/unique-tournament/\d+/seasons',
    r'/api/v1/search/all',
]


# ══════════════════════════════════════════════════════════════════
# HELPER: attesa condizionale su captured
# ══════════════════════════════════════════════════════════════════

async def wait_for_capture(
    captured: dict,
    keyword: str,
    timeout: float = 10.0,
    poll_interval: float = 0.3,
    extra_condition=None,
) -> bool:
    """
    Aspetta finché una URL contenente `keyword` appare in `captured`,
    oppure finché scade il timeout.

    Args:
        captured:        dict URL → data popolato dal listener _on_response
        keyword:         sottostringa da cercare nelle URL (es. 'attribute-overviews')
        timeout:         secondi massimi di attesa (default 10)
        poll_interval:   intervallo di polling in secondi (default 0.3)
        extra_condition: callable(captured) → bool per condizioni aggiuntive

    Returns:
        True  se il dato è stato trovato prima del timeout
        False se è scaduto il timeout (il chiamante usa il fallback)
    """
    elapsed = 0.0
    while elapsed < timeout:
        # Controlla se la keyword è già in captured
        found = any(keyword in url for url in captured)
        if found:
            if extra_condition is None or extra_condition(captured):
                return True
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return False


async def wait_for_heatmap_capture(
    captured: dict,
    tid: str,
    sid: str,
    timeout: float = 7.0,
    poll_interval: float = 0.3,
) -> bool:
    """
    Versione specializzata per la heatmap: controlla anche tid e sid.
    """
    elapsed = 0.0
    while elapsed < timeout:
        for url in captured:
            if 'heatmap' in url and f'/{tid}/' in url and f'/{sid}' in url:
                pts = captured[url].get('points', captured[url].get('heatmap', []))
                if pts:
                    return True
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return False


# ══════════════════════════════════════════════════════════════════
# DATACLASS
# ══════════════════════════════════════════════════════════════════

@dataclass
class PlayerJob:
    name: str
    club: str = ''
    sofascore_id: Optional[int] = None
    db_id: Optional[int] = None
    league_key: str = 'serie_a'
    status: str = 'pending'
    error: str = ''
    started_at: str = ''
    completed_at: str = ''
    data_fetched: dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════
# SORGENTI  (invariate)
# ══════════════════════════════════════════════════════════════════

def load_from_db(league, only_missing=True):
    try:
        from app.database import SessionLocal
        from app.models.models import ScoutingPlayer, Club
        from sqlalchemy import or_
        db = SessionLocal()
        try:
            q = db.query(ScoutingPlayer).join(Club, ScoutingPlayer.club_id == Club.id)
            q = q.filter(Club.league_key == league)
            log.info(f"RPA: Avvio sessione per la lega '{league}'")
            if only_missing:
                q = q.filter(or_(
                    ScoutingPlayer.sofascore_id.is_(None),
                    ScoutingPlayer.last_updated_sofascore.is_(None),
                ))
            players = q.order_by(ScoutingPlayer.name).all()
            jobs = [PlayerJob(
                name=p.name,
                club=p.club or '',
                sofascore_id=int(p.sofascore_id) if p.sofascore_id else None,
                db_id=p.id,
                league_key=league,
            ) for p in players]
            log.info(f'DB: {len(jobs)} giocatori caricati.')
            return jobs
        finally:
            db.close()
    except Exception as e:
        log.error(f'Errore caricamento DB: {e}')
        return []


def load_from_csv(filepath, league='serie_a'):
    jobs = []
    with open(filepath, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            jobs.append(PlayerJob(
                name=row.get('name', '').strip(),
                club=row.get('club', '').strip(),
                sofascore_id=int(row['sofascore_id']) if row.get('sofascore_id') else None,
                league_key=row.get('league', league),
            ))
    log.info(f'CSV: {len(jobs)} da {filepath}')
    return jobs


def load_single(name, club='', sofascore_id=None, league='serie_a'):
    return [PlayerJob(name=name, club=club, sofascore_id=sofascore_id, league_key=league)]


# ══════════════════════════════════════════════════════════════════
# UTILITÀ  (invariate)
# ══════════════════════════════════════════════════════════════════

def extract_competitions_from_matches(matches: list) -> list:
    seen = {}
    for m in matches:
        t = m.get('tournament', {})
        ut = t.get('uniqueTournament', {})
        s = m.get('season', {})
        tid = ut.get('id')
        sid = s.get('id')
        if not tid or not sid:
            continue
        key = (tid, sid)
        if key not in seen:
            seen[key] = {
                'tournament_id': tid,
                'season_id': sid,
                'tournament_name': ut.get('name') or t.get('name', 'Unknown'),
                'season_year': s.get('year', ''),
                'season_name': s.get('name', ''),
            }
    comps = list(seen.values())
    log.info(f'  Competizioni trovate nelle partite: {len(comps)}')
    for c in comps:
        log.info(f'    → {c["tournament_name"]} {c["season_year"]} '
                 f'(tid={c["tournament_id"]}, sid={c["season_id"]})')
    return comps


def _map_attributes(raw: list) -> dict:
    result = {}
    if not isinstance(raw, list) or not raw:
        return result
    first = raw[0] if raw else {}
    if isinstance(first, dict) and 'attributes' not in first and 'title' not in first:
        for item in raw:
            for k, v in item.items():
                if k != 'position' and v is not None:
                    result[f'attr_{k}'] = v
                elif k == 'position':
                    result['attr_position'] = v
        return result
    for group in raw:
        group_title = group.get('title', 'unknown').replace(' ', '_')
        avg = group.get('averageAttributeValue')
        if avg is not None:
            result[f'attr_avg_{group_title}'] = avg
        for attr in group.get('attributes', []):
            key = attr.get('key', '')
            value = attr.get('value')
            title = attr.get('title', '')
            if key:
                result[f'attr_{key}'] = value
                result[f'attr_title_{key}'] = title
    return result


# ══════════════════════════════════════════════════════════════════
# PLAYWRIGHT CLIENT
# ══════════════════════════════════════════════════════════════════

class SofaPlaywrightClient:

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._stealth_fn = None
        self._xrw_token = 'XMLHttpRequest'

    async def start(self):
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox', '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage', '--disable-gpu',
            ]
        )
        self._context = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            locale='it-IT',
            timezone_id='Europe/Rome',
            extra_http_headers={'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8'},
        )
        try:
            from playwright_stealth import stealth_async
            self._stealth_fn = stealth_async
            log.info('[PW] Stealth attivo')
        except ImportError:
            log.warning('[PW] playwright-stealth non disponibile')
        log.info('[PW] Browser avviato')

    async def stop(self):
        if self._context: await self._context.close()
        if self._browser: await self._browser.close()
        if self._playwright: await self._playwright.stop()
        log.info('[PW] Browser chiuso')

    async def _js_fetch(self, page, endpoint: str, referer: str = None) -> Optional[dict]:
        url = f'{SOFA_BASE}{endpoint}' if endpoint.startswith('/') else endpoint
        ref = referer or f'{SOFA_BASE}/'
        xrw = self._xrw_token
        try:
            data = await page.evaluate(f"""
                async () => {{
                    try {{
                        const r = await fetch('{url}', {{
                            credentials: 'include',
                            headers: {{
                                'Accept': 'application/json, text/plain, */*',
                                'Referer': '{ref}',
                                'x-requested-with': '{xrw}',
                            }}
                        }});
                        if (!r.ok) return {{ __status: r.status }};
                        return await r.json();
                    }} catch(e) {{ return {{ __error: e.toString() }}; }}
                }}
            """)
            if data and ('__status' in data or '__error' in data):
                code = data.get('__status', 'err')
                log.warning(f'  [PW-JS] HTTP {code}: {endpoint[-55:]}')
                return None
            return data if data else None
        except Exception as e:
            log.warning(f'  [PW-JS] Eccezione {endpoint[-50:]}: {e}')
            return None

    async def _extract_xrw_token(self, page) -> str:
        try:
            token = await page.evaluate("""
                () => {
                    const scripts = Array.from(document.querySelectorAll('script[src]'))
                        .map(s => s.src)
                        .filter(s => s.includes('/_next/') || s.includes('/static/'));
                    try {
                        const chunks = window.__NEXT_DATA__ || {};
                        const str = JSON.stringify(chunks);
                        const m = str.match(/"x-?[Rr]equested-?[Ww]ith"\s*:\s*"([a-f0-9]{4,10})"/);
                        if (m) return m[1];
                    } catch(e) {}
                    const html = document.documentElement.innerHTML;
                    const patterns = [
                        /x-requested-with['":\s]+([a-f0-9]{4,10})/i,
                        /"x-requested-with":"([a-f0-9]{4,10})"/i,
                        /xRequestedWith['":\s]+([a-f0-9]{4,10})/i,
                    ];
                    for (const p of patterns) {
                        const m = html.match(p);
                        if (m && m[1] !== 'xmlhttprequest') return m[1];
                    }
                    return null;
                }
            """)
            if token:
                log.info(f'  [PW] Token estratto: {token}')
                return token
        except Exception as e:
            log.warning(f'  [PW] Estrazione token fallita: {e}')

        try:
            js_urls = await page.evaluate("""
                () => Array.from(document.querySelectorAll('script[src]'))
                    .map(s => s.src)
                    .filter(s => (s.includes('/_next/static/chunks/') || s.includes('/static/js/'))
                                 && s.endsWith('.js'))
                    .slice(0, 5)
            """)
            for js_url in js_urls:
                try:
                    js_content = await page.evaluate(f"""
                        async () => {{
                            const r = await fetch('{js_url}');
                            return r.ok ? await r.text() : null;
                        }}
                    """)
                    if js_content:
                        import re as _re
                        for pat in [
                            r'"x-requested-with"\s*:\s*"([a-f0-9]{4,10})"',
                            r'xRequestedWith\s*:\s*"([a-f0-9]{4,10})"',
                            r"'x-requested-with'\s*:\s*'([a-f0-9]{4,10})'",
                        ]:
                            m = _re.search(pat, js_content, _re.IGNORECASE)
                            if m and m.group(1).lower() not in ('xmlhttprequest', ''):
                                log.info(f'  [PW] Token trovato nel bundle JS: {m.group(1)}')
                                return m.group(1)
                except Exception:
                    continue
        except Exception as e:
            log.warning(f'  [PW] Ricerca token in bundle JS fallita: {e}')

        log.warning('  [PW] Token non trovato — uso XMLHttpRequest (fallback)')
        return 'XMLHttpRequest'

    async def fetch_player_data(self, player_id: int, league_key: str) -> dict:
        result = {
            'player_id': player_id,
            'league_key': league_key,
            'fetched_at': datetime.utcnow().isoformat(),
            'profile': {},
            'attributes': {},
            'matches': [],
            'transfers': [],
            'national_stats': [],
            'competitions': [],
        }

        page = await self._context.new_page()
        if self._stealth_fn:
            await self._stealth_fn(page)

        self._xrw_token = 'XMLHttpRequest'
        captured = {}

        def _should_capture(url):
            return any(re.search(p, url) for p in INTERCEPT_PATTERNS)

        async def _on_response(response):
            url = response.url
            if not _should_capture(url): return
            ct = response.headers.get('content-type') or ''
            if 'application/json' not in ct: return
            try:
                data = await response.json()
                captured[url] = data
                if 'heatmap' in url:
                    log.info(f'  [📡] Heatmap intercettata: {url[-60:]}')
                elif 'attribute-overviews' in url:
                    log.info(f'  [📡] Attributi intercettati: {url[-60:]}')
            except Exception:
                pass

        async def _on_request(request):
            if '/api/v1/' not in request.url: return
            xrw = request.headers.get('x-requested-with', '')
            if xrw and xrw.lower() not in ('', 'xmlhttprequest') and self._xrw_token == 'XMLHttpRequest':
                self._xrw_token = xrw
                log.info(f'  [📡] Token intercettato: {xrw}')

        page.on('response', _on_response)
        page.on('request', _on_request)

        try:
            # ── FASE 1: Cookie homepage ────────────────────────────
            # Invariata: i 2s sono necessari per la sessione/cookie
            log.info('  [PW] Step 1: acquisizione cookie (homepage)...')
            try:
                await page.goto(SOFA_BASE, wait_until='domcontentloaded', timeout=PAGE_TIMEOUT_MS)
                await asyncio.sleep(2)
            except Exception as e:
                log.warning(f'  [PW] Homepage errore (continuo): {e}')

            # ── FASE 2: Profilo + slug ─────────────────────────────
            log.info(f'  [PW] Step 2: profilo + slug player {player_id}...')
            profile_data = await self._js_fetch(page, f'/api/v1/player/{player_id}')
            if profile_data and profile_data.get('player'):
                result['profile'] = profile_data['player']
                slug = result['profile'].get('slug', f'player-{player_id}')
                log.info(f'  [PW] Profilo OK ({len(result["profile"])} campi) | slug={slug}')
            else:
                slug = f'player-{player_id}'
                log.warning('  [PW] Profilo non disponibile — slug di fallback')

            await asyncio.sleep(0.5)

            # ── FASE 3: Pagina profilo — intercetta attributi ──────
            # OTTIMIZZATO: invece di sleep(5)+sleep(3)+sleep(6)=14s fissi,
            # aspettiamo fino a quando 'attribute-overviews' appare in captured,
            # con timeout 10s. Se arriva prima (di solito in 2-4s), proseguiamo subito.
            player_url = f'{SOFA_BASE}/player/{slug}/{player_id}'
            log.info(f'  [PW] Step 3: navigazione profilo: {player_url}')
            try:
                await page.goto(player_url, wait_until='commit', timeout=PAGE_TIMEOUT_MS)
                # Scroll immediato per attivare i widget React
                await page.evaluate("window.scrollTo(0, 500)")

                # Attesa condizionale: esce appena gli attributi sono intercettati
                found = await wait_for_capture(captured, 'attribute-overviews', timeout=10.0)
                if found:
                    log.info('  [PW] ✅ Attributi intercettati in anticipo — proseguo')
                else:
                    log.info('  [PW] ⏱ Timeout attributi — continuo con fallback JS')

            except Exception as e:
                log.warning(f'  [PW] goto profilo errore (continuo): {e}')

            # ── FASE 4: Tab Statistics — intercetta heatmap ────────
            # OTTIMIZZATO: invece di sleep(5)+sleep(4)+5×sleep(1)+sleep(2)=16s,
            # scroll ridotto a 3 passi + wait_for_capture con timeout 9s.
            stats_url = f'{SOFA_BASE}/player/{slug}/{player_id}/statistics'
            log.info('  [PW] Step 4: navigazione Statistics (heatmap)...')
            try:
                await page.goto(stats_url, wait_until='commit', timeout=PAGE_TIMEOUT_MS)
                # Scroll progressivo compresso: 3 passi da 0.4s (era 5 da 1s)
                for scroll_y in [600, 1000, 1400]:
                    await page.evaluate(f"window.scrollTo(0, {scroll_y})")
                    await asyncio.sleep(0.4)

                # Attesa condizionale heatmap generica (qualsiasi competizione)
                found = await wait_for_capture(captured, 'heatmap', timeout=9.0)
                if found:
                    log.info('  [PW] ✅ Heatmap intercettata in anticipo — proseguo')
                else:
                    log.info('  [PW] ⏱ Timeout heatmap passiva — userò JS fetch per competizione')

            except Exception as e:
                log.warning(f'  [PW] goto statistics errore (continuo): {e}')

            # ── FASE 5: Injection endpoint mancanti ───────────────
            xrw_status = f'✅ {self._xrw_token}' if self._xrw_token != 'XMLHttpRequest' else '⚠️ fallback'
            log.info(f'  [PW] Step 5: token={xrw_status}')

            base_endpoints = [
                f'/api/v1/player/{player_id}/attribute-overviews',
                f'/api/v1/player/{player_id}/transfer-history',
                f'/api/v1/player/{player_id}/national-team-statistics',
            ]

            for ep in base_endpoints:
                captured_data = None
                for url, data in captured.items():
                    if ep in url:
                        captured_data = data
                        break

                if captured_data:
                    log.info(f'  [PW] ✅ {ep.split("/")[-1]} da captured')
                    if 'attribute-overviews' in ep:
                        attrs_raw = (
                            captured_data.get('playerAttributeOverviews')
                            or captured_data.get('playerAttributeGroups')
                            or captured_data.get('playerAttributes')
                            or (captured_data if isinstance(captured_data, list) else [])
                        )
                        result['attributes'] = _map_attributes(attrs_raw)
                        log.info(f'  [PW] ✅ Attributi: {len(result["attributes"])} valori')
                    continue

                log.info(f'  [PW-JS] Forcing fetch: {ep.split("/")[-1]}')
                try:
                    data = await page.evaluate(f"""
                        fetch("{ep}", {{
                            "headers": {{
                                "x-requested-with": "XMLHttpRequest",
                                "cache-control": "no-cache"
                            }}
                        }})
                        .then(res => res.ok ? res.json() : null)
                        .catch(() => null)
                    """)
                    if data:
                        captured[ep] = data
                        if 'attribute-overviews' in ep:
                            attrs_raw = (
                                data.get('playerAttributeOverviews')
                                or data.get('playerAttributeGroups')
                                or data.get('playerAttributes')
                                or (data if isinstance(data, list) else [])
                            )
                            result['attributes'] = _map_attributes(attrs_raw)
                            log.info(f'  [PW-JS] ✅ Attributi via JS: {len(result["attributes"])} valori')
                        log.info(f'  [PW-JS] OK: {ep.split("/")[-1]}')
                    else:
                        log.warning(f'  [PW-JS] Fallito: {ep.split("/")[-1]}')
                except Exception as e:
                    log.error(f'  [PW-JS] Errore {ep}: {e}')

                # OTTIMIZZATO: da random(0.6,1.2) a random(0.3,0.6)
                await asyncio.sleep(random.uniform(0.3, 0.6))

            # ── FASE 6: Estrai dati da captured ──────────────────
            for url, data in captured.items():
                if re.search(r'/api/v1/player/\d+$', url):
                    if not result['profile']:
                        result['profile'] = data.get('player', {})

                elif 'attribute-overviews' in url and not result['attributes']:
                    attrs_raw = (
                        data.get('playerAttributeOverviews')
                        or data.get('playerAttributeGroups')
                        or data.get('playerAttributes')
                        or (data if isinstance(data, list) else [])
                    )
                    result['attributes'] = _map_attributes(attrs_raw)
                    log.info(f'  [PW] Attributi da captured: {len(result["attributes"])} valori')

                elif re.search(r'/events/', url):
                    result['matches'] = data.get('events', [])
                    log.info(f'  [PW] Partite: {len(result["matches"])}')

                elif 'transfer-history' in url:
                    result['transfers'] = data.get('transferHistory', [])
                    log.info(f'  [PW] Trasferimenti: {len(result["transfers"])}')

                elif 'national-team-statistics' in url:
                    nat = data.get('statistics', data if isinstance(data, list) else [])
                    result['national_stats'] = nat if isinstance(nat, list) else [nat]
                    log.info(f'  [PW] Nazionale: {len(result["national_stats"])}')

            # ── FASE 7: Competizioni — stats + heatmap ────────────
            competitions = extract_competitions_from_matches(result['matches'])
            if not competitions and league_key in LEAGUES:
                lg = LEAGUES[league_key]
                competitions = [{
                    'tournament_id': lg['tournament_id'],
                    'season_id': lg['season_id'],
                    'tournament_name': league_key.replace('_', ' ').title(),
                    'season_year': '24/25',
                    'season_name': '',
                }]
                log.warning(f'  [PW] Nessuna partita — fallback: {league_key}')

            log.info(f'  [PW] Step 7: {len(competitions)} competizioni...')

            # OTTIMIZZATO: da sleep(2) a sleep(1) — tempo di assestamento ridotto
            await asyncio.sleep(1)

            for comp in competitions:
                tid = str(comp['tournament_id'])
                sid = str(comp['season_id'])
                name = comp['tournament_name']
                year = comp['season_year']

                log.info(f'  [PW] → {name} {year} (tid={tid}, sid={sid})')
                entry = {**comp, 'statistics': {}, 'heatmap_points': []}

                # --- Stats via JS fetch (invariato) ---
                stats_ep = f'/api/v1/player/{player_id}/unique-tournament/{tid}/season/{sid}/statistics/overall'
                stats_data = await self._js_fetch(page, stats_ep)
                if stats_data and stats_data.get('statistics'):
                    entry['statistics'] = stats_data['statistics']
                    log.info(f'      ✅ Stats: {len(entry["statistics"])} campi')

                # --- Heatmap: controlla captured prima di navigare ---
                heat_ep = f'/api/v1/player/{player_id}/unique-tournament/{tid}/season/{sid}/heatmap/overall'

                for cap_url, cap_data in captured.items():
                    if 'heatmap' in cap_url and f'/{tid}/' in cap_url and f'/{sid}' in cap_url:
                        pts = cap_data.get('points', cap_data.get('heatmap', []))
                        if pts:
                            entry['heatmap_points'] = pts
                            log.info(f'      ✅ Heatmap passiva: {len(pts)} punti')
                            break

                if not entry['heatmap_points']:
                    # OTTIMIZZATO: naviga e usa wait_for_heatmap_capture invece di sleep(3)+sleep(3)
                    heat_page_url = (
                        f'{SOFA_BASE}/player/{slug}/{player_id}/statistics'
                        f'?uniqueTournamentId={tid}&seasonId={sid}'
                    )
                    log.info(f'      Navigazione heatmap: tid={tid} sid={sid}')
                    try:
                        await page.goto(heat_page_url, wait_until='commit', timeout=PAGE_TIMEOUT_MS)
                        await page.evaluate("window.scrollTo(0, 800)")

                        # Attesa condizionale: esce appena heatmap per tid/sid appare in captured
                        found = await wait_for_heatmap_capture(captured, tid, sid, timeout=7.0)
                        if found:
                            log.info(f'      ✅ Heatmap intercettata (wait_for_capture)')
                        else:
                            log.info(f'      ⏱ Timeout heatmap — provo JS fetch')

                        for cap_url, cap_data in captured.items():
                            if 'heatmap' in cap_url and f'/{tid}/' in cap_url and f'/{sid}' in cap_url:
                                pts = cap_data.get('points', cap_data.get('heatmap', []))
                                if pts:
                                    entry['heatmap_points'] = pts
                                    log.info(f'      ✅ Heatmap post-nav: {len(pts)} punti')
                                    break
                    except Exception as e:
                        log.warning(f'      Navigazione heatmap errore: {e}')

                if not entry['heatmap_points']:
                    log.info(f'      Heatmap JS fetch: {heat_ep[-50:]}')
                    heat_referer = f'{SOFA_BASE}/player/{slug}/{player_id}'
                    heat_data = await self._js_fetch(page, heat_ep, referer=heat_referer)
                    if heat_data:
                        pts = heat_data.get('points', heat_data.get('heatmap', []))
                        if pts:
                            entry['heatmap_points'] = pts
                            log.info(f'      ✅ Heatmap JS: {len(pts)} punti')
                        else:
                            log.warning(f'      🚫 Heatmap vuota (tid={tid} sid={sid})')
                    else:
                        log.warning(f'      🚫 Heatmap fetch fallita (tid={tid} sid={sid})')

                if entry['heatmap_points']:
                    log.info(f'      ✅ Heatmap finale: {len(entry["heatmap_points"])} punti')
                else:
                    log.warning(f'      🚫 Heatmap non disponibile (tid={tid} sid={sid})')

                result['competitions'].append(entry)
                # OTTIMIZZATO: da random(0.7,1.3) a random(0.3,0.7)
                await asyncio.sleep(random.uniform(0.3, 0.7))

        finally:
            await page.close()

        n_stats = sum(len(c['statistics']) for c in result['competitions'])
        n_heat = sum(len(c['heatmap_points']) for c in result['competitions'])
        n_attrs = len([v for v in result['attributes'].values() if v is not None])
        log.info(
            f'  [PW] Fine: competizioni={len(result["competitions"])} '
            f'stats={n_stats} heatmap={n_heat} attributi={n_attrs} '
            f'partite={len(result["matches"])} trasferimenti={len(result["transfers"])}'
        )
        return result

    async def search_player_id(self, name: str, team: str) -> Optional[int]:
        page = await self._context.new_page()
        if self._stealth_fn:
            await self._stealth_fn(page)
        try:
            await page.goto(SOFA_BASE, wait_until='domcontentloaded', timeout=PAGE_TIMEOUT_MS)
            await asyncio.sleep(2)
            safe_name = urllib.parse.quote(name)
            data = await self._js_fetch(page, f'/api/v1/search/all?q={safe_name}&page=0')
            if not data:
                return None
            for item in data.get('results', []):
                if item.get('type') != 'player': continue
                entity = item.get('entity', {})
                team_name = entity.get('team', {}).get('name', '').lower()
                if name.lower() in entity.get('name', '').lower():
                    if not team or team.lower() in team_name:
                        found_id = entity.get('id')
                        log.info(f'  Trovato: {entity.get("name")} ({team_name}) → id={found_id}')
                        return found_id
            for item in data.get('results', []):
                if item.get('type') == 'player':
                    found_id = item.get('entity', {}).get('id')
                    found_name = item.get('entity', {}).get('name', '')
                    log.warning(f'  Match parziale: {found_name} → id={found_id}')
                    return found_id
        finally:
            await page.close()
        return None


# ══════════════════════════════════════════════════════════════════
# MAPPING  (invariato da v9.0)
# ══════════════════════════════════════════════════════════════════

def _map_stats(raw: dict) -> dict:
    return {
        'rating': raw.get('rating'),
        'total_rating': raw.get('totalRating'),
        'count_rating': raw.get('countRating'),
        'appearances': raw.get('appearances'),
        'matches_started': raw.get('matchesStarted'),
        'minutes_played': raw.get('minutesPlayed'),
        'goals': raw.get('goals'),
        'assists': raw.get('assists'),
        'goals_assists_sum': raw.get('goalsAssistsSum'),
        'shots_total': raw.get('totalShots'),
        'shots_on_target': raw.get('shotsOnTarget'),
        'shots_off_target': raw.get('shotsOffTarget'),
        'shots_inside_box': raw.get('shotsFromInsideTheBox'),
        'shots_outside_box': raw.get('shotsFromOutsideTheBox'),
        'big_chances_created': raw.get('bigChancesCreated'),
        'big_chances_missed': raw.get('bigChancesMissed'),
        'goal_conversion_pct': raw.get('goalConversionPercentage'),
        'headed_goals': raw.get('headedGoals'),
        'left_foot_goals': raw.get('leftFootGoals'),
        'right_foot_goals': raw.get('rightFootGoals'),
        'goals_inside_box': raw.get('goalsFromInsideTheBox'),
        'goals_outside_box': raw.get('goalsFromOutsideTheBox'),
        'free_kick_goals': raw.get('freeKickGoal'),
        'penalty_goals': raw.get('penaltyGoals'),
        'penalty_taken': raw.get('penaltiesTaken'),
        'penalty_won': raw.get('penaltyWon'),
        'penalty_conceded': raw.get('penaltyConceded'),
        'own_goals': raw.get('ownGoals'),
        'hit_woodwork': raw.get('hitWoodwork'),
        'scoring_frequency': raw.get('scoringFrequency'),
        'totw_appearances': raw.get('totwAppearances'),
        'set_piece_conversion': raw.get('setPieceConversion'),
        'shot_from_set_piece': raw.get('shotFromSetPiece'),
        'xg': raw.get('expectedGoals'),
        'xa': raw.get('expectedAssists'),
        'accurate_passes': raw.get('accuratePasses'),
        'inaccurate_passes': raw.get('inaccuratePasses'),
        'total_passes': raw.get('totalPasses'),
        'pass_accuracy_pct': raw.get('accuratePassesPercentage'),
        'accurate_own_half_passes': raw.get('accurateOwnHalfPasses'),
        'accurate_opp_half_passes': raw.get('accurateOppositionHalfPasses'),
        'total_own_half_passes': raw.get('totalOwnHalfPasses'),
        'total_opp_half_passes': raw.get('totalOppositionHalfPasses'),
        'accurate_final_third_passes': raw.get('accurateFinalThirdPasses'),
        'accurate_long_balls': raw.get('accurateLongBalls'),
        'long_ball_accuracy_pct': raw.get('accurateLongBallsPercentage'),
        'total_long_balls': raw.get('totalLongBalls'),
        'accurate_crosses': raw.get('accurateCrosses'),
        'cross_accuracy_pct': raw.get('accurateCrossesPercentage'),
        'total_crosses': raw.get('totalCross'),
        'key_passes': raw.get('keyPasses'),
        'pass_to_assist': raw.get('passToAssist'),
        'total_attempt_assist': raw.get('totalAttemptAssist'),
        'accurate_chipped_passes': raw.get('accurateChippedPasses'),
        'total_chipped_passes': raw.get('totalChippedPasses'),
        'successful_dribbles': raw.get('successfulDribbles'),
        'dribble_success_pct': raw.get('successfulDribblesPercentage'),
        'dribbled_past': raw.get('dribbledPast'),
        'dispossessed': raw.get('dispossessed'),
        'ground_duels_won': raw.get('groundDuelsWon'),
        'ground_duels_won_pct': raw.get('groundDuelsWonPercentage'),
        'aerial_duels_won': raw.get('aerialDuelsWon'),
        'aerial_duels_lost': raw.get('aerialLost'),
        'aerial_duels_won_pct': raw.get('aerialDuelsWonPercentage'),
        'total_duels_won': raw.get('totalDuelsWon'),
        'total_duels_won_pct': raw.get('totalDuelsWonPercentage'),
        'duel_lost': raw.get('duelLost'),
        'total_contest': raw.get('totalContest'),
        'tackles': raw.get('tackles'),
        'tackles_won': raw.get('tacklesWon'),
        'tackles_won_pct': raw.get('tacklesWonPercentage'),
        'interceptions': raw.get('interceptions'),
        'clearances': raw.get('clearances'),
        'blocked_shots': raw.get('blockedShots'),
        'errors_led_to_goal': raw.get('errorLeadToGoal'),
        'errors_led_to_shot': raw.get('errorLeadToShot'),
        'ball_recovery': raw.get('ballRecovery'),
        'possession_won_att_third': raw.get('possessionWonAttThird'),
        'touches': raw.get('touches'),
        'possession_lost': raw.get('possessionLost'),
        'yellow_cards': raw.get('yellowCards'),
        'yellow_red_cards': raw.get('yellowRedCards'),
        'red_cards': raw.get('redCards'),
        'direct_red_cards': raw.get('directRedCards'),
        'fouls_committed': raw.get('fouls'),
        'fouls_won': raw.get('wasFouled'),
        'offsides': raw.get('offsides'),
        'saves': raw.get('saves'),
        'saves_caught': raw.get('savesCaught'),
        'saves_parried': raw.get('savesParried'),
        'goals_conceded': raw.get('goalsConceded'),
        'goals_conceded_inside_box': raw.get('goalsConcededInsideTheBox'),
        'goals_conceded_outside_box': raw.get('goalsConcededOutsideTheBox'),
        'clean_sheets': raw.get('cleanSheet'),
        'penalty_saved': raw.get('penaltySave'),
        'penalty_faced': raw.get('penaltyFaced'),
        'high_claims': raw.get('highClaims'),
        'punches': raw.get('punches'),
        'runs_out': raw.get('runsOut'),
        'successful_runs_out': raw.get('successfulRunsOut'),
        'saved_shots_inside_box': raw.get('savedShotsFromInsideTheBox'),
        'saved_shots_outside_box': raw.get('savedShotsFromOutsideTheBox'),
        'goal_kicks': raw.get('goalKicks'),
        'crosses_not_claimed': raw.get('crossesNotClaimed'),
        'penalty_attempt_miss': raw.get('attemptPenaltyMiss'),
        'penalty_attempt_post': raw.get('attemptPenaltyPost'),
        'penalty_attempt_target': raw.get('attemptPenaltyTarget'),
    }


def _map_profile(p: dict) -> dict:
    contract_str = None
    ct = p.get('contractUntilTimestamp')
    if ct:
        try:
            contract_str = datetime.fromtimestamp(ct, tz=timezone.utc).strftime('%Y-%m-%d')
        except Exception:
            pass
    mv = p.get('proposedMarketValue') or p.get('marketValue')
    mv_millions = round(float(mv) / 1_000_000, 2) if mv else None
    dob_str = None
    dob = p.get('dateOfBirth')
    if dob and isinstance(dob, str):
        dob_str = dob[:10]
    return {
        'sofascore_id': p.get('id'),
        'height_cm': p.get('height'),
        'weight_kg': p.get('weight'),
        'preferred_foot': p.get('preferredFoot'),
        'jersey_number': p.get('jerseyNumber') or p.get('shirtNumber'),
        'contract_until': contract_str,
        'market_value': mv_millions,
        'nationality': p.get('country', {}).get('name'),
        'date_of_birth': dob_str,
        'position': p.get('position'),
        'position_detail': ','.join(p.get('positionsDetailed', [])),
        'gender': p.get('gender', 'M'),
        'slug': p.get('slug'),
        'short_name': p.get('shortName'),
        'club': p.get('team', {}).get('name'),
        'club_id': p.get('team', {}).get('id'),
    }


def _map_matches(matches_raw: list) -> list:
    result = []
    for m in matches_raw:
        t = m.get('tournament', {})
        ut = t.get('uniqueTournament', {})
        s = m.get('season', {})
        ps = m.get('playerStatistics', {})
        ri = m.get('roundInfo', {})
        match_date = None
        ts = m.get('startTimestamp')
        if ts:
            try:
                match_date = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                pass
        result.append({
            'event_id': m.get('id'),
            'sofascore_slug': m.get('slug'),
            'date': match_date,
            'tournament_name': ut.get('name') or t.get('name', ''),
            'tournament_id': ut.get('id'),
            'season_name': s.get('name', ''),
            'season_year': s.get('year', ''),
            'season_id': s.get('id'),
            'round': ri.get('round'),
            'home_team': m.get('homeTeam', {}).get('name', ''),
            'home_team_id': m.get('homeTeam', {}).get('id'),
            'away_team': m.get('awayTeam', {}).get('name', ''),
            'away_team_id': m.get('awayTeam', {}).get('id'),
            'home_score': m.get('homeScore', {}).get('current'),
            'away_score': m.get('awayScore', {}).get('current'),
            'winner_code': m.get('winnerCode'),
            'status': m.get('status', {}).get('type', ''),
            'has_xg': m.get('hasXg', False),
            'has_player_stats': m.get('hasEventPlayerStatistics', False),
            'has_heatmap': m.get('hasEventPlayerHeatMap', False),
            'rating': ps.get('rating'),
            'minutes_played': ps.get('minutesPlayed'),
            'goals': ps.get('goals', 0),
            'assists': ps.get('goalAssist', 0),
            'yellow_card': bool(ps.get('yellowCard', False)),
            'red_card': bool(ps.get('redCard', False)),
        })
    return result


def _map_transfers(transfers_raw: list) -> list:
    TYPE_MAP = {1: 'Transfer', 2: 'Loan', 3: 'Free', 4: 'Youth', 5: 'Return from loan'}
    result = []
    for t in transfers_raw:
        transfer_date = None
        ts = t.get('transferDateTimestamp')
        if ts:
            try:
                transfer_date = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                pass
        type_code = t.get('type', 0)
        result.append({
            'transfer_id': t.get('id'),
            'from_team': t.get('fromTeamName') or t.get('transferFrom', {}).get('name', ''),
            'to_team': t.get('toTeamName') or t.get('transferTo', {}).get('name', ''),
            'from_team_id': t.get('transferFrom', {}).get('id'),
            'to_team_id': t.get('transferTo', {}).get('id'),
            'transfer_date': transfer_date,
            'fee': t.get('transferFee'),
            'fee_description': t.get('transferFeeDescription', ''),
            'transfer_type': TYPE_MAP.get(type_code, str(type_code)),
            'type_code': type_code,
        })
    return result


def _map_national(nat_raw) -> list:
    entries = nat_raw if isinstance(nat_raw, list) else [nat_raw]
    result = []
    for entry in entries:
        if not entry:
            continue
        team = entry.get('team', {})
        stats = entry.get('statistics', {})
        debut_str = None
        dt = entry.get('debutTimestamp')
        if dt:
            try:
                debut_str = datetime.fromtimestamp(dt, tz=timezone.utc).strftime('%Y-%m-%d')
            except Exception:
                pass
        result.append({
            'national_team': team.get('name', ''),
            'national_team_id': team.get('id'),
            'appearances': entry.get('appearances') or stats.get('appearances'),
            'goals': entry.get('goals') or stats.get('goals'),
            'assists': stats.get('goalAssist'),
            'minutes': stats.get('minutesPlayed'),
            'rating': stats.get('rating'),
            'yellow_cards': stats.get('yellowCards'),
            'red_cards': stats.get('redCards'),
            'debut_date': debut_str,
        })
    return result


def build_payload(job: PlayerJob, data: dict) -> dict:
    profile_mapped = _map_profile(data.get('profile', {}))
    competitions_mapped = []
    for comp in data.get('competitions', []):
        stats_mapped = _map_stats(comp.get('statistics', {}))
        n_vals = len([v for v in stats_mapped.values() if v is not None])
        competitions_mapped.append({
            'tournament_id': comp['tournament_id'],
            'season_id': comp['season_id'],
            'tournament_name': comp['tournament_name'],
            'season_year': comp['season_year'],
            'season_name': comp.get('season_name', ''),
            'statistics': stats_mapped,
            'heatmap_points': comp.get('heatmap_points', []),
        })
        log.info(f'  [MAP] {comp["tournament_name"]} {comp["season_year"]}: '
                 f'{n_vals} stats, {len(comp.get("heatmap_points", []))} heatmap pts')

    matches_mapped = _map_matches(data.get('matches', []))
    transfers_mapped = _map_transfers(data.get('transfers', []))
    national_mapped = _map_national(data.get('national_stats', []))

    return {
        'name': job.name,
        'club': job.club,
        'db_id': job.db_id,
        'sofascore_id': job.sofascore_id,
        'source': 'playwright_v9',
        'extracted': {
            'profile': profile_mapped,
            'attributes': data.get('attributes', {}),
            'competitions': competitions_mapped,
            'matches': matches_mapped,
            'career': transfers_mapped,
            'national': national_mapped,
        },
        'extracted_at': datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════
# BACKEND  (invariato)
# ══════════════════════════════════════════════════════════════════

def send_to_backend(job: PlayerJob) -> bool:
    import requests as req
    if not job.data_fetched:
        log.warning(f'  Nessun dato per {job.name}')
        return False
    payload = build_payload(job, job.data_fetched)
    log.info(f'  [BACKEND] POST /ingest/sofascore/ocr')
    try:
        resp = req.post(f'{BACKEND_URL}/ingest/sofascore/ocr', json=payload, timeout=30)
        if resp.status_code == 200:
            log.info(f'  [BACKEND] OK: {resp.json()}')
            _update_player_done(job)
            _save_fallback(job, payload)
            return True
        else:
            log.error(f'  [BACKEND] HTTP {resp.status_code}: {resp.text[:300]}')
            _save_fallback(job, payload)
            return False
    except Exception as e:
        log.error(f'  [BACKEND] Errore: {e}')
        _save_fallback(job, payload)
        return False


def _update_player_done(job: PlayerJob):
    import requests as req
    try:
        req.post(f'{BACKEND_URL}/ingest/sofascore/player-done', json={
            'name': job.name, 'club': job.club, 'db_id': job.db_id,
            'sofascore_id': job.sofascore_id,
            'completed_at': datetime.utcnow().isoformat(),
        }, timeout=10)
    except Exception as e:
        log.warning(f'  [BACKEND] player-done errore: {e}')


def _save_fallback(job: PlayerJob, payload: dict):
    fallback_dir = Path('sofascore_fallback')
    fallback_dir.mkdir(exist_ok=True)
    safe_name = re.sub(r'[^\w]', '_', job.name)
    path = fallback_dir / f'{safe_name}_{job.sofascore_id}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({
            'meta': {
                'name': job.name,
                'sofascore_id': job.sofascore_id,
                'league': job.league_key,
                'saved_at': datetime.utcnow().isoformat(),
                'rpa_version': 'v9.5-fast',
            },
            'raw_data': job.data_fetched,
            'mapped_payload': payload,
        }, f, indent=2, ensure_ascii=False, default=str)
    log.info(f'  [FALLBACK] Salvato: {path}')


# ══════════════════════════════════════════════════════════════════
# PROCESSO PRINCIPALE  (invariato)
# ══════════════════════════════════════════════════════════════════

async def process_player(job: PlayerJob, client: SofaPlaywrightClient) -> bool:
    job.started_at = datetime.now().isoformat()
    log.info(f'── {job.name} ({job.club or "N/D"}) ──')
    log.info(f'  sofascore_id={job.sofascore_id} league={job.league_key}')

    if not job.sofascore_id:
        job.sofascore_id = await client.search_player_id(job.name, job.club)
        if not job.sofascore_id:
            job.status = 'skipped'
            job.error = 'ID non trovato'
            log.warning(f'  Non trovato: {job.name}')
            return False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = await client.fetch_player_data(job.sofascore_id, job.league_key)
            job.data_fetched = data
            ok = send_to_backend(job)
            job.status = 'done' if ok else 'done_fallback'
            job.completed_at = datetime.now().isoformat()
            n_c = len(data.get('competitions', []))
            n_s = sum(len(c['statistics']) for c in data.get('competitions', []))
            n_heat = sum(len(c['heatmap_points']) for c in data.get('competitions', []))
            n_attrs = len([v for v in data.get('attributes', {}).values() if v is not None])
            log.info(
                f'✓ {job.name} — competizioni={n_c} stats={n_s} '
                f'heatmap={n_heat} attributi={n_attrs} '
                f'partite={len(data.get("matches", []))} '
                f'trasferimenti={len(data.get("transfers", []))}'
            )
            return True
        except Exception as e:
            log.error(f'  Tentativo {attempt}/{MAX_RETRIES}: {e}', exc_info=True)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(DELAY_BETWEEN_PLAYERS * 2)

    job.status = 'failed'
    job.error = f'Fallito dopo {MAX_RETRIES} tentativi'
    return False


async def run_async(jobs: list) -> dict:
    if not jobs:
        log.warning('Nessun giocatore')
        return {}
    started = datetime.now()
    client = SofaPlaywrightClient()
    log.info(f'Avvio RPA v9.5-fast: {len(jobs)} giocatori')
    log.info(f'Backend: {BACKEND_URL}')
    await client.start()
    try:
        for idx, job in enumerate(jobs, 1):
            log.info(f'[{idx}/{len(jobs)}] {job.name}')
            await process_player(job, client)
            if idx < len(jobs):
                await asyncio.sleep(DELAY_BETWEEN_PLAYERS)
    finally:
        await client.stop()

    duration = (datetime.now() - started).total_seconds()
    done = sum(1 for j in jobs if 'done' in j.status)
    failed = sum(1 for j in jobs if j.status == 'failed')
    skipped = sum(1 for j in jobs if j.status == 'skipped')
    report = {
        'total': len(jobs),
        'done': done,
        'failed': failed,
        'skipped': skipped,
        'duration_minutes': round(duration / 60, 1),
        'avg_sec_player': round(duration / len(jobs), 1),
    }
    log.info('═' * 50)
    log.info('REPORT FINALE')
    for k, v in report.items():
        log.info(f'  {k}: {v}')
    log.info('═' * 50)

    report_path = f'rpa_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            'report': report,
            'players': [{
                'name': j.name,
                'sofascore_id': j.sofascore_id,
                'league': j.league_key,
                'status': j.status,
                'error': j.error,
                'competitions': len(j.data_fetched.get('competitions', [])),
                'matches': len(j.data_fetched.get('matches', [])),
                'transfers': len(j.data_fetched.get('transfers', [])),
                'attributes': len([v for v in j.data_fetched.get('attributes', {}).values()
                                   if v is not None]),
                'started_at': j.started_at,
                'completed_at': j.completed_at,
            } for j in jobs],
        }, f, indent=2, ensure_ascii=False)
    log.info(f'Report: {report_path}')
    return report


def run(jobs: list) -> dict:
    return asyncio.run(run_async(jobs))


# ══════════════════════════════════════════════════════════════════
# CLI  (invariata)
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='SofaScore RPA v9.5-fast')
    parser.add_argument('--source', choices=['db', 'csv', 'single'], default='db')
    parser.add_argument('--league', default='serie_a')
    parser.add_argument('--file', help='CSV: name,club,sofascore_id,league')
    parser.add_argument('--name')
    parser.add_argument('--club', default='')
    parser.add_argument('--sofascore-id', type=int, dest='sofascore_id')
    parser.add_argument('--only-missing', action='store_true', default=False)
    parser.add_argument('--backend', default=None)
    args = parser.parse_args()

    if args.backend:
        global BACKEND_URL
        BACKEND_URL = args.backend

    if args.source == 'db':
        jobs = load_from_db(args.league, args.only_missing)
    elif args.source == 'csv':
        if not args.file:
            parser.error('--file richiesto')
        jobs = load_from_csv(args.file, args.league)
    else:
        if not args.name and not args.sofascore_id:
            parser.error('--name o --sofascore-id richiesto')
        jobs = load_single(
            name=args.name or '', club=args.club,
            sofascore_id=args.sofascore_id, league=args.league,
        )

    if not jobs:
        log.info('Nessun giocatore. Uscita.')
        return

    run(jobs)

    print('\n' + '=' * 50)
    print('✅ Download completato. Avvio ricalcolo score...')
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from app.database import SessionLocal
        from app.services.scoring import recalculate_all
        from app.services.percentiles import recalculate_percentiles
        db = SessionLocal()
        n = recalculate_all(db)
        pct = recalculate_percentiles(db)
        print(f'✅ Score: {n} giocatori aggiornati.')
        print(f'✅ Percentili: {pct.get("players_updated", 0)} aggiornati.')
        db.close()
    except Exception as e:
        print(f'❌ Ricalcolo errore: {e}')
    print('=' * 50 + '\n')


if __name__ == '__main__':
    main()