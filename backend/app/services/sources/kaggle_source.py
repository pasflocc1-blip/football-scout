import csv
import os
from sqlalchemy.orm import Session

from app.models.models import ScoutingPlayer
from app.services.scoring import compute_scores
from app.services.player_matcher import find_player_in_db


def import_from_kaggle_csv(
        db: Session,
        filepath: str,
        limit: int = 2000,
        progress_cb=None,
) -> int:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File non trovato: {filepath}")

    imported = 0

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            if i >= limit:
                break

            # Identificativo univoco dal CSV
            sofifa_id = row.get("sofifa_id")
            tm_id = f"kaggle_{sofifa_id}" if sofifa_id else f"kaggle_{i}"

            # Estrazione posizione
            raw_pos = row.get("player_positions", "")
            position = raw_pos.split(",")[0].strip() if raw_pos else None

            # Mapping dati (usando i TUOI nomi colonna originali)
            player_data = {
                "transfermarkt_id": tm_id,
                "name": row.get("short_name", f"Player_{i}"),
                "position": position,
                "club": row.get("club_name"),
                "nationality": row.get("nationality_name"),
                "preferred_foot": row.get("preferred_foot"),
                "age": _int(row.get("age")),

                # Stats base
                "pace": _int(row.get("pace")),
                "shooting": _int(row.get("shooting")),
                "passing": _int(row.get("passing")),
                "dribbling": _int(row.get("dribbling")),
                "defending": _int(row.get("defending")),
                "physical": _int(row.get("physic")),  # Nome colonna originale
                "aerial_duels_won_pct": _float(row.get("attacking_heading_accuracy")),  # Nome colonna originale

                "xg_per90": 0.0,
                "xa_per90": 0.0,
                "progressive_passes": 0,
            }

            # --- LOGICA ANTI-ERRORE (UPSERT) ---

            # 1. Cerchiamo prima per ID (evita UniqueViolation se l'ID esiste già)
            p = db.query(ScoutingPlayer).filter_by(transfermarkt_id=tm_id).first()

            # 2. Se non trovato per ID, usiamo il tuo matcher per nome/club
            if not p:
                p = find_player_in_db(db, player_data["name"], player_data["club"])

            if p:
                # Aggiorniamo il record esistente
                for k, v in player_data.items():
                    # NON aggiorniamo l'ID se lo abbiamo trovato tramite nome,
                    # per evitare conflitti con altri record
                    if k != "transfermarkt_id" and v is not None:
                        setattr(p, k, v)

                # Se il record trovato per nome non aveva ID, glielo diamo ora
                if not p.transfermarkt_id:
                    p.transfermarkt_id = tm_id
            else:
                # Creazione nuovo record
                p = ScoutingPlayer(**player_data)
                db.add(p)

            # Flush per rendere l'oggetto pronto per il calcolo degli score
            db.flush()

            # Calcolo degli score
            scores = compute_scores(p)
            for k, v in scores.items():
                setattr(p, k, v)

            imported += 1

            if imported % 200 == 0:
                db.commit()
                print(f"  → Kaggle: {imported}/{limit} giocatori importati...")
                if progress_cb:
                    progress_cb(imported)

    db.commit()
    return imported


def _int(val) -> int | None:
    try:
        return int(float(val)) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", "N/A") else 0.0
    except (ValueError, TypeError):
        return 0.0