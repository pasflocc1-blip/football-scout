"""
services/sources/kaggle_source.py — FIX: rimossi tutti i dati FIFA soggettivi

CAMBIAMENTI:
  - Rimossi: pace, shooting, passing, dribbling, defending, physical
  - Salvate solo: anagrafica + aerial_duels_won_pct (dato oggettivo da heading accuracy)
  - Il CSV Kaggle è ancora utile per popolare il DB con nomi/club/posizioni/età
    che verranno poi arricchiti da FBref, Understat, API-Football
"""
import csv
import os
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import ScoutingPlayer
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
            if i >= limit:
                break

            sofifa_id = row.get("sofifa_id")
            tm_id = f"kaggle_{sofifa_id}" if sofifa_id else f"kaggle_{i}"

            # ── Salva SOLO dati anagrafici oggettivi ─────────────────────
            # Nessun dato FIFA (pace/shooting/passing/dribbling/defending/physical)
            player_data = {
                "transfermarkt_id":    tm_id,
                "name":                row.get("short_name") or row.get("long_name") or f"Player_{i}",
                "club":                row.get("club_name") or None,
                "nationality":         row.get("nationality_name") or row.get("nationality") or None,
                "position":            (row.get("player_positions", "").split(",")[0].strip() or None),
                "age":                 _int(row.get("age")),
                "preferred_foot":      row.get("preferred_foot") or None,
                # aerial_duels_won_pct è un dato semi-oggettivo dal dataset
                # Viene usato come seed iniziale, poi sovrascritto da API-Football
                "aerial_duels_won_pct": _float(row.get("attacking_heading_accuracy")),
            }

            p = next((x for x in all_db_players if x.transfermarkt_id == tm_id), None)

            if not p:
                p = find_player_in_list(player_data["name"], player_data["club"], all_db_players)

            if p:
                # Aggiorna solo i campi anagrafici, NON sovrascrivere score già calcolati
                for k, v in player_data.items():
                    if k != "transfermarkt_id" and v is not None:
                        # Non sovrascrivere i campi oggettivi già valorizzati
                        existing_val = getattr(p, k, None)
                        if existing_val is None or k in ("name", "club", "position", "age", "nationality", "preferred_foot"):
                            setattr(p, k, v)
            else:
                p = ScoutingPlayer(**player_data)
                db.add(p)
                all_db_players.append(p)

            # NON calcolare scores qui: verranno calcolati da recalculate_all()
            # dopo che tutte le sorgenti hanno popolato i dati raw

            imported += 1
            if imported % 200 == 0:
                db.commit()
                now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                print(f"[{now_str}] → Kaggle: {imported}/{limit} giocatori importati...")
                if progress_cb:
                    progress_cb(imported)

    db.commit()
    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] Importazione Kaggle completata: {imported} record (solo anagrafica).")
    return imported


def _int(val) -> int:
    try:
        return int(float(val)) if val and str(val).strip() != "" else None
    except Exception:
        return None


def _float(val) -> float:
    try:
        return float(val) if val and str(val).strip() != "" else None
    except Exception:
        return None