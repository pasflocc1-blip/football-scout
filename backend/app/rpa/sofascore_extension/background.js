/**
 * background.js — Service Worker MV3 v2.1
 *
 * FIX rispetto alla v2.0:
 *   1. DEFAULT_BACKEND confermato a http://backend:8000 per Docker
 *   2. Aggiunto listener 'service_worker_ready' per permettere al RPA
 *      di sapere quando il SW è attivo prima di tentare chrome.storage
 *   3. Aggiunto messaggio 'set_backend' per permettere al RPA di impostare
 *      il backend tramite messaggio invece di chrome.storage.local.set()
 *      dal contesto pagina (che non ha accesso a chrome.storage)
 */

'use strict';

const DEFAULT_BACKEND = 'http://backend:8000';  // ← Docker internal hostname
const ENDPOINT        = '/ingest/sofascore/raw';
const RETRY_DELAY_MS  = 2000;
const MAX_RETRIES     = 3;

const _sent    = new Set();
let   _counter = 0;

function dedupeKey(payload) {
  return `${payload.type}:${payload.url}`;
}

async function getBackendUrl() {
  return new Promise(resolve => {
    chrome.storage.local.get(['backendUrl'], result => {
      resolve(result.backendUrl || DEFAULT_BACKEND);
    });
  });
}

async function sendToBackend(payload, attempt = 1) {
  const key = dedupeKey(payload);
  if (_sent.has(key)) {
    console.debug(`[Scout BG] skip duplicato: ${key}`);
    return;
  }

  const backendUrl = await getBackendUrl();
  const url = `${backendUrl}${ENDPOINT}`;

  try {
    const resp = await fetch(url, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    if (resp.ok) {
      _sent.add(key);
      const result = await resp.json();
      console.log(
        `[Scout BG] ✓ [${_counter}] ${payload.type}`,
        `player_id=${payload.ids?.player_id ?? '-'}`,
        `→ matched=${result.matched ?? result.status}`
      );
    } else {
      throw new Error(`HTTP ${resp.status}`);
    }
  } catch (err) {
    if (attempt < MAX_RETRIES) {
      console.warn(`[Scout BG] retry ${attempt}/${MAX_RETRIES} ${payload.type}: ${err.message}`);
      setTimeout(() => sendToBackend(payload, attempt + 1), RETRY_DELAY_MS * attempt);
    } else {
      console.error(`[Scout BG] ✗ fallito: ${payload.type} — ${err.message}`);
      saveFailedPayload(payload);
    }
  }
}

async function saveFailedPayload(payload) {
  const existing = await new Promise(resolve =>
    chrome.storage.local.get(['failedPayloads'], r => resolve(r.failedPayloads || []))
  );
  existing.push({ ...payload, failed_at: new Date().toISOString() });
  chrome.storage.local.set({ failedPayloads: existing.slice(-100) });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

  if (message.action === 'sofa_data') {
    _counter++;
    const payload = {
      ...message.payload,
      tab_id:  sender.tab?.id,
      tab_url: sender.tab?.url,
    };
    console.log(`[Scout BG] ricevuto #${_counter}: ${payload.type} — ${payload.url.slice(-60)}`);
    sendToBackend(payload);
    sendResponse({ received: true, count: _counter });
    return;
  }

  // FIX-3: Il RPA può impostare il backend via messaggio invece di chrome.storage.set()
  // dal contesto pagina (che non funziona). Il content script fa da ponte.
  if (message.action === 'set_backend') {
    const newUrl = message.backendUrl;
    if (newUrl) {
      chrome.storage.local.set({ backendUrl: newUrl }, () => {
        console.log(`[Scout BG] Backend URL aggiornato → ${newUrl}`);
        sendResponse({ ok: true, backendUrl: newUrl });
      });
      return true; // risposta asincrona
    }
    sendResponse({ ok: false, error: 'backendUrl mancante' });
    return;
  }

  // FIX-4: Il RPA può verificare se il SW è attivo
  if (message.action === 'ping') {
    sendResponse({ ok: true, backend: DEFAULT_BACKEND, version: '2.1' });
    return;
  }

  if (message.action === 'get_status') {
    chrome.storage.local.get(['failedPayloads', 'backendUrl'], result => {
      sendResponse({
        sent_count:   _sent.size,
        recv_count:   _counter,
        failed_count: (result.failedPayloads || []).length,
        backend:      result.backendUrl || DEFAULT_BACKEND,
      });
    });
    return true;
  }

  if (message.action === 'retry_failed') {
    chrome.storage.local.get(['failedPayloads'], async result => {
      const failed = result.failedPayloads || [];
      chrome.storage.local.set({ failedPayloads: [] });
      for (const p of failed) {
        _sent.delete(dedupeKey(p));
        await sendToBackend(p);
        await new Promise(r => setTimeout(r, 500));
      }
      sendResponse({ retried: failed.length });
    });
    return true;
  }

  if (message.action === 'reset_cache') {
    _sent.clear();
    _counter = 0;
    console.log('[Scout BG] Cache deduplicazione resettata');
    sendResponse({ ok: true });
    return;
  }

  if (message.action === 'rpa_player_done') {
    console.log(`[Scout BG] Giocatore completato: ${message.player_name || message.player_id}`);
    sendResponse({ ok: true });
    return;
  }
});

chrome.storage.onChanged.addListener((changes) => {
  if (changes.backendUrl) {
    console.log('[Scout BG] Backend URL → ', changes.backendUrl.newValue);
  }
});

console.log(`[Scout BG] Service worker v2.1 avviato — default backend: ${DEFAULT_BACKEND}`);