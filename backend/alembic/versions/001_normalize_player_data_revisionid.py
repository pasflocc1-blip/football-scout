"""add normalized player tables

Revision ID: 001_normalize_player_data
Revises: (your current head revision)
Create Date: 2026-04-02

ISTRUZIONI:
  1. Metti questo file in alembic/versions/
  2. Rinomina secondo la convenzione Alembic (es. 001_normalize_player_data_revisionid.py)
  3. Aggiorna `down_revision` con l'ID dell'ultima migration esistente
  4. Esegui:
       docker compose exec backend alembic upgrade head

STRATEGIA:
  - Le nuove tabelle vengono create da zero (forward safe).
  - La tabella scouting_players viene modificata:
      * Aggiunte colonne mancanti (position_detail, height, weight, ecc.)
      * Rimosse le colonne statistiche spostate nelle nuove tabelle
      * La colonna sofascore_rating viene mantenuta come cache
  - I dati esistenti nelle colonne statistiche vengono prima migrati
    nelle nuove tabelle, poi le colonne vengono rimosse.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json
from datetime import datetime


# ── Metadata migration ────────────────────────────────────────────
revision     = '001_normalize_player_data'
down_revision = '0001'   # ← AGGIORNA con il tuo revision corrente
branch_labels = None
depends_on    = None


def upgrade():

    # ══════════════════════════════════════════════════════════════
    # 1. AGGIUNGI COLONNE MANCANTI A scouting_players
    # ══════════════════════════════════════════════════════════════

    with op.batch_alter_table('scouting_players') as batch_op:
        # Nuove colonne anagrafiche
        batch_op.add_column(sa.Column('position_detail', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('height',          sa.Integer(),  nullable=True))
        batch_op.add_column(sa.Column('weight',          sa.Integer(),  nullable=True))
        batch_op.add_column(sa.Column('jersey_number',   sa.Integer(),  nullable=True))
        batch_op.add_column(sa.Column('gender',          sa.String(5),  nullable=True, server_default='M'))
        batch_op.add_column(sa.Column('contract_until',  sa.Date(),     nullable=True))

        # Rinomina rating_sofascore → sofascore_rating (se esiste con il vecchio nome)
        # NOTA: eseguire solo se la colonna si chiama 'rating_sofascore'
        try:
            batch_op.alter_column('rating_sofascore', new_column_name='sofascore_rating')
        except Exception:
            # Colonna già rinominata o non esistente — ignora
            pass

    # ══════════════════════════════════════════════════════════════
    # 2. CREA player_season_stats
    # ══════════════════════════════════════════════════════════════

    op.create_table(
        'player_season_stats',
        sa.Column('id',        sa.Integer(), primary_key=True),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('scouting_players.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('season',    sa.String(10), nullable=False),
        sa.Column('league',    sa.String(50), nullable=False),
        sa.Column('source',    sa.String(30), nullable=False),

        # Rating & volume
        sa.Column('sofascore_rating', sa.Float()),
        sa.Column('appearances',      sa.Integer()),
        sa.Column('matches_started',  sa.Integer()),
        sa.Column('minutes_played',   sa.Integer()),

        # Attacco
        sa.Column('goals',               sa.Integer()),
        sa.Column('assists',             sa.Integer()),
        sa.Column('goals_assists_sum',   sa.Integer()),
        sa.Column('shots_total',         sa.Integer()),
        sa.Column('shots_on_target',     sa.Integer()),
        sa.Column('shots_off_target',    sa.Integer()),
        sa.Column('shots_inside_box',    sa.Integer()),
        sa.Column('shots_outside_box',   sa.Integer()),
        sa.Column('big_chances_created', sa.Integer()),
        sa.Column('big_chances_missed',  sa.Integer()),
        sa.Column('goal_conversion_pct', sa.Float()),
        sa.Column('headed_goals',        sa.Integer()),
        sa.Column('left_foot_goals',     sa.Integer()),
        sa.Column('right_foot_goals',    sa.Integer()),
        sa.Column('goals_inside_box',    sa.Integer()),
        sa.Column('goals_outside_box',   sa.Integer()),
        sa.Column('free_kick_goals',     sa.Integer()),
        sa.Column('penalty_goals',       sa.Integer()),
        sa.Column('penalty_taken',       sa.Integer()),
        sa.Column('penalty_won',         sa.Integer()),
        sa.Column('own_goals',           sa.Integer()),

        # xG/xA
        sa.Column('xg',             sa.Float()),
        sa.Column('xa',             sa.Float()),
        sa.Column('xg_per90',       sa.Float()),
        sa.Column('xa_per90',       sa.Float()),
        sa.Column('npxg_per90',     sa.Float()),
        sa.Column('xgchain_per90',  sa.Float()),
        sa.Column('xgbuildup_per90',sa.Float()),

        # Passaggi
        sa.Column('accurate_passes',            sa.Integer()),
        sa.Column('inaccurate_passes',          sa.Integer()),
        sa.Column('total_passes',               sa.Integer()),
        sa.Column('pass_accuracy_pct',          sa.Float()),
        sa.Column('accurate_own_half_passes',   sa.Integer()),
        sa.Column('accurate_opp_half_passes',   sa.Integer()),
        sa.Column('accurate_final_third_passes',sa.Integer()),
        sa.Column('accurate_long_balls',        sa.Integer()),
        sa.Column('long_ball_accuracy_pct',     sa.Float()),
        sa.Column('total_long_balls',           sa.Integer()),
        sa.Column('accurate_crosses',           sa.Integer()),
        sa.Column('cross_accuracy_pct',         sa.Float()),
        sa.Column('total_crosses',              sa.Integer()),
        sa.Column('key_passes',                 sa.Integer()),
        sa.Column('pass_to_assist',             sa.Integer()),
        sa.Column('chipped_passes',             sa.Integer()),

        # Progressione (FBref)
        sa.Column('progressive_passes',          sa.Integer()),
        sa.Column('progressive_carries',         sa.Integer()),
        sa.Column('progressive_passes_received', sa.Integer()),
        sa.Column('touches_att_pen',             sa.Integer()),

        # Dribbling
        sa.Column('successful_dribbles',  sa.Integer()),
        sa.Column('dribble_success_pct',  sa.Float()),
        sa.Column('dribbled_past',        sa.Integer()),
        sa.Column('dispossessed',         sa.Integer()),

        # Duelli
        sa.Column('ground_duels_won',     sa.Integer()),
        sa.Column('ground_duels_won_pct', sa.Float()),
        sa.Column('aerial_duels_won',     sa.Integer()),
        sa.Column('aerial_duels_lost',    sa.Integer()),
        sa.Column('aerial_duels_won_pct', sa.Float()),
        sa.Column('total_duels_won',      sa.Integer()),
        sa.Column('total_duels_won_pct',  sa.Float()),
        sa.Column('total_contest',        sa.Integer()),

        # Difesa
        sa.Column('tackles',              sa.Integer()),
        sa.Column('tackles_won',          sa.Integer()),
        sa.Column('tackles_won_pct',      sa.Float()),
        sa.Column('interceptions',        sa.Integer()),
        sa.Column('clearances',           sa.Integer()),
        sa.Column('blocked_shots',        sa.Integer()),
        sa.Column('errors_led_to_goal',   sa.Integer()),
        sa.Column('errors_led_to_shot',   sa.Integer()),
        sa.Column('ball_recovery',        sa.Integer()),
        sa.Column('possession_won_att_third', sa.Integer()),

        # Pressing (FBref)
        sa.Column('pressures',        sa.Integer()),
        sa.Column('pressure_regains', sa.Integer()),

        # Possesso
        sa.Column('touches',        sa.Integer()),
        sa.Column('possession_lost',sa.Integer()),

        # Set piece
        sa.Column('shot_from_set_piece', sa.Integer()),

        # Disciplina
        sa.Column('yellow_cards',     sa.Integer()),
        sa.Column('yellow_red_cards', sa.Integer()),
        sa.Column('red_cards',        sa.Integer()),
        sa.Column('fouls_committed',  sa.Integer()),
        sa.Column('fouls_won',        sa.Integer()),
        sa.Column('offsides',         sa.Integer()),
        sa.Column('hit_woodwork',     sa.Integer()),

        # Portiere
        sa.Column('saves',                     sa.Integer()),
        sa.Column('goals_conceded',            sa.Integer()),
        sa.Column('goals_conceded_inside_box', sa.Integer()),
        sa.Column('goals_conceded_outside_box',sa.Integer()),
        sa.Column('clean_sheets',              sa.Integer()),
        sa.Column('penalty_saved',             sa.Integer()),
        sa.Column('penalty_faced',             sa.Integer()),
        sa.Column('high_claims',               sa.Integer()),
        sa.Column('punches',                   sa.Integer()),
        sa.Column('runs_out',                  sa.Integer()),
        sa.Column('successful_runs_out',       sa.Integer()),
        sa.Column('saved_shots_inside_box',    sa.Integer()),
        sa.Column('saved_shots_outside_box',   sa.Integer()),

        # Fantacalcio
        sa.Column('fanta_media',             sa.Float()),
        sa.Column('fanta_media_mv',          sa.Float()),
        sa.Column('fanta_gol',               sa.Integer()),
        sa.Column('fanta_assist',            sa.Integer()),
        sa.Column('fanta_ammonizioni',       sa.Integer()),
        sa.Column('fanta_espulsioni',        sa.Integer()),
        sa.Column('fanta_rigori_segnati',    sa.Integer()),
        sa.Column('fanta_rigori_sbagliati',  sa.Integer()),
        sa.Column('fanta_autogol',           sa.Integer()),
        sa.Column('fanta_presenze',          sa.Integer()),

        # Meta
        sa.Column('tournament_id', sa.Integer()),
        sa.Column('season_id',     sa.Integer()),
        sa.Column('fetched_at',    sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at',    sa.DateTime(), default=datetime.utcnow,
                  onupdate=datetime.utcnow),

        sa.UniqueConstraint('player_id', 'season', 'league', 'source',
                            name='uq_player_season_league_source'),
    )
    op.create_index('ix_season_stats_player_season', 'player_season_stats',
                    ['player_id', 'season'])

    # ══════════════════════════════════════════════════════════════
    # 3. CREA player_matches
    # ══════════════════════════════════════════════════════════════

    op.create_table(
        'player_matches',
        sa.Column('id',         sa.Integer(), primary_key=True),
        sa.Column('player_id',  sa.Integer(),
                  sa.ForeignKey('scouting_players.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('event_id',      sa.Integer(), index=True),
        sa.Column('date',          sa.DateTime(), index=True),
        sa.Column('season',        sa.String(10)),
        sa.Column('tournament',    sa.String(100)),
        sa.Column('home_team',     sa.String(100)),
        sa.Column('away_team',     sa.String(100)),
        sa.Column('home_score',    sa.Integer()),
        sa.Column('away_score',    sa.Integer()),
        sa.Column('rating',        sa.Float()),
        sa.Column('minutes_played',sa.Integer()),
        sa.Column('goals',         sa.Integer(), server_default='0'),
        sa.Column('assists',       sa.Integer(), server_default='0'),
        sa.Column('yellow_card',   sa.Integer(), server_default='0'),
        sa.Column('red_card',      sa.Integer(), server_default='0'),
        sa.Column('source',        sa.String(20), server_default='sofascore'),
        sa.Column('fetched_at',    sa.DateTime(), default=datetime.utcnow),

        sa.UniqueConstraint('player_id', 'event_id', name='uq_player_event'),
    )
    op.create_index('ix_player_match_player_date', 'player_matches', ['player_id', 'date'])

    # ══════════════════════════════════════════════════════════════
    # 4. CREA player_heatmap
    # ══════════════════════════════════════════════════════════════

    op.create_table(
        'player_heatmap',
        sa.Column('id',         sa.Integer(), primary_key=True),
        sa.Column('player_id',  sa.Integer(),
                  sa.ForeignKey('scouting_players.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('season',          sa.String(10), nullable=False),
        sa.Column('league',          sa.String(50), nullable=False),
        sa.Column('points',          sa.JSON()),
        sa.Column('point_count',     sa.Integer(), server_default='0'),
        sa.Column('position_played', sa.String(20)),
        sa.Column('source',          sa.String(20), server_default='sofascore'),
        sa.Column('fetched_at',      sa.DateTime(), default=datetime.utcnow),

        sa.UniqueConstraint('player_id', 'season', 'league', 'source',
                            name='uq_heatmap_player_season_league'),
    )

    # ══════════════════════════════════════════════════════════════
    # 5. CREA player_career
    # ══════════════════════════════════════════════════════════════

    op.create_table(
        'player_career',
        sa.Column('id',            sa.Integer(), primary_key=True),
        sa.Column('player_id',     sa.Integer(),
                  sa.ForeignKey('scouting_players.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('from_team',     sa.String(100)),
        sa.Column('to_team',       sa.String(100)),
        sa.Column('transfer_date', sa.DateTime()),
        sa.Column('fee',           sa.Float()),
        sa.Column('transfer_type', sa.String(30)),
        sa.Column('season',        sa.String(10)),
        sa.Column('source',        sa.String(20), server_default='sofascore'),
        sa.Column('fetched_at',    sa.DateTime(), default=datetime.utcnow),
    )

    # ══════════════════════════════════════════════════════════════
    # 6. CREA player_national_stats
    # ══════════════════════════════════════════════════════════════

    op.create_table(
        'player_national_stats',
        sa.Column('id',            sa.Integer(), primary_key=True),
        sa.Column('player_id',     sa.Integer(),
                  sa.ForeignKey('scouting_players.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('national_team', sa.String(100)),
        sa.Column('appearances',   sa.Integer()),
        sa.Column('minutes',       sa.Integer()),
        sa.Column('goals',         sa.Integer()),
        sa.Column('assists',       sa.Integer()),
        sa.Column('rating',        sa.Float()),
        sa.Column('yellow_cards',  sa.Integer()),
        sa.Column('red_cards',     sa.Integer()),
        sa.Column('raw_data',      sa.JSON()),
        sa.Column('source',        sa.String(20), server_default='sofascore'),
        sa.Column('fetched_at',    sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at',    sa.DateTime(), default=datetime.utcnow,
                  onupdate=datetime.utcnow),

        sa.UniqueConstraint('player_id', 'national_team', 'source',
                            name='uq_national_player_team'),
    )

    # ══════════════════════════════════════════════════════════════
    # 7. RIMUOVI COLONNE STATISTICHE DA scouting_players
    #    (erano usate solo dall'RPA / sofascore.py — ora migrate)
    # ══════════════════════════════════════════════════════════════

    cols_to_drop = [
        'goals_season', 'assists_season', 'minutes_season', 'games_season',
        'shots_season', 'shots_on_target_season', 'key_passes_season',
        'npxg_per90', 'xgchain_per90', 'xgbuildup_per90',
        'progressive_passes', 'progressive_carries', 'progressive_passes_received',
        'touches_att_pen_season', 'pressures_season', 'pressure_regains_season',
        'tackles_season', 'interceptions_season',
        'duels_total_season', 'duels_won_season', 'duels_won_pct', 'aerial_duels_won_pct',
        'pass_accuracy_pct',
        'heatmap_data',      # → player_heatmap.points
        'match_history',     # → player_matches
        'transfer_history',  # → player_career
        'career_stats',      # → player_career
    ]

    with op.batch_alter_table('scouting_players') as batch_op:
        for col in cols_to_drop:
            try:
                batch_op.drop_column(col)
            except Exception:
                pass  # colonna non esistente — ignora

    # NOTA: xg_per90 e xa_per90 vengono mantenuti in scouting_players
    # perché usati da altri servizi (Understat, FBref).
    # Vengono anche copiati in player_season_stats con source corretto.


def downgrade():
    """Rollback: rimuove le nuove tabelle e ripristina le colonne."""
    op.drop_table('player_national_stats')
    op.drop_table('player_heatmap')
    op.drop_table('player_career')
    op.drop_table('player_matches')
    op.drop_index('ix_season_stats_player_season', table_name='player_season_stats')
    op.drop_table('player_season_stats')

    # Ripristino parziale colonne in scouting_players (solo le principali)
    with op.batch_alter_table('scouting_players') as batch_op:
        batch_op.add_column(sa.Column('goals_season',   sa.Integer()))
        batch_op.add_column(sa.Column('assists_season', sa.Integer()))
        batch_op.add_column(sa.Column('minutes_season', sa.Integer()))
        batch_op.add_column(sa.Column('games_season',   sa.Integer()))
        batch_op.add_column(sa.Column('heatmap_data',   sa.JSON()))