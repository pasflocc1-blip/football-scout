# ─────────────────────────────────────────────────────────────────
# Backend Dockerfile — FastAPI
# Funziona identico su Windows (build) e Mac (run)
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

# Imposta variabili d'ambiente per comportamento consistente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
	
WORKDIR /app

# Imposta la variabile d'ambiente per il percorso dei browser
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Installa dipendenze di sistema (stesso layer cacheable)
RUN apt-get update && apt-get install -y \
	xvfb \
    libxml2-dev libxslt1-dev gcc \
    wget gnupg ca-certificates \
    fonts-liberation \
    fonts-unifont \
    fonts-noto-color-emoji \
    libappindicator3-1 libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 \
    libglib2.0-0 libnspr4 libnss3 libx11-xcb1 libxcb-dri3-0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxss1 \
    libxtst6 xdg-utils \
	--no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Installa dipendenze Python prima del codice (cache Docker layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Assicurati che playwright sia installato (se non è già in requirements.txt)
RUN pip install playwright playwright-stealth google-generativeai
# Scarica il browser Chromium dentro l'immagine Docker
RUN playwright install chromium

# Copia il codice sorgente
COPY . .

EXPOSE 8000

# In sviluppo viene sovrascritto da docker-compose.yml (--reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
