# ─────────────────────────────────────────────────────────────────
# Backend Dockerfile — FastAPI
# Funziona identico su Windows (build) e Mac (run)
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Imposta variabili d'ambiente per comportamento consistente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Installa dipendenze di sistema (stesso layer cacheable)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Installa dipendenze Python prima del codice (cache Docker layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice sorgente
COPY . .

EXPOSE 8000

# In sviluppo viene sovrascritto da docker-compose.yml (--reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
