"""Add sources column to tool_jobs

Revision ID: abc123def456
Revises: 1234567890ab
Create Date: 2026-03-06 13:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abc123def456'
down_revision: Union[str, None] = '1234567890ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use inspector to check if column exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tool_jobs')]
    
    if 'sources' not in columns:
        op.add_column('tool_jobs', sa.Column('sources', sa.String(), nullable=True, server_default=''))
        op.alter_column('tool_jobs', 'sources', server_default=None)


def downgrade() -> None:
    # Use inspector to check if column exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tool_jobs')]
    
    if 'sources' in columns:
        op.drop_column('tool_jobs', 'sources')
