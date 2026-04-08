"""add fbref tables

Revision ID: 6f312449f1cc
Revises: 001_normalize_player_data
Create Date: 2026-04-07 20:59:24.490166

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6f312449f1cc'
down_revision: Union[str, None] = '001_normalize_player_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. AGGIUNTA COLONNE E INDICI SICURI
    op.add_column('my_players', sa.Column('season', sa.String(length=20), nullable=True))

    # 2. CREAZIONE TABELLE FBREF (Se mancano nel file originale, aggiungile qui sotto)
    # Se le tabelle non compaiono nel file generato, significa che Alembic non le vede.
    # Per ora puliamo gli errori di quelle esistenti:

    op.create_index(op.f('ix_clubs_id'), 'clubs', ['id'], unique=False)
    op.create_index(op.f('ix_my_players_id'), 'my_players', ['id'], unique=False)
    op.create_index(op.f('ix_my_team_id'), 'my_team', ['id'], unique=False)

    # Rimosse tutte le op.alter_column sugli ID che causavano l'errore Identity

    op.drop_constraint('uq_national_player_team', 'player_national_stats', type_='unique')
    op.create_unique_constraint('uq_national_player_team_season', 'player_national_stats',
                                ['player_id', 'national_team', 'season', 'source'])


def downgrade() -> None:
    op.drop_constraint('uq_national_player_team_season', 'player_national_stats', type_='unique')
    op.create_unique_constraint('uq_national_player_team', 'player_national_stats',
                                ['player_id', 'national_team', 'source'])
    op.drop_index(op.f('ix_my_team_id'), table_name='my_team')
    op.drop_index(op.f('ix_my_players_id'), table_name='my_players')
    op.drop_index(op.f('ix_clubs_id'), table_name='clubs')
    op.drop_column('my_players', 'season')