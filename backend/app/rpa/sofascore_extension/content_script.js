/**
 * content_script.js
 * Iniettato su www.sofascore.com — intercetta TUTTE le chiamate
 * a api.sofascore.com e le forwarda al background service worker.
 *
 * Tecnica: monkey-patch di window.fetch e XMLHttpRequest PRIMA
 * che la pagina li usi, così catturiamo ogni risposta JSON.
 */

(function () {
  'use strict';

  // ── Endpoint SofaScore che ci interessano ─────────────────────
  const PATTERNS = [
    /\/api\/v1\/player\/(\d+)$/,                          // profilo
    /\/api\/v1\/player\/(\d+)\/tournaments\/\d+\/seasons\/\d+\/statistics/,  // stats stagione
    /\/api\/v1\/player\/(\d+)\/heatmap\//,                // heatmap stagione
    /\/api\/v1\/event\/\d+\/player\/(\d+)\/heatmap/,      // heatmap singola partita
    /\/api\/v1\/player\/(\d+)\/events\//,                 // partite recenti
    /\/api\/v1\/player\/(\d+)\/transfer-history/,         // trasferimenti
    /\/api\/v1\/player\/(\d+)\/national-team-statistics/, // nazionale
    /\/api\/v1\/event\/(\d+)\/lineups/,                   // formazioni partita
    /\/api\/v1\/event\/(\d+)\/statistics/,                // stats partita
    /\/api\/v1\/unique-tournament\/\d+\/season\/\d+\/top-players\//,  // top giocatori
    /\/api\/v1\/search\/all/,                             // ricerca per nome
  ];

  function shouldCapture(url) {
    return PATTERNS.some(p => p.test(url));
  }

  function classifyUrl(url) {
    if (/\/player\/\d+$/.test(url))                        return 'player_profile';
    if (/\/statistics/.test(url) && /\/player\//.test(url)) return 'player_season_stats';
    if (/\/heatmap/.test(url) && /\/player\//.test(url))   return 'player_heatmap';
    if (/\/heatmap/.test(url) && /\/event\//.test(url))    return 'match_heatmap';
    if (/\/events\//.test(url))                            return 'player_matches';
    if (/\/transfer-history/.test(url))                    return 'transfers';
    if (/\/national-team/.test(url))                       return 'national_stats';
    if (/\/lineups/.test(url))                             return 'match_lineups';
    if (/\/event\/\d+\/statistics/.test(url))              return 'match_stats';
    if (/\/top-players/.test(url))                         return 'top_players';
    if (/\/search\/all/.test(url))                         return 'search';
    return 'unknown';
  }

  function extractIds(url) {
    const ids = {};
    const playerMatch = url.match(/\/player\/(\d+)/);
    if (playerMatch) ids.player_id = parseInt(playerMatch[1]);
    const eventMatch = url.match(/\/event\/(\d+)/);
    if (eventMatch) ids.event_id = parseInt(eventMatch[1]);
    const tournamentMatch = url.match(/\/tournaments\/(\d+)/);
    if (tournamentMatch) ids.tournament_id = parseInt(tournamentMatch[1]);
    const seasonMatch = url.match(/\/seasons\/(\d+)/);
    if (seasonMatch) ids.season_id = parseInt(seasonMatch[1]);
    return ids;
  }

  function sendToBackground(url, data) {
    const payload = {
      type:      classifyUrl(url),
      url:       url,
      ids:       extractIds(url),
      data:      data,
      captured_at: new Date().toISOString(),
      page_url:  window.location.href,
    };
    // Invia al background service worker tramite chrome.runtime
    chrome.runtime.sendMessage({ action: 'sofa_data', payload });
  }

  // ── Patch window.fetch ────────────────────────────────────────
  const _fetch = window.fetch.bind(window);
  window.fetch = async function (...args) {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
    const response = await _fetch(...args);

    if (shouldCapture(url)) {
      try {
        const clone = response.clone();
        const ct = clone.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          clone.json().then(data => sendToBackground(url, data)).catch(() => {});
        }
      } catch (_) {}
    }
    return response;
  };

  // ── Patch XMLHttpRequest ──────────────────────────────────────
  const _open = XMLHttpRequest.prototype.open;
  const _send = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._scoutUrl = url;
    return _open.call(this, method, url, ...rest);
  };

  XMLHttpRequest.prototype.send = function (...args) {
    if (this._scoutUrl && shouldCapture(this._scoutUrl)) {
      const url = this._scoutUrl;
      this.addEventListener('load', function () {
        try {
          const data = JSON.parse(this.responseText);
          sendToBackground(url, data);
        } catch (_) {}
      });
    }
    return _send.apply(this, args);
  };

  // ── Segnala alla pagina che l'estensione è attiva ─────────────
  window.__scoutInterceptorActive = true;
  console.log('[Scout Interceptor] attivo su', window.location.hostname);

})();