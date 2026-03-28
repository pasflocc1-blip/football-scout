import csv
import os
from datetime import datetime  # <--- Nuova importazione
from sqlalchemy.orm import Session
from app.models.models import ScoutingPlayer
from app.services.scoring import compute_scores
from app.services.player_matcher import find_player_in_list


def import_from_kaggle_csv(db: Session, filepath: str, limit: int = 2000, progress_cb=None) -> int:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File non trovato: {filepath}")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Inizializzazione cache giocatori...")
    all_db_players = db.query(ScoutingPlayer).all()
    imported = 0

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit: break

            sofifa_id = row.get("sofifa_id")
            tm_id = f"kaggle_{sofifa_id}" if sofifa_id else f"kaggle_{i}"

            player_data = {
                "transfermarkt_id": tm_id,
                "name": row.get("short_name") or row.get("long_name") or f"Player_{i}",
                "club": row.get("club_name"),
                "position": (row.get("player_positions", "").split(",")[0].strip() or None),
                "age": _int(row.get("age")),
                "pace": _int(row.get("pace")),
                "shooting": _int(row.get("shooting")),
                "passing": _int(row.get("passing")),
                "dribbling": _int(row.get("dribbling")),
                "defending": _int(row.get("defending")),
                "physical": _int(row.get("physic")),
                "aerial_duels_won_pct": _float(row.get("attacking_heading_accuracy")),
            }

            p = next((x for x in all_db_players if x.transfermarkt_id == tm_id), None)

            if not p:
                p = find_player_in_list(player_data["name"], player_data["club"], all_db_players)

            if p:
                for k, v in player_data.items():
                    if k != "transfermarkt_id" and v is not None:
                        setattr(p, k, v)
            else:
                p = ScoutingPlayer(**player_data)
                db.add(p)
                all_db_players.append(p)

            db.flush()
            scores = compute_scores(p)
            for k, v in scores.items():
                setattr(p, k, v)

            imported += 1
            if imported % 200 == 0:
                db.commit()
                # --- RIGA MODIFICATA QUI ---
                now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                print(f"[{now_str}] → Kaggle: {imported}/{limit} giocatori importati...")
                # ---------------------------
                if progress_cb: progress_cb(imported)

    db.commit()
    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] Importazione completata: {imported} record.")
    return imported


def _int(val) -> int:
    try:
        return int(float(val)) if val and str(val).strip() != "" else 0
    except:
        return 0


def _float(val) -> float:
    try:
        return float(val) if val and str(val).strip() != "" else 0.0
    except:
        return 0.0