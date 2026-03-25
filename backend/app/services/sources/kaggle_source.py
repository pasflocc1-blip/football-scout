"""
sources/kaggle_source.py
------------------------
Importa giocatori da un CSV Kaggle FIFA.

Dataset consigliato:
  https://www.kaggle.com/datasets/stefanoleone992/fifa-22-complete-player-dataset
  File: players_22.csv oppure players_23.csv

Copertura: ~18.000 giocatori con PAC, TIR, PAS, DRI, DIF, FIS
Costo: gratuito, ideale per sviluppo/prototipo
"""

import csv
import os
from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer
from app.services.scoring import compute_scores


def import_from_kaggle_csv(
    db: Session,
    filepath: str,
    limit: int = 2000,
    progress_cb=None,  # callable(imported: int) opzionale per aggiornare lo stato
) -> int:
    """
    Importa giocatori da un CSV Kaggle FIFA.

    Ritorna il numero di record importati/aggiornati.

    Raises:
        FileNotFoundError: se il file CSV non esiste nel container.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"File non trovato nel container: {filepath}\n"
            f"Scarica da Kaggle e copialo nella cartella data/ del progetto."
        )

    imported = 0

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            if i >= limit:
                break

            # Prende solo il primo ruolo (es. "ST, CF" → "ST")
            raw_pos = row.get("player_positions", "")
            position = raw_pos.split(",")[0].strip() if raw_pos else None

            player_data = {
                "external_id":          f"kaggle_{row.get('sofifa_id', i)}",
                "name":                 row.get("short_name", f"Player_{i}"),
                "position":             position,
                "club":                 row.get("club_name"),
                "nationality":          row.get("nationality_name"),
                "age":                  _int(row.get("age")),
                "preferred_foot":       row.get("preferred_foot"),
                "pace":                 _int(row.get("pace")),
                "shooting":             _int(row.get("shooting")),
                "passing":              _int(row.get("passing")),
                "dribbling":            _int(row.get("dribbling")),
                "defending":            _int(row.get("defending")),
                "physical":             _int(row.get("physic")),
                "aerial_duels_won_pct": _float(row.get("attacking_heading_accuracy")),
            }

            # Upsert: aggiorna se esiste, inserisce se no
            existing = db.query(ScoutingPlayer).filter_by(
                external_id=player_data["external_id"]
            ).first()

            if existing:
                for k, v in player_data.items():
                    setattr(existing, k, v)
                p = existing
            else:
                p = ScoutingPlayer(**player_data)
                db.add(p)
                db.flush()

            scores = compute_scores(p)
            for k, v in scores.items():
                setattr(p, k, v)

            imported += 1

            if imported % 200 == 0:
                db.commit()
                msg = f"  → Kaggle: {imported} giocatori importati..."
                print(msg)
                if progress_cb:
                    progress_cb(imported)

    db.commit()
    return imported


# ── Helpers ──────────────────────────────────────────────────────

def _int(val) -> int | None:
    try:
        return int(float(val)) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None