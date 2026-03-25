# ⚽ Football Scout

Sistema di gestione squadra e scouting calciatori con ricerca in linguaggio naturale.

**Stack:** FastAPI · PostgreSQL · Vue 3 · Docker · Pinia

---

## 🚀 Come iniziare (su qualsiasi OS)

### Su Mac — solo 2 comandi

```bash
git clone https://github.com/tuo-utente/football-scout.git
cd football-scout
cp .env.example .env
docker compose up --build
```

**Nient'altro.** Il Mac non richiede nessuna configurazione aggiuntiva.

| Servizio     | URL                          |
|--------------|------------------------------|
| Frontend     | http://localhost:5173        |
| API Swagger  | http://localhost:8000/docs   |
| API health   | http://localhost:8000        |

---

### Su Windows — una configurazione Git (una volta sola)

Su Windows i file vengono salvati con `CRLF` invece di `LF`.
Questo romperebbe gli script dentro Docker (che gira su Linux).
Il rimedio è **un solo comando**, da eseguire una volta sola sul PC Windows:

```bash
git config --global core.autocrlf input
```

Poi il flusso è identico al Mac:

```bash
git clone https://github.com/tuo-utente/football-scout.git
cd football-scout
cp .env.example .env    # oppure: copy .env.example .env
docker compose up --build
```

> **Perché funziona automaticamente?**
> Il file `.gitattributes` nella root del progetto istruisce Git a salvare
> sempre i file con `LF` nel repository. Quando il Mac fa `git clone`,
> riceve file già corretti — nessuno script manuale necessario.

---

## 🔄 Workflow Git giornaliero

```bash
# Aggiorna prima di iniziare
git pull origin main

# Crea un branch per la tua feature
git checkout -b feature/nome-feature

# ... fai le modifiche ...

# Commit e push
git add .
git commit -m "feat: descrizione della modifica"
git push origin feature/nome-feature

# Apri una Pull Request su GitHub
```

---

## Come funziona il meccanismo cross-platform

```
PC Windows (sviluppo)
  │
  │  git config --global core.autocrlf input   ← una volta sola
  │  git add .  →  Git normalizza a LF
  │  git push
  ▼
GitHub Repository
  │  Tutti i file sono in LF  (garantito da .gitattributes)
  │  GitHub Actions verifica i line endings ad ogni push
  ▼
Mac (o qualsiasi altro OS)
  │  git clone  →  riceve file già in LF
  │  docker compose up --build
  ▼
App funzionante ✅  (nessun setup manuale)
```

Il meccanismo si regge su **tre elementi già presenti nel progetto**:

| File | Ruolo |
|------|-------|
| `.gitattributes` | Dice a Git: "salva sempre tutto in LF nel repository" |
| `.github/workflows/ci.yml` | Blocca il push se qualcuno commette CRLF per errore |
| `vite.config.js` (`usePolling: true`) | Il file watching funziona anche su Windows con Docker |

---

## Comandi Docker

```bash
# Avvia tutto (con log visibili — utile in sviluppo)
docker compose up

# Avvia in background
docker compose up -d

# Ferma tutto
docker compose down

# Ferma e CANCELLA il database (reset completo)
docker compose down -v

# Ribilancia solo il backend dopo modifiche a requirements.txt
docker compose up --build backend

# Log in tempo reale
docker compose logs -f

# Log solo del backend
docker compose logs -f backend

# Shell dentro il container backend
docker compose exec backend bash

# Connessione diretta al database
docker compose exec db psql -U football football_scout
```

---

## Comandi `make` (shortcut)

```bash
make up              # docker compose up
make down            # docker compose down
make down-clean      # down + cancella volumi (⚠️ reset DB)
make build           # up --build
make logs            # segui tutti i log
make logs-back       # log solo backend
make shell-backend   # shell nel container backend
make shell-db        # psql nel container db
make test            # esegui i test pytest
make migrate         # esegui le migration Alembic
make import-kaggle   # importa dataset FIFA (vedi sezione Dati)
make recalc          # ricalcola gli score di tutti i giocatori
make stats           # statistiche del database
```

---

## Importare i calciatori (dataset)

Il database parte con 4 giocatori di esempio (`scripts/init.sql`).
Per caricare dati reali hai due opzioni:

### Opzione A — Kaggle FIFA (gratuito, ottimo per sviluppo)

1. Scarica `players_22.csv` da:
   https://www.kaggle.com/datasets/stefanoleone992/fifa-22-complete-player-dataset
2. Copialo nella cartella `data/`
3. Esegui l'import:

```bash
make import-kaggle FILE=data/players_22.csv
# oppure:
docker compose exec backend python -m app.services.ingest \
  --source kaggle --file /app/data/players_22.csv --limit 5000
```

### Opzione B — API-Football (dati live, per produzione)

1. Registrati su https://api-football.com (free tier: 100 req/giorno)
2. Aggiungi la chiave nel `.env`: `API_FOOTBALL_KEY=la-tua-chiave`
3. Esegui:

```bash
docker compose exec backend python -m app.services.ingest \
  --source api --league 135 --season 2024
# 135 = Serie A
```

Dopo ogni import, ricalcola gli score:

```bash
make recalc
# oppure: curl -X POST http://localhost:8000/admin/recalculate-scores
```

---

## Migration database (Alembic)

```bash
# Applica tutte le migration pendenti
make migrate
# oppure:
docker compose exec backend alembic upgrade head

# Crea una nuova migration dopo aver modificato i modelli
docker compose exec backend alembic revision --autogenerate -m "descrizione"

# Rollback dell'ultima migration
docker compose exec backend alembic downgrade -1

# Stato attuale
docker compose exec backend alembic current
```

---

## Test

```bash
make test
# oppure:
docker compose exec backend pytest tests/ -v
```

---

## Struttura del progetto

```
football-scout/
│
├── .gitattributes              ← CHIAVE: normalizza LF per tutti gli OS
├── .gitignore
├── .env.example                ← copia in .env e compila
├── docker-compose.yml          ← sviluppo (hot-reload)
├── docker-compose.prod.yml     ← override produzione
├── Makefile                    ← shortcut comandi
│
├── .github/
│   └── workflows/ci.yml        ← CI: verifica LF + test + build
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                ← migration database
│   ├── tests/                  ← pytest
│   └── app/
│       ├── main.py             ← FastAPI + CORS
│       ├── database.py         ← SQLAlchemy
│       ├── models/models.py    ← MyTeam, TeamTrait, MyPlayer, ScoutingPlayer
│       ├── schemas/schemas.py  ← Pydantic I/O
│       ├── routers/
│       │   ├── team.py         ← CRUD squadra + traits
│       │   ├── players.py      ← CRUD rosa
│       │   ├── scouting.py     ← ricerca semantica
│       │   └── admin.py        ← ricalcolo score, statistiche DB
│       └── services/
│           ├── search.py       ← motore query NL (sicuro, ORM)
│           ├── scoring.py      ← heading/buildup/defensive score
│           └── ingest.py       ← import Kaggle CSV e API-Football
│
├── frontend/
│   ├── Dockerfile              ← multi-stage: dev + build + nginx
│   ├── vite.config.js          ← usePolling:true per Windows+Docker
│   └── src/
│       ├── App.vue             ← shell con sidebar
│       ├── router/             ← Vue Router 4
│       ├── api/client.js       ← Axios con gestione errori globale
│       ├── stores/             ← Pinia (teamStore, scoutingStore)
│       ├── views/
│       │   ├── TeamDashboard.vue
│       │   ├── TeamTraits.vue  ← punti forza / debolezza
│       │   ├── TeamRoster.vue  ← rosa giocatori
│       │   └── ScoutingSearch.vue  ← ricerca in linguaggio naturale
│       └── components/
│           ├── PlayerCard.vue
│           ├── StatBar.vue
│           ├── ScorePill.vue
│           ├── TraitItem.vue
│           ├── TeamForm.vue
│           └── InfoRow.vue
│
├── scripts/
│   └── init.sql               ← dati di esempio caricati al primo avvio
│
└── data/                      ← metti qui i CSV Kaggle (ignorati da Git)
    └── .gitkeep
```

