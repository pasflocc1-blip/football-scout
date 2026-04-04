"""
services/percentiles.py — Fase 4: Percentile rank per ruolo
------------------------------------------------------------
Confronta ogni giocatore SOLO con giocatori dello stesso ruolo (o famiglia).
Un pressing_score di 65 è eccellente per un ST, mediocre per un CM.

Pipeline:
    1. Raggruppa i giocatori per position_family
       (ST/CF/LW/RW → "attacker", CM/DM/AM → "midfielder", ecc.)
    2. Per ogni score dimensionale calcola il percentile rank
       dentro al gruppo: rank(pct=True) * 100
    3. Scrive i valori *_pct nel DB

Soglia minima: solo giocatori con minutes_season >= MIN_MINUTES
vengono usati come riferimento percentile (per evitare sample size piccoli).
Giocatori sotto soglia ricevono percentile = NULL.

Valori degeneri: se tutti i giocatori eligible hanno lo stesso score
(es. pressing=0 perche pressures e NULL in assenza di dati FBref),
il percentile viene impostato a NULL — non ha senso mostrare 100
a tutti solo perche nessuno ha il dato.

Esecuzione:
    POST /admin/recalculate-scores   ← chiama questa fase in automatico
    oppure:
    POST /admin/recalculate-percentiles  ← solo percentili
"""

from __future__ import annotations

MIN_MINUTES = 450   # ~5 partite intere — soglia minima per entrare nel calcolo

# Famiglie di ruoli: confronto avviene DENTRO ogni famiglia
POSITION_FAMILIES: dict[str, str] = {
    "GK":  "goalkeeper",
    "CB":  "defender",
    "LB":  "fullback",
    "RB":  "fullback",
    "WB":  "fullback",
    "DM":  "midfielder",
    "CM":  "midfielder",
    "AM":  "attacking_mid",
    "LW":  "winger",
    "RW":  "winger",
    "SS":  "forward",
    "CF":  "forward",
    "ST":  "forward",
}

# Score per cui calcolare il percentile
# formato: (colonna_score_db, colonna_pct_db)
SCORE_PAIRS: list[tuple[str, str]] = [
    ("finishing_score",     "finishing_pct"),
    ("creativity_score",    "creativity_pct"),
    ("pressing_score",      "pressing_pct"),
    ("carrying_score",      "carrying_pct"),
    ("defending_obj_score", "defending_pct"),
    ("buildup_obj_score",   "buildup_pct"),
]


def _family(position: str | None) -> str:
    """Mappa il codice posizione alla famiglia di ruoli."""
    if not position:
        return "unknown"
    return POSITION_FAMILIES.get(position.strip().upper(), "other")


def recalculate_percentiles(db, progress_cb=None) -> dict:
    """
    Calcola i percentili per ruolo per tutti i giocatori nel DB.

    Richiede pandas — sempre disponibile perché già dipendenza di fbref_source.

    Returns:
        {"players_updated": N, "families": {...}}
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas non installato. Aggiungilo a requirements.txt:\n"
            "    pandas>=2.0"
        )

    from app.models.models import ScoutingPlayer

    # ── 1. Carica tutti i giocatori con almeno un score calcolato ──
    players = db.query(ScoutingPlayer).all()
    if not players:
        return {"players_updated": 0, "families": {}}

    total = len(players)
    print(f"  → percentiles: caricati {total} giocatori")

    # ── 2. Costruisci DataFrame ────────────────────────────────────
    records = []
    for p in players:
        minutes = getattr(p, "minutes_season", None) or 0
        records.append({
            "id":     p.id,
            "family": _family(p.position),
            "eligible": minutes >= MIN_MINUTES,
            **{score_col: getattr(p, score_col, None)
               for score_col, _ in SCORE_PAIRS}
        })

    df = pd.DataFrame(records)

    # ── 3. Calcola percentili per famiglia ─────────────────────────
    # Usa solo i giocatori eligible come riferimento per il rank,
    # ma poi assegna il percentile anche agli ineligible (basandosi
    # sul loro score assoluto rispetto al gruppo eligible).

    result_pcts: dict[int, dict[str, float | None]] = {p.id: {} for p in players}

    family_stats: dict[str, int] = {}

    for score_col, pct_col in SCORE_PAIRS:
        # Giocatori eligible con score non-null
        eligible_mask = df["eligible"] & df[score_col].notna()
        eligible_df   = df[eligible_mask].copy()

        if eligible_df.empty:
            # Nessun dato: tutti NULL
            for pid in result_pcts:
                result_pcts[pid][pct_col] = None
            continue

        # Se tutti i valori sono uguali (es. tutti 0 perche il dato manca
        # per quella metrica, come pressures senza FBref), il percentile
        # non e significativo — lo impostiamo a NULL per tutti.
        if eligible_df[score_col].nunique() <= 1:
            for pid in result_pcts:
                result_pcts[pid][pct_col] = None
            continue

        # Rank percentile dentro ogni famiglia (solo eligible)
        eligible_df[pct_col] = eligible_df.groupby("family")[score_col].rank(
            pct=True, method="average"
        ) * 100.0

        # Dizionario id → percentile per eligible
        pct_map: dict[int, float] = dict(
            zip(eligible_df["id"], eligible_df[pct_col])
        )

        # Per i non-eligible con score: calcola percentile
        # rispetto al gruppo eligible della stessa famiglia
        # (confronto "quanto saresti in quel gruppo")
        for _, row in df[~eligible_mask & df[score_col].notna()].iterrows():
            fam       = row["family"]
            score_val = row[score_col]
            fam_eligible = eligible_df[eligible_df["family"] == fam][score_col]
            if fam_eligible.empty:
                pct_map[row["id"]] = None
            else:
                # percentuale di giocatori eligible che hanno score <= score_val
                pct_val = (fam_eligible <= score_val).mean() * 100.0
                pct_map[row["id"]] = round(pct_val, 1)

        # Assegna NULL per chi non ha score
        for _, row in df[df[score_col].isna()].iterrows():
            pct_map[row["id"]] = None

        for pid, pct_val in pct_map.items():
            result_pcts[pid][pct_col] = (
                round(float(pct_val), 1) if pct_val is not None else None
            )

    # Conta famiglie per debug
    family_counts = df[df["eligible"]].groupby("family").size().to_dict()

    # ── 4. Scrivi nel DB ───────────────────────────────────────────
    updated = 0
    player_map = {p.id: p for p in players}

    for pid, pct_vals in result_pcts.items():
        p = player_map.get(pid)
        if p is None:
            continue
        for pct_col, pct_val in pct_vals.items():
            if hasattr(p, pct_col):
                setattr(p, pct_col, pct_val)
        updated += 1

        if progress_cb and updated % 200 == 0:
            progress_cb(updated, total)

    db.commit()
    print(
        f"  → percentiles: {updated} giocatori aggiornati | "
        f"famiglie: {family_counts}"
    )

    return {
        "players_updated": updated,
        "families": family_counts,
    }