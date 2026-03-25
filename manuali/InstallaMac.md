 # Installare PostgreSQL su Mac

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

# Per fermare/riavviare PostgreSQL:
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