---

## API Reference

Documentazione interattiva: http://localhost:8000/docs

### Squadra

| Metodo   | Endpoint                            | Descrizione              |
|----------|-------------------------------------|--------------------------|
| `GET`    | `/teams`                            | Lista squadre            |
| `POST`   | `/teams`                            | Crea squadra             |
| `GET`    | `/teams/{id}`                       | Dettaglio + traits       |
| `PUT`    | `/teams/{id}`                       | Aggiorna squadra         |
| `DELETE` | `/teams/{id}`                       | Elimina squadra          |
| `POST`   | `/teams/{id}/traits`                | Aggiungi caratteristica  |
| `DELETE` | `/teams/{id}/traits/{trait_id}`     | Elimina caratteristica   |
| `GET`    | `/teams/{id}/players`               | Lista rosa               |
| `POST`   | `/teams/{id}/players`               | Aggiungi a rosa          |
| `DELETE` | `/teams/{id}/players/{player_id}`   | Rimuovi da rosa          |

### Scouting

| Metodo | Endpoint             | Descrizione          |
|--------|----------------------|----------------------|
| `GET`  | `/scouting/search?q=...` | Ricerca semantica |

**Parametri:**

| Parametro     | Esempio                              |
|---------------|--------------------------------------|
| `q`           | `centravanti mancino bravo di testa` |
| `position`    | `ST`, `CM`, `CB`, `GK`              |
| `min_age`     | `18`                                 |
| `max_age`     | `25`                                 |
| `nationality` | `Italiana`                           |
| `limit`       | `20`                                 |

**Keywords riconosciute nella ricerca:**
`bravo di testa` · `forte fisicamente` · `veloce` · `bravo col pallone` · `ottimo passatore` · `tiratore` · `fa salire la squadra` · `difensore solido` · `mancino` · `destro` · `centravanti` · `trequartista` · `ala` · `terzino` · `centrocampista` · `difensore centrale` · `portiere` · `giovane` · `under 21` · `under 25` · `esperto` · `realizzatore` · `assist man`

### Admin

| Metodo  | Endpoint                       | Descrizione                    |
|---------|--------------------------------|--------------------------------|
| `POST`  | `/admin/recalculate-scores`    | Ricalcola score tutti i player |
| `GET`   | `/admin/stats`                 | Statistiche database           |

---

## Fonti dati

| Fonte | Tipo | URL | Costo |
|-------|------|-----|-------|
| **StatsBomb Open Data** | Event data | [github.com/statsbomb/open-data](https://github.com/statsbomb/open-data) | ✅ Gratuito |
| **API-Football** | Giocatori live | [api-football.com](https://www.api-football.com/) | ✅ Free tier |
| **Football-Data.org** | Competizioni | [football-data.org](https://www.football-data.org/) | ✅ Free tier |
| **Kaggle FIFA dataset** | 18k+ giocatori | [kaggle.com](https://www.kaggle.com/datasets/stefanoleone992/fifa-22-complete-player-dataset) | ✅ Gratuito |

---

## FAQ

**Il frontend non si aggiorna su Windows**
Già risolto: `vite.config.js` ha `usePolling: true`.

**Port already in use**
```bash
# Mac/Linux
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# Windows PowerShell
netstat -ano | findstr :8000
taskkill /PID <numero> /F
```

**Reset completo del database**
```bash
docker compose down -v
docker compose up --build
```

**Errore permission denied su script .sh (Mac)**
```bash
chmod +x setup.sh
```
