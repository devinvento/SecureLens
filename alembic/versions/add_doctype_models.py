"""add_doctype_models

Revision ID: add_doctype_models
Revises: add_mode_column
Create Date: 2026-03-13 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'add_doctype_models'
down_revision: Union[str, None] = 'add_mode_column'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if 'doctypes' not in existing_tables:
        op.create_table('doctypes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('table_name', sa.String(), nullable=False),
            sa.Column('is_submittable', sa.Boolean(), nullable=True),
            sa.Column('module', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('modified_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
            sa.UniqueConstraint('table_name')
        )
        op.create_index(op.f('ix_doctypes_id'), 'doctypes', ['id'], unique=False)
        op.create_index(op.f('ix_doctypes_name'), 'doctypes', ['name'], unique=True)

    if 'docfields' not in existing_tables:
        op.create_table('docfields',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('parent_doctype_id', sa.Integer(), nullable=False),
            sa.Column('label', sa.String(), nullable=False),
            sa.Column('fieldname', sa.String(), nullable=False),
            sa.Column('fieldtype', sa.String(), nullable=False),
            sa.Column('options', sa.Text(), nullable=True),
            sa.Column('reqd', sa.Boolean(), nullable=True),
            sa.Column('unique', sa.Boolean(), nullable=True),
            sa.Column('search_index', sa.Boolean(), nullable=True),
            sa.Column('default_value', sa.String(), nullable=True),
            sa.Column('idx', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['parent_doctype_id'], ['doctypes.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_docfields_id'), 'docfields', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('docfields')
    op.drop_table('doctypes')
