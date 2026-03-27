Con Football-Data.org riesco a caricare anche le rose delle squadre aggiornate al campionato in corso, mi serve sapere come posso arricchire i dati statistici di questi calciatori, per poter applicare la ricerca di scouting. StaBomb fornisce diverse statistiche ma sono datate, trovami qualche servizio che mi consente di crearmi una base dati aggiornata anche con le statistiche, anche tra i servizi che gia uso. In allegato trovi i servizi free, che utilizzo ora.

00:01
Ottima domanda. Analizzo la situazione: hai le rose aggiornate (Football-Data.org) ma ti mancano le statistiche correnti per fare scouting. Vediamo cosa puoi fare con quello che hai già e cosa aggiungere.


Cercato sul web
Cercato sul web
Ho tutto quello che mi serve. Ti faccio un quadro completo e pratico.

Ottimo, ora costruisco una visualizzazione chiara e completa della situazione.



Ecco la situazione completa. Ti spiego le tre strade concrete, nell'ordine in cui ti conviene implementarle.

Understat — la priorità assoluta (step 1)

Understat copre le Big 5 europee (Serie A inclusa) dalla stagione 2014/15 fino a quella in corso 
PyPI
, ed è completamente gratuito. La libreria Python understat ti dà per ogni giocatore: xG, xA, npxG (non-penalty expected goals), xGChain, xGBuildup, goals, assists, shots, key_passes e i minuti giocati. È il modo più diretto per avere xG/xA aggiornati per la stagione corrente. L'integrazione è strutturalmente identica alla tua statsbomb_source.py: chiami get_league_players("Serie_A", 2024) e poi passi i risultati al tuo player_matcher esistente. Il vantaggio enorme rispetto a StatsBomb è che i dati sono della stagione in corso, non storici.

FBref — già ce l'hai, sfruttalo meglio (step 2)

FBref, alimentato da Opta, offre indicatori avanzati come xG, xA, pressioni riuscite e azioni difensive, ed è possibile filtrare per minuti giocati, zona del campo e ruolo tattico 
Sports Data Campus
. Hai già il source FBref nel tuo stack — il problema è che probabilmente non stai estraendo tutti i campi per90 disponibili. Ti conviene aggiornare quella sorgente per portare nel DB anche progressive_carries, pressures, touches_att_pen che sono metriche chiave per lo scouting.

API-Football — non sprecare le 100 richieste giornaliere (step 3)

L'endpoint /players di API-Football restituisce per ogni giocatore il profilo statistico completo: shots-per-goal, assist count, rating, dribbles, e molto altro 
API-Football
. Attualmente stai usando quelle 100 richieste solo per importare i giocatori per nome/club. Puoi invece usare i giocatori già nel DB (importati via Football-Data.org) come lista e chiamare /players/statistics?id=X&season=2024 solo per quelli che ti interessano.

Il vero problema trasversale: il matching tra sorgenti

Il fix al player_matcher.py che hai già risolve il caso StatsBomb (nome pieno senza club). Ma per collegare in modo affidabile Football-Data → Understat → FBref ti serve aggiungere un campo external_id al modello ScoutingPlayer — ad esempio understat_id e fbref_id. Una volta che hai fatto il primo match con fuzzy e lo salvi, i match successivi diventano deterministici. Vuoi che ti scriva il codice per la sorgente Understat o per l'estensione del modello DB?






