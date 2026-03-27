def calculate_pro_attributes(raw_stats: dict, position: str) -> dict:
    """
    Converte le statistiche reali grezze in valutazioni in centesimi (1-99).
    raw_stats deve contenere: minutes, goals, assists, shots_on_target,
    pass_accuracy, key_passes, dribbles_success, duels_won, aerial_won_pct
    """
    minutes = raw_stats.get("minutes") or 0

    # Se un giocatore ha giocato meno di 270 minuti (3 partite),
    # i dati sono inaffidabili. Diamo voti base bassi o nulli.
    if minutes < 270:
        return {
            "pace": 50, "shooting": 40, "passing": 50,
            "dribbling": 50, "defending": 40, "physical": 50
        }

    # Calcolatore Per 90 (P90)
    p90 = 90.0 / minutes

    # --- DATI GREZZI NORMALIZZATI ---
    goals_p90 = raw_stats.get("goals", 0) * p90
    key_passes_p90 = raw_stats.get("key_passes", 0) * p90
    dribbles_p90 = raw_stats.get("dribbles_success", 0) * p90
    duels_p90 = raw_stats.get("duels_won", 0) * p90

    pass_acc = raw_stats.get("pass_accuracy", 0)
    aerial_pct = raw_stats.get("aerial_won_pct", 0)

    # --- 1. SHOOTING (Tiro) ---
    # Un attaccante di livello mondiale fa circa 0.8+ gol ogni 90 min
    shooting_score = 40 + (goals_p90 / 0.8) * 50
    shooting = min(99, max(20, int(shooting_score)))

    # --- 2. PASSING (Passaggio) ---
    # Mix tra precisione passaggi e passaggi chiave (creatività)
    # 90% accuracy e 3 key_passes p90 = 95+ di passing
    passing_score = (pass_acc * 0.6) + ((key_passes_p90 / 3.0) * 40)
    passing = min(99, max(30, int(passing_score)))

    # --- 3. DRIBBLING ---
    # ~3.5 dribbling riusciti per 90 min è un'ala d'élite
    dribbling_score = 50 + (dribbles_p90 / 3.5) * 45
    dribbling = min(99, max(30, int(dribbling_score)))

    # --- 4. DEFENDING (Difesa) ---
    # I duelli vinti per 90 min indicano l'attività difensiva
    # ~6 duelli difensivi vinti p90 = difensore top
    defending_score = 30 + (duels_p90 / 6.0) * 60

    # Penalizziamo i non-difensori per realismo
    if position in ["Attacker", "Forward"]:
        defending_score *= 0.4
    elif position in ["Midfielder"]:
        defending_score *= 0.8

    defending = min(99, max(15, int(defending_score)))

    # --- 5. PHYSICAL (Fisico) ---
    # Mix tra duelli aerei vinti e volume di duelli totali
    physical_score = 40 + (aerial_pct * 0.4) + (duels_p90 * 3)
    physical = min(99, max(30, int(physical_score)))

    # --- 6. PACE (Velocità) ---
    # Le API base non danno la velocità di punta in km/h.
    # La stimiamo in base al ruolo e all'abilità di dribbling (proxy).
    base_pace = {"Attacker": 75, "Midfielder": 65, "Defender": 60, "Goalkeeper": 40}
    pace_score = base_pace.get(position, 65) + (dribbles_p90 * 5)
    pace = min(99, max(30, int(pace_score)))

    return {
        "pace": pace,
        "shooting": shooting,
        "passing": passing,
        "dribbling": dribbling,
        "defending": defending,
        "physical": physical
    }