#!/bin/bash
# run_rpa.sh — v2.1
# FIX: Xvfb più robusto — gestisce correttamente il caso in cui :99 sia già occupato
set -e

export PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ── Cleanup Xvfb precedente ────────────────────────────────────────
# Trova e termina tutti i processi Xvfb esistenti
pkill -9 -x Xvfb 2>/dev/null || true
sleep 1

# Rimuovi i lock per tutti i display da :90 a :99
for d in $(seq 90 99); do
    rm -f "/tmp/.X${d}-lock" 2>/dev/null || true
done

# ── Trova un display libero ────────────────────────────────────────
DISPLAY_NUM=99
for d in $(seq 99 -1 90); do
    if ! ls /tmp/.X${d}-lock 2>/dev/null; then
        DISPLAY_NUM=$d
        break
    fi
done

echo "[run_rpa.sh] Usando DISPLAY :${DISPLAY_NUM}"

# ── Avvia Xvfb ────────────────────────────────────────────────────
Xvfb :${DISPLAY_NUM} -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Aspetta che Xvfb sia pronto (massimo 5 secondi)
for i in $(seq 1 10); do
    if xdpyinfo -display :${DISPLAY_NUM} >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

export DISPLAY=:${DISPLAY_NUM}

echo "[run_rpa.sh] Xvfb avviato (PID=$XVFB_PID) su DISPLAY=$DISPLAY"
echo "[run_rpa.sh] Avvio RPA: $@"

# ── Esegui RPA ────────────────────────────────────────────────────
# Trap per cleanup anche in caso di errore
cleanup() {
    echo "[run_rpa.sh] Cleanup Xvfb (PID=$XVFB_PID)..."
    kill $XVFB_PID 2>/dev/null || true
}
trap cleanup EXIT

python app/rpa/sofascore_rpa.py "$@"

echo "[run_rpa.sh] Completato."

# ── UTILIZZO ──────────────────────────────────────────────────────
# Giocatore singolo:
# docker compose exec backend bash app/rpa/run_rpa.sh \
#   --source single --name "Zeki Amdouni" --sofascore-id 990550 \
#   --backend http://backend:8000
#
# Da DB:
# docker compose exec backend bash app/rpa/run_rpa.sh \
#   --source db --league serie_a --backend http://backend:8000
#
# Da CSV:
# docker compose exec backend bash app/rpa/run_rpa.sh \
#   --source csv --file /app/giocatori.csv --backend http://backend:8000