import pandas as pd
import requests
import time
from io import StringIO

url = "https://fbref.com/en/comps/11/stats/Serie-A-Stats"

# 1. Imposta un User-Agent per sembrare un browser vero
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://google.com/'
}
try:
    # Scarica la pagina con requests
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Verifica che non ci siano errori (404, 500, etc.)

    # 2. Leggi le tabelle dall'HTML scaricato
    # Usiamo StringIO per evitare warning di pandas
    tables = pd.read_html(StringIO(response.text))

    # Cerchiamo la tabella corretta (di solito è 'stats_squads_standard' o la prima)
    df = tables[0]

    # 3. Pulizia Multi-index (FBref usa intestazioni a due livelli)
    df.columns = [' '.join(col).strip() for col in df.columns.values]

    # Rimuovi eventuali righe di intestazione ripetute (succede spesso nelle tabelle lunghe)
    df = df[df.iloc[:, 0] != "Squad"]

    # 4. Conversione in JSON
    # 'records' è il formato standard per le API (lista di oggetti)
    data_to_send = df.to_dict(orient='records')

    # 5. Invio all'endpoint
    # NOTA: assicurati che l'URL dell'endpoint sia corretto (nel tuo esempio mancava l'host)
    endpoint = "http://localhost:8000/ingest/fbref/csv"

    post_response = requests.post(endpoint, json=data_to_send)

    print(f"Status Code Invio: {post_response.status_code}")
    if post_response.status_code != 200:
        print(f"Dettagli errore: {post_response.text}")

except Exception as e:
    print(f"Si è verificato un errore: {e}")

# Rispetta FBref: non fare più di 20 richieste al minuto!
time.sleep(3)