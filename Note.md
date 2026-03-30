# Dalla cartella backend (sei già lì da quello che vedo)
# D:\Progetti\football-scout\backend>

# Crea l'ambiente virtuale
python -m venv .venv

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1

#Svuota la cache di pip e forza il download del wheel corretto
python -m pip cache purge

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -r requirements.txt --only-binary=psycopg2-binary
cd ..
copy .env.example .env
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


Get-ChildItem "C:\Program Files\PostgreSQL"


Ti spiego cosa succede: xg_per90, xa_per90 (e anche progressive_passes) sono metriche avanzate. Fonti base come API-Football e Kaggle (FIFA) non le forniscono direttamente, mentre FBref e StatsBomb sì.

Tuttavia, quando creiamo un giocatore nuovo (ad esempio partendo da API-Football o Kaggle), dobbiamo assicurarci di "inizializzare" questi campi a 0.0 nel dizionario player_data, altrimenti il database potrebbe lamentarsi o potresti avere dei None fastidiosi.

Negli script di FBref e StatsBomb, invece, li andiamo proprio ad aggiornare.


# 🛠️ Fix Football Scout — Riepilogo interventi

## 0 — Errore DatabaseExplorer.vue
**File:** `frontend/src/views/DatabaseExplorer.vue`

Il problema è che nel file Vue è presente sia `<script setup>` che `<script src="...">` 
nella stessa componente — Vue non lo permette.

**Fix:** Rimuovi il tag `<script src="...">` separato e incorpora tutto il codice nel `<script setup>`.
Vedi: `FIX_0_DatabaseExplorer.vue`

---

## 1 — Filtri avanzati Scouting non trovano nulla
**File:** `frontend/src/views/ScoutingSearch.vue` (la parte `doSearch`)

Il problema: i filtri `position`, `min_age`, `max_age`, `nationality` venivano passati solo 
se **truthy**. Ma `min_age=0` o `position=""` non vengono mai inviati, causando problemi.
Il fix vero è nel backend: `search.py` deve supportare ricerche **solo con filtri**, 
senza la query testuale `q` obbligatoria.

**Fix backend:** `FIX_1_search.py` — `q` diventa opzionale nel `search_players()`
**Fix backend router:** `FIX_1_scouting_router.py` — `q` non è più obbligatoria
**Fix frontend:** nella `doSearch()`, aggiunge `q` vuota se filtri sono presenti

---

## 2 — "Scarsa in difesa" restituisce giocatori errati
**File:** `backend/app/services/search.py`

Il problema: `"Scarsa in difesa"` non matcha nessuna keyword nella `SEMANTIC_MAP`, 
quindi ritorna tutti i giocatori ordinati per score generico, senza filtro di posizione.

**Fix:** Aggiunta keyword negativa `"scarsa in difesa"` che cerca difensori bravi 
(la logica è: se la squadra è scarsa in difesa → cerca CB/LB/RB con alto defending_pct).
Vedi: `FIX_1_search.py` (stesso file del fix 1)

---

## 3 & 4 — Eliminazione servizio FIFA / Kaggle
**File:** `backend/app/services/sources/kaggle_source.py`
**File:** `backend/app/services/ingest.py`
**File:** `frontend/src/views/DataIngestion.vue`

Il Kaggle CSV contiene dati FIFA soggettivi (pace, shooting, passing, dribbling, 
defending, physical). Questi campi NON esistono più nel modello `ScoutingPlayer`.

**Fix:**
- `FIX_3_kaggle_source.py` — rimuove i campi FIFA, salva solo anagrafica
- `FIX_4_migration.sql` — query SQL per rimuovere colonne FIFA rimaste nel DB
- Nel frontend DataIngestion.vue rimuovere il blocco "Kaggle FIFA" 
  (vedi istruzioni nel file `FIX_4_DataIngestion_patch.md`)

---

## 5 — Traduzioni ruoli in Global Scouting
**File:** `frontend/src/views/GlobalScouting.vue`

Le etichette dei ruoli come "Centre-Forward", "Left Midfield" etc. erano in inglese.

**Fix:** Il file `positions.js` è già corretto con le traduzioni italiane.
Il problema è che `GlobalScouting.vue` non usava `posLabel()` da `positions.js`.
Vedi: `FIX_5_GlobalScoutingView.vue` — aggiunge import e uso di `posLabel()`

---

## 6 — Come funzionano le team_traits
Vedi sezione dedicata in fondo a questo documento.

---

## 7 — Manuale tecnico
Vedi: `FIX_7_manuale_tecnico.md`

---

## 6 — Architettura Team Traits

### Struttura dati
Il sistema dei **team traits** (caratteristiche squadra) è composto da:

**Backend:**
- Modello `TeamTrait` (tabella `team_traits`):
  - `id` — PK
  - `team_id` — FK verso `my_team.id` (cascade delete)
  - `trait_type` — Enum: `"positive"` o `"negative"`
  - `description` — Testo libero (es. "Scarsa efficacia di testa")
  - `priority` — Intero 1=Alta, 2=Media, 3=Bassa

- Endpoints REST in `routers/team.py`:
  - `POST /teams/{team_id}/traits` — aggiunge un trait
  - `DELETE /teams/{team_id}/traits/{trait_id}` — elimina un trait

**Frontend — Store Pinia (`teamStore.js`):**
- `positiveTraits` — computed: `activeTeam.traits.filter(t => t.trait_type === 'positive')`
- `negativeTraits` — computed: `activeTeam.traits.filter(t => t.trait_type === 'negative')`
- `scoutingSuggestions` — computed: trasforma i trait NEGATIVI in query di scouting

### Come funziona `scoutingSuggestions`
La logica più interessante è il calcolo automatico dei **suggerimenti di scouting** 
dai punti deboli della squadra:

```js
// In teamStore.js
const scoutingSuggestions = computed(() => {
  return negativeTraits.value
    .sort((a, b) => a.priority - b.priority)
    .map(t => t.description)  // usa la descrizione come query
    .slice(0, 6)
})
```

Ogni **punto debole** diventa automaticamente un link cliccabile in `TeamTraits.vue`:
```html
<RouterLink :to="`/scouting?q=${encodeURIComponent(s)}`">
  🔍 {{ s }}
</RouterLink>
```

Quando l'utente clicca, la `ScoutingSearch.vue` esegue:
```js
onMounted(() => {
  if (route.query.q) {
    query.value = route.query.q  // es. "Scarsa in difesa"
    doSearch()
  }
})
```

Il testo della descrizione (es. "Scarsa in difesa") viene passato a `search.py` che 
lo confronta con la `SEMANTIC_MAP`. **Questo è il motivo del bug #2**: la descrizione 
"Scarsa in difesa" non matchava nessuna keyword. Il fix aggiunge keyword che interpretano 
correttamente frasi negative sulla difesa.

### Flusso completo
```
TeamTraits.vue
  → addTrait() → POST /teams/{id}/traits
  → teamStore.addTrait() → activeTeam.traits.push()
  → scoutingSuggestions (computed) si aggiorna automaticamente
  → Link badge in TeamTraits.vue
    → click → /scouting?q=Scarsa in difesa
    → ScoutingSearch.vue → doSearch()
    → GET /scouting/search?q=Scarsa+in+difesa
    → search.py → build_conditions() → SEMANTIC_MAP lookup
    → Filtra ScoutingPlayer dal DB
    → Ritorna lista giocatori ordinata per score
```