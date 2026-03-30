"""
services/position_normalizer.py
---------------------------------
Normalizza i codici posizione provenienti da diverse sorgenti
verso i codici standard del sistema (GK, CB, LB, RB, CM, DM, AM, LW, RW, ST, ecc.)

Problema: diverse sorgenti mandano le posizioni in formati diversi:
  - Kaggle/FIFA: "ST", "CM", "LM", "CAM" (codici)
  - API-Football: "Goalkeeper", "Defender", "Midfielder", "Attacker" (generico)
  - FBref: "GK", "DF", "MF", "FW" (aggregati) o codici completi
  - StatsBomb: posizioni variabili
  - Football-Data.org: "Goalkeeper", "Defender", "Midfielder", "Offence"

Questa mappa garantisce che tutti i giocatori nel DB abbiano
posizioni nel formato standard, così posLabel() in frontend le traduce correttamente.

Uso:
    from app.services.position_normalizer import normalize_position
    position = normalize_position(raw_position_string)
"""

# Mappa completa: tutti i formati noti → codici standard
_POSITION_MAP = {
    # ── Portieri ──────────────────────────────────────
    "goalkeeper": "GK",
    "gk": "GK",
    "portiere": "GK",

    # ── Difensori ──────────────────────────────────────
    "centre-back": "CB",
    "centre back": "CB",
    "center back": "CB",
    "central defender": "CB",
    "cb": "CB",
    "df": "CB",  # FBref generico → CB di default
    "defender": "CB",  # API-Football generico

    "left-back": "LB",
    "left back": "LB",
    "lb": "LB",
    "terzino sinistro": "LB",

    "right-back": "RB",
    "right back": "RB",
    "rb": "RB",
    "terzino destro": "RB",

    "left wing-back": "LWB",
    "left wingback": "LWB",
    "lwb": "LWB",
    "quinto sinistro": "LWB",

    "right wing-back": "RWB",
    "right wingback": "RWB",
    "rwb": "RWB",
    "quinto destro": "RWB",

    "sweeper": "SW",
    "libero": "SW",
    "sw": "SW",

    # ── Centrocampisti ──────────────────────────────────
    "defensive midfield": "DM",
    "defensive midfielder": "DM",
    "holding midfield": "DM",
    "dm": "DM",
    "cdm": "DM",
    "mediano difensivo": "DM",

    "central midfield": "CM",
    "central midfielder": "CM",
    "midfielder": "CM",  # API-Football generico
    "mf": "CM",  # FBref generico
    "cm": "CM",
    "centrocampista": "CM",

    "attacking midfield": "AM",
    "attacking midfielder": "AM",
    "trequartista": "AM",
    "am": "AM",
    "cam": "AM",

    "left midfield": "LM",
    "left midfielder": "LM",
    "lm": "LM",
    "mezzala sinistra": "LM",

    "right midfield": "RM",
    "right midfielder": "RM",
    "rm": "RM",
    "mezzala destra": "RM",

    # ── Attaccanti ──────────────────────────────────────
    "left winger": "LW",
    "left wing": "LW",
    "lw": "LW",
    "ala sinistra": "LW",

    "right winger": "RW",
    "right wing": "RW",
    "rw": "RW",
    "ala destra": "RW",

    "second striker": "SS",
    "seconda punta": "SS",
    "ss": "SS",

    "centre-forward": "ST",
    "center-forward": "ST",
    "centre forward": "ST",
    "center forward": "ST",
    "striker": "ST",
    "attacker": "ST",  # API-Football generico
    "offence": "ST",  # Football-Data.org
    "forward": "ST",
    "fw": "ST",  # FBref generico
    "st": "ST",
    "centravanti": "ST",

    "cf": "CF",
    "prima punta": "CF",
}


def normalize_position(raw: str | None) -> str | None:
    """
    Normalizza una stringa posizione verso il codice standard.

    Args:
        raw: Stringa posizione grezza (qualsiasi fonte)

    Returns:
        Codice posizione standard (es. "CB", "ST", "CM") o None se sconosciuta

    Esempi:
        normalize_position("Centre-Forward") → "ST"
        normalize_position("Left Midfield")  → "LM"
        normalize_position("Goalkeeper")     → "GK"
        normalize_position("ST")             → "ST"
        normalize_position(None)             → None
    """
    if not raw:
        return None

    key = raw.strip().lower()

    # Prima prova match esatto
    if key in _POSITION_MAP:
        return _POSITION_MAP[key]

    # Poi prova il primo elemento se è una lista (es. "ST, CF" da Kaggle)
    if "," in key:
        first = key.split(",")[0].strip()
        if first in _POSITION_MAP:
            return _POSITION_MAP[first]

    # Prova partial match per casi come "Left Midfielder (CM)"
    for pattern, code in _POSITION_MAP.items():
        if pattern in key:
            return code

    # Ritorna il raw in maiuscolo se non riconosciuto (meglio che None)
    return raw.strip().upper()[:5] if raw.strip() else None