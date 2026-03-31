"""add_session_id_to_project_profiles

Revision ID: c3f2cc1fa4f8
Revises: b648e260b252
Create Date: 2026-03-23 19:03:44.376804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f2cc1fa4f8'
down_revision: Union[str, Sequence[str], None] = 'b648e260b252'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('project_profiles', sa.Column('session_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_project_profiles_session_id'), 'project_profiles', ['session_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_project_profiles_session_id'), table_name='project_profiles')
    op.drop_column('project_profiles', 'session_id')
