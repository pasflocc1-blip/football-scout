"""
routers/ingest_fbref_csv.py
---------------------------
Aggiunge due endpoint per importare FBref da CSV incollato dall'utente:

  POST /ingest/fbref/csv         — importa da testo CSV nel body
  POST /ingest/fbref/csv-upload  — importa da file CSV caricato

Questi endpoint risolvono il problema del 403 di FBref da Docker:
l'utente copia il CSV dal browser e lo incolla nell'app.

Come usarlo in main.py:
  from app.routers import ingest_fbref_csv
  app.include_router(ingest_fbref_csv.router)
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.sources.fbref_source import (
    import_from_csv_text,
    import_from_csv_file,
    FBREF_LEAGUES,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


class FBrefCsvRequest(BaseModel):
    csv_text:   str
    league_key: str = "serie_a"


@router.post("/fbref/csv")
def import_fbref_csv(req: FBrefCsvRequest, db: Session = Depends(get_db)):
    """
    Importa statistiche FBref da testo CSV copiato dalla pagina web.

    Come ottenere il CSV:
      1. Vai su fbref.com → pagina statistiche della lega
      2. Scorri fino alla tabella "Standard Stats"
      3. Clicca "Share & Export" → "Get table as CSV"
      4. Copia tutto il testo (Ctrl+A, Ctrl+C)
      5. Incollalo qui nel campo csv_text

    Questo endpoint bypassa completamente il problema del 403.
    """
    if req.league_key not in FBREF_LEAGUES:
        raise HTTPException(
            400,
            f"Lega non supportata: '{req.league_key}'. "
            f"Disponibili: {list(FBREF_LEAGUES.keys())}"
        )

    if not req.csv_text.strip():
        raise HTTPException(400, "csv_text è vuoto")

    try:
        result = import_from_csv_text(db, req.csv_text, req.league_key, progress_cb=lambda cur, tot: None)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Errore durante l'importazione: {e}")

    # Dopo l'importazione, ricalcola score in background
    try:
        from app.services.scoring import recalculate_all
        recalculate_all(db)
    except Exception as e:
        print(f"  WARN: ricalcolo score fallito: {e}")

    return {
        "message": f"Importazione FBref CSV completata: {result['players_enriched_in_db']} giocatori arricchiti",
        **result,
    }


@router.post("/fbref/csv-upload")
async def import_fbref_csv_upload(
    file: UploadFile = File(...),
    league_key: str = "serie_a",
    db: Session = Depends(get_db),
):
    """
    Importa da file CSV caricato (multipart/form-data).
    Alternativa a /fbref/csv per file salvati localmente.
    """
    if league_key not in FBREF_LEAGUES:
        raise HTTPException(400, f"Lega non supportata: {league_key}")

    print(f"  INFO: csv-upload filename: {file.filename}")

    content = await file.read()
    csv_text = content.decode("utf-8", errors="replace")

    if not csv_text.strip():
        raise HTTPException(400, "File CSV vuoto")

    try:
        result = import_from_csv_text(db, csv_text, league_key)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Errore: {e}")

    try:
        from app.services.scoring import recalculate_all
        recalculate_all(db)
    except Exception as e:
        print(f"  WARN: ricalcolo score fallito: {e}")

    return {
        "message": f"Importazione FBref CSV completata: {result['players_enriched_in_db']} giocatori arricchiti",
        **result,
    }