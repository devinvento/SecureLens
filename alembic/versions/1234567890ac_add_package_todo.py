"""Add package_todo table

Revision ID: 1234567890ac
Revises: 1234567890ab
Create Date: 2026-03-14 07:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '1234567890ac'
down_revision: Union[str, None] = '72675d407b0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if 'package_todo' not in existing_tables:
        op.create_table('package_todo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('target', sa.String(), nullable=False),
        sa.Column('package_name', sa.String(), nullable=False),
        sa.Column('section', sa.String(), nullable=True),
        sa.Column('data', sa.Text(), nullable=True),
        sa.Column('execution_time', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_package_todo_id'), 'package_todo', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_package_todo_id'), table_name='package_todo')
    op.drop_table('package_todo')
