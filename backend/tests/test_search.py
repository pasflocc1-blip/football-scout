"""
tests/test_search.py
Esegui con: docker compose exec backend pytest -v
"""
import pytest
from unittest.mock import MagicMock
from app.services.search import build_conditions, search_players
from app.services.scoring import compute_scores
from app.models.models import ScoutingPlayer


# ── Test build_conditions ────────────────────────────────────────

def test_build_conditions_empty():
    assert build_conditions("") == []

def test_build_conditions_single():
    conds = build_conditions("mancino")
    assert len(conds) == 1

def test_build_conditions_multiple():
    conds = build_conditions("centravanti mancino bravo di testa under 25")
    # attesi: centravanti, mancino, bravo di testa, under 25
    assert len(conds) == 4

def test_build_conditions_case_insensitive():
    conds_lower = build_conditions("veloce")
    conds_upper = build_conditions("VELOCE")
    assert len(conds_lower) == len(conds_upper)


# ── Test compute_scores ───────────────────────────────────────────

def make_player(**kwargs):
    defaults = dict(
        pace=70, shooting=70, passing=70,
        dribbling=70, defending=70, physical=70,
        aerial_duels_won_pct=60.0,
    )
    defaults.update(kwargs)
    return MagicMock(spec=ScoutingPlayer, **defaults)

def test_heading_score_high():
    p = make_player(aerial_duels_won_pct=90, physical=85)
    scores = compute_scores(p)
    assert scores["heading_score"] > 80

def test_heading_score_low():
    p = make_player(aerial_duels_won_pct=10, physical=40)
    scores = compute_scores(p)
    assert scores["heading_score"] < 40

def test_scores_never_exceed_100():
    p = make_player(pace=100, shooting=100, passing=100,
                    dribbling=100, defending=100, physical=100,
                    aerial_duels_won_pct=100)
    scores = compute_scores(p)
    for val in scores.values():
        assert val <= 100.0

def test_scores_with_none_values():
    p = make_player(pace=None, physical=None, aerial_duels_won_pct=None,
                    dribbling=None, passing=None, defending=None)
    scores = compute_scores(p)
    # Non deve sollevare eccezioni e i valori devono essere numeri
    for val in scores.values():
        assert isinstance(val, float)
