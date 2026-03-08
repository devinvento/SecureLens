"""add_mode_column_tool_jobs

Revision ID: add_mode_column
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_mode_column'
down_revision = 'cc67c28d16fa'  # Latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tool_jobs', sa.Column('mode', sa.String(), nullable=True, server_default=''))
    op.add_column('tool_jobs', sa.Column('target_flag', sa.String(), nullable=True, server_default=''))


def downgrade() -> None:
    op.drop_column('tool_jobs', 'mode')
    op.drop_column('tool_jobs', 'target_flag')
