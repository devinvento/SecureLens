"""Remove form_report column from tool_jobs

Revision ID: 1234567890ad
Revises: 1234567890ac
Create Date: 2026-03-14 07:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '1234567890ad'
down_revision: Union[str, None] = '1234567890ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('tool_jobs')]

    if 'form_report' in existing_columns:
        op.drop_column('tool_jobs', 'form_report')


def downgrade() -> None:
    op.add_column('tool_jobs', sa.Column('form_report', sa.Text(), nullable=True))
