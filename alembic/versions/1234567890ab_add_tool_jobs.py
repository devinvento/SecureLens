"""Add tool_jobs table

Revision ID: 1234567890ab
Revises: b71d374431e7
Create Date: 2026-03-05 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '1234567890ab'
down_revision: Union[str, None] = 'b71d374431e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if 'tool_jobs' not in existing_tables:
        op.create_table('tool_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('target', sa.String(), nullable=False),
        sa.Column('args', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('execution_time', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_tool_jobs_id'), 'tool_jobs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tool_jobs_id'), table_name='tool_jobs')
    op.drop_table('tool_jobs')
