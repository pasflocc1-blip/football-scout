/**
 * background.js — Service Worker MV3
 *
 * Riceve i payload dal content script e li manda al backend FastAPI.
 * Gestisce: queue, retry, configurazione URL backend, deduplicazione.
 */

'use strict';

// ── Configurazione ────────────────────────────────────────────────
const DEFAULT_BACKEND = 'http://backend:8000';
const ENDPOINT        = '/ingest/sofascore/raw';
const RETRY_DELAY_MS  = 2000;
const MAX_RETRIES     = 3;

// Cache per evitare di mandare duplicati nella stessa sessione
// (SofaScore fa spesso la stessa chiamata più volte)
const _sent = new Set();

function dedupeKey(payload) {
  // Aggiungi un timestamp per forzare l'invio ogni volta durante il debug
  return `${payload.type}:${payload.url}:${Date.now()}`;
}

// ── Legge il backend URL da storage (configurabile dal popup) ─────
async function getBackendUrl() {
  return new Promise(resolve => {
    chrome.storage.local.get(['backendUrl'], result => {
      resolve(result.backendUrl || DEFAULT_BACKEND);
    });
  });
}

// ── Invia al backend con retry ────────────────────────────────────
async function sendToBackend(payload, attempt = 1) {
  const key = dedupeKey(payload);
  if (_sent.has(key)) return; // già inviato

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
      console.log(`[Scout BG] ✓ ${payload.type} player_id=${payload.ids?.player_id} →`, result);
    } else {
      throw new Error(`HTTP ${resp.status}`);
    }
  } catch (err) {
    if (attempt < MAX_RETRIES) {
      console.warn(`[Scout BG] retry ${attempt}/${MAX_RETRIES} per ${payload.type}:`, err.message);
      setTimeout(() => sendToBackend(payload, attempt + 1), RETRY_DELAY_MS * attempt);
    } else {
      console.error(`[Scout BG] ✗ fallito dopo ${MAX_RETRIES} tentativi:`, payload.type, err.message);
      // Salva in storage locale come fallback
      saveFailedPayload(payload);
    }
  }
}

// ── Salva i payload falliti per retry manuale ─────────────────────
async function saveFailedPayload(payload) {
  const existing = await new Promise(resolve => {
    chrome.storage.local.get(['failedPayloads'], r => resolve(r.failedPayloads || []));
  });
  existing.push({ ...payload, failed_at: new Date().toISOString() });
  // Mantieni solo gli ultimi 100 fallimenti
  const trimmed = existing.slice(-100);
  chrome.storage.local.set({ failedPayloads: trimmed });
}

// ── Listener messaggi dal content script ─────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'sofa_data') {
    const payload = {
      ...message.payload,
      tab_id: sender.tab?.id,
      tab_url: sender.tab?.url,
    };
    sendToBackend(payload);
    sendResponse({ received: true });
  }

  // Popup: richiesta status
  if (message.action === 'get_status') {
    chrome.storage.local.get(['failedPayloads'], result => {
      sendResponse({
        sent_count:   _sent.size,
        failed_count: (result.failedPayloads || []).length,
        backend:      DEFAULT_BACKEND,
      });
    });
    return true; // async response
  }

  // Popup: retry falliti
  if (message.action === 'retry_failed') {
    chrome.storage.local.get(['failedPayloads'], async result => {
      const failed = result.failedPayloads || [];
      chrome.storage.local.set({ failedPayloads: [] });
      for (const p of failed) {
        await sendToBackend(p);
        await new Promise(r => setTimeout(r, 500));
      }
      sendResponse({ retried: failed.length });
    });
    return true;
  }

  // RPA: segnale "navigazione completata per giocatore X"
  if (message.action === 'rpa_player_done') {
    console.log(`[Scout BG] RPA: giocatore ${message.player_id} completato`);
    sendResponse({ ok: true });
  }
});

// ── Listener per cambio configurazione backend ────────────────────
chrome.storage.onChanged.addListener((changes) => {
  if (changes.backendUrl) {
    console.log('[Scout BG] Backend URL aggiornato:', changes.backendUrl.newValue);
  }
});

console.log('[Scout BG] Service worker avviato');