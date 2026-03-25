1 — Come modificare/inserire le ricerche intelligentiLe ricerche intelligenti si trovano in un unico file:backend/app/services/search.py


Regole:

La chiave (a sinistra) è la frase che l'utente digita — minuscolo, il sistema è case-insensitive
Il valore (a destra) è la condizione SQLAlchemy — usa i campi della tabella scouting_players
Non serve riavviare il database — solo riavviare il backend con python -m uvicorn app.main:app --reload
Il --reload lo fa automaticamente se è già avviato in modalità sviluppo

Campi disponibili per le condizioni:
Campo Cosa misura
M.paceVelocità (0-100)
M.shootingTiro (0-100)
M.passingPassaggi (0-100)
M.dribblingDribbling (0-100)
M.defendingDifesa (0-100)
M.physicalFisico (0-100)
M.heading_scoreScore testa calcolato (0-100)
M.build_up_scoreScore gioco calcolato (0-100)
M.defensive_scoreScore difesa calcolato (0-100)
M.ageEtàM.preferred_foot"Left" o "Right"
M.position"ST", "CM", "CB", "GK", ecc.M.nationalityEs. "Italiana"
M.xg_per90Expected Goals per 90 minM.xa_per90Expected Assists per 90 min






Ottimo riepilogo richiesto. Rispondo punto per punto in modo chiaro e diretto.

---

## 1 — Come modificare/inserire le ricerche intelligenti

Le ricerche intelligenti si trovano in un unico file:

```
backend/app/services/search.py
```

Apri quel file e trovi questa struttura:

```python
SEMANTIC_MAP: dict = {
    "bravo di testa":    lambda: M.heading_score > 75,
    "forte fisicamente": lambda: M.physical > 80,
    "veloce":            lambda: M.pace > 80,
    "mancino":           lambda: M.preferred_foot == "Left",
    "centravanti":       lambda: M.position == "ST",
    "giovane":           lambda: M.age <= 23,
    ...
}
```

**Per aggiungere una nuova keyword** basta aggiungere una riga:

```python
"tecnico":        lambda: M.dribbling > 82,
"forte in area":  lambda: M.shooting > 78,
"under 23":       lambda: M.age <= 23,
"italiano":       lambda: M.nationality.ilike("%italian%"),
```

**Regole:**
- La chiave (a sinistra) è la frase che l'utente digita — minuscolo, il sistema è case-insensitive
- Il valore (a destra) è la condizione SQLAlchemy — usa i campi della tabella `scouting_players`
- **Non serve riavviare il database** — solo riavviare il backend con `python -m uvicorn app.main:app --reload`
- Il `--reload` lo fa automaticamente se è già avviato in modalità sviluppo

**Campi disponibili per le condizioni:**

| Campo | Cosa misura |
|-------|-------------|
| `M.pace` | Velocità (0-100) |
| `M.shooting` | Tiro (0-100) |
| `M.passing` | Passaggi (0-100) |
| `M.dribbling` | Dribbling (0-100) |
| `M.defending` | Difesa (0-100) |
| `M.physical` | Fisico (0-100) |
| `M.heading_score` | Score testa calcolato (0-100) |
| `M.build_up_score` | Score gioco calcolato (0-100) |
| `M.defensive_score` | Score difesa calcolato (0-100) |
| `M.age` | Età |
| `M.preferred_foot` | "Left" o "Right" |
| `M.position` | "ST", "CM", "CB", "GK", ecc. |
| `M.nationality` | Es. "Italiana" |
| `M.xg_per90` | Expected Goals per 90 min |
| `M.xa_per90` | Expected Assists per 90 min |

---

## 2 — A quale campionato e anno appartengono i dati demo

I **4 giocatori demo** che vedi ora sono quelli inseriti manualmente in `scripts/init.sql` — sono dati inventati, non reali.

Per i dati reali, dipende dalla fonte:

| Fonte | Campionato | Anno |
|-------|-----------|------|
| **Kaggle FIFA 22** | Tutti i campionati principali mondiali | Stagione **2021/2022** |
| **Kaggle FIFA 23** | Tutti i campionati principali mondiali | Stagione **2022/2023** |
| **API-Football** | Configurabile per lega (es. 135 = Serie A) | **Stagione attuale** (live) |
| **StatsBomb Open Data** | Serie A, Champions League, Mondiali (dati selezionati) | Varie stagioni, fino al **2023** |

**Risposta diretta:** con il dataset Kaggle FIFA 22 (quello che abbiamo usato come esempio) i dati sono della stagione 2021/2022. Se vuoi dati più recenti devi usare **API-Football** oppure il dataset **FIFA 23/24** su Kaggle.

---

## 3 — Servizi di aggiornamento automatico dei dati

Al momento nel progetto **non è attivo nessun aggiornamento automatico** — l'import va lanciato manualmente. Ecco cosa esiste e come si attiva:

### 3a — Import manuale (già funzionante)

```powershell
# Kaggle CSV
docker compose exec backend python -m app.services.ingest --source kaggle --file /app/data/players_22.csv

# API-Football (richiede API key nel .env)
docker compose exec backend python -m app.services.ingest --source api --league 135 --season 2024
```

### 3b — Aggiornamento automatico schedulato (da attivare)

Per attivarlo devi aggiungere uno scheduler nel backend. Il modo più semplice con FastAPI è usare **APScheduler**. Aggiungi al `requirements.txt`:

```
apscheduler==3.10.4
```

Poi aggiungi in `backend/app/main.py`:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.ingest import fetch_from_api_football
from app.services.scoring import recalculate_all
from app.database import SessionLocal

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=3, minute=0)  # ogni notte alle 3:00
async def nightly_update():
    db = SessionLocal()
    try:
        await fetch_from_api_football(db, league_id=135, season=2024)
        recalculate_all(db)
        print("Aggiornamento notturno completato")
    finally:
        db.close()

@app.on_event("startup")
async def start_scheduler():
    scheduler.start()
```

**Requisiti per l'aggiornamento automatico:**
- Avere una API key valida in `.env` (`API_FOOTBALL_KEY=...`)
- Il container backend deve essere sempre in esecuzione (`docker compose up -d`)
- Con il free tier di API-Football (100 req/giorno) si aggiornano circa 2-3 squadre al giorno

---

## 4 — Tutti i comandi Git per caricare i sorgenti

Eseguire nell'ordine dalla cartella `D:\Progetti\football-scout`:

### Prima volta — inizializzazione repository

```powershell
# 1. Entra nella cartella del progetto
cd D:\Progetti\football-scout

# 2. Configura Git (se non fatto) — UNA VOLTA SOLA
git config --global user.name "Tuo Nome"
git config --global user.email "tua@email.com"
git config --global core.autocrlf input

# 3. Inizializza il repository
git init

# 4. Collega al repository GitHub (crea prima il repo su github.com)
git remote add origin https://github.com/tuo-utente/football-scout.git

# 5. Verifica che .gitattributes sia presente (normalizza line endings)
type .gitattributes

# 6. Rinormalizza tutti i file (importante su Windows)
git add --renormalize .

# 7. Aggiungi tutti i file
git add .

# 8. Primo commit
git commit -m "feat: inizializzazione progetto Football Scout"

# 9. Imposta il branch principale come main
git branch -M main

# 10. Push iniziale
git push -u origin main
```

### Workflow quotidiano — dopo ogni modifica

```powershell
# Vedi cosa è cambiato
git status

# Vedi le differenze nel dettaglio
git diff

# Aggiungi tutti i file modificati
git add .

# Oppure aggiungi un file specifico
git add backend/app/services/search.py

# Commit con messaggio descrittivo
git commit -m "feat: aggiunta keyword 'tecnico' nella ricerca semantica"

# Push sul branch corrente
git push
```

### Lavorare con branch (consigliato per nuove funzionalità)

```powershell
# Crea e spostati su un nuovo branch
git checkout -b feature/nuove-keywords

# ... fai le modifiche ...
git add .
git commit -m "feat: aggiunte 5 nuove keyword di ricerca"
git push origin feature/nuove-keywords

# Quando sei pronto, torna su main e fai merge
git checkout main
git merge feature/nuove-keywords
git push
```

### Comandi utili di controllo

```powershell
# Storico commit
git log --oneline --graph

# Annulla modifiche non ancora in commit
git checkout -- backend/app/services/search.py

# Verifica line endings (devono essere tutti LF)
git ls-files --eol backend/app/services/search.py
```

---

## 5 — Verifica file GitHub Actions per download su MacIl CI è corretto e completo. C'è però **un problema reale** alla riga 117: il `cache-dependency-path` punta a `frontend/package-lock.json` ma quel file non esiste ancora perché non hai mai eseguito `npm install` nel repository. Correggo subito:Il CI era quasi corretto — l'unico problema era la dipendenza da `package-lock.json` che non esiste finché non esegui `npm install` la prima volta. **Ora è corretto.**

---

## 6 — Installare PostgreSQL su Mac

```bash
# Passo 1 — Installa Homebrew (se non ce l'hai)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Passo 2 — Installa PostgreSQL 15
brew install postgresql@15

# Passo 3 — Aggiungi PostgreSQL al PATH (copia e incolla entrambe le righe)
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Passo 4 — Avvia il servizio PostgreSQL
brew services start postgresql@15

# Passo 5 — Verifica che sia avviato
brew services list | grep postgresql
# Deve mostrare: postgresql@15   started

# Passo 6 — Connettiti (su Mac il primo accesso è senza password)
psql postgres

# Dentro psql, crea database e utente del progetto:
CREATE DATABASE football_scout;
CREATE USER football WITH PASSWORD 'football123';
GRANT ALL PRIVILEGES ON DATABASE football_scout TO football;
\c football_scout
GRANT ALL ON SCHEMA public TO football;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO football;
\q
```

**Per fermare/riavviare PostgreSQL:**
```bash
brew services stop postgresql@15
brew services restart postgresql@15
```

> **Nota:** se usi Docker sul Mac non serve installare PostgreSQL — il container lo gestisce da solo. L'installazione manuale serve solo se vuoi lavorare **senza Docker**.

---

## 7 — Perché da 192.168.1.186:5173 non vedi i dati

Il problema è che il frontend fa le chiamate API a `http://localhost:8000`, ma quando accedi da un altro dispositivo (o da IP di rete) `localhost` non esiste — si riferisce sempre alla macchina locale del browser.

**Fix — modifica il file `frontend/.env.local`:**

```
# Sostituisci localhost con l'IP del tuo PC Windows
VITE_API_URL=http://192.168.1.186:8000
```

Poi riavvia il frontend:
```powershell
# Ferma con CTRL+C poi rilancia
npm run dev
```

**Attenzione:** anche il backend deve accettare connessioni da rete. Verifica che nel `docker-compose.yml` il backend abbia:
```yaml
ports:
  - "8000:8000"   # ← deve essere così, non 127.0.0.1:8000:8000
```
E nel file `.env` del backend:
```
# Assicurati che il CORS permetta l'IP di rete
```
In `backend/app/main.py` aggiungi l'IP di rete alla lista CORS:
```python
allow_origins=[
    "http://localhost:5173",
    "http://192.168.1.186:5173",   # ← aggiungi questa riga
]
```
Poi riavvia il backend.

---

## 8 — Dati esterni: quale fonte usare e per cosa

Risposta diretta su come usare ciascuna fonte per la ricerca calciatori con competenze:

| Fonte | Quando usarla | Cosa fornisce per la ricerca |
|-------|--------------|------------------------------|
| **Kaggle FIFA** | Subito, gratis, per iniziare | 18.000 giocatori con tutte le stats (PAC, TIR, PAS, DRI, DIF, FIS) — ideale per popolare `scouting_players` |
| **API-Football** | Per dati live e aggiornati | Giocatori attivi, squadre reali, trasferimenti — dati anagrafici più affidabili |
| **StatsBomb** | Per stats avanzate (xG, xA, duelli) | Event data dettagliato — arricchisce i giocatori già importati con statistiche avanzate |
| **FBref** | Alternativa gratuita a StatsBomb | Stesse stats avanzate, accessibili via scraping |
| **Football-Data.org** | Per struttura campionati | Competizioni, squadre, rose — utile per sapere in quale squadra gioca un giocatore oggi |

**Il flusso consigliato per avere dati completi:**

```
1. Kaggle FIFA  →  importa i 18.000 giocatori con stats base
                   (già implementato con make import-kaggle)
        +
2. StatsBomb    →  arricchisci con xG, xA, duelli aerei
                   (da implementare in ingest.py)
        =
Database completo con stats base + avanzate
        ↓
Ricerca semantica funzionante su tutti i campi
```

Il codice per l'import da Kaggle è già pronto nel file `backend/app/services/ingest.py`. Devi solo scaricare il CSV da Kaggle, metterlo in `data/` e lanciare il comando.