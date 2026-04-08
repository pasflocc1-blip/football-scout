"""check fbref

Revision ID: c7f7ef6f8817
Revises: 6f312449f1cc
Create Date: 2026-04-07 21:05:28.580485

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c7f7ef6f8817'
down_revision: Union[str, None] = '6f312449f1cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass