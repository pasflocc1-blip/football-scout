"""create initial tables

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'my_team',
        sa.Column('id',         sa.Integer,     primary_key=True),
        sa.Column('name',       sa.String(100), nullable=False),
        sa.Column('formation',  sa.String(20)),
        sa.Column('league',     sa.String(100)),
        sa.Column('season',     sa.String(20)),
        sa.Column('coach',      sa.String(100)),
        sa.Column('budget',     sa.Float),
        sa.Column('notes',      sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()')),
    )

    op.create_table(
        'team_traits',
        sa.Column('id',          sa.Integer,     primary_key=True),
        sa.Column('team_id',     sa.Integer,     sa.ForeignKey('my_team.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trait_type',  sa.Enum('positive', 'negative', name='traittype'), nullable=False),
        sa.Column('description', sa.Text,        nullable=False),
        sa.Column('priority',    sa.Integer,     server_default='1'),
    )

    op.create_table(
        'my_players',
        sa.Column('id',             sa.Integer,     primary_key=True),
        sa.Column('team_id',        sa.Integer,     sa.ForeignKey('my_team.id', ondelete='CASCADE')),
        sa.Column('name',           sa.String(100), nullable=False),
        sa.Column('position',       sa.String(20)),
        sa.Column('age',            sa.Integer),
        sa.Column('preferred_foot', sa.String(10)),
        sa.Column('rating',         sa.Float),
    )

    op.create_table(
        'scouting_players',
        sa.Column('id',                    sa.Integer,     primary_key=True),
        sa.Column('external_id',           sa.String(50),  unique=True, index=True),
        sa.Column('name',                  sa.String(100), nullable=False),
        sa.Column('position',              sa.String(20)),
        sa.Column('club',                  sa.String(100)),
        sa.Column('nationality',           sa.String(50)),
        sa.Column('age',                   sa.Integer),
        sa.Column('preferred_foot',        sa.String(10)),
        sa.Column('pace',                  sa.Integer),
        sa.Column('shooting',              sa.Integer),
        sa.Column('passing',               sa.Integer),
        sa.Column('dribbling',             sa.Integer),
        sa.Column('defending',             sa.Integer),
        sa.Column('physical',              sa.Integer),
        sa.Column('xg_per90',              sa.Float),
        sa.Column('xa_per90',              sa.Float),
        sa.Column('progressive_passes',    sa.Integer),
        sa.Column('aerial_duels_won_pct',  sa.Float),
        sa.Column('heading_score',         sa.Float),
        sa.Column('build_up_score',        sa.Float),
        sa.Column('defensive_score',       sa.Float),
        sa.Column('updated_at',            sa.DateTime, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('scouting_players')
    op.drop_table('my_players')
    op.drop_table('team_traits')
    op.drop_table('my_team')
    op.execute("DROP TYPE IF EXISTS traittype")
