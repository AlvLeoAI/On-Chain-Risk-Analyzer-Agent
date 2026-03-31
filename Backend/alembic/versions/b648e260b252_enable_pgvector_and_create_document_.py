"""enable_pgvector_and_create_document_embeddings

Revision ID: b648e260b252
Revises: 9f94f7d47fc0
Create Date: 2026-03-23 18:49:54.366041

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b648e260b252'
down_revision: Union[str, Sequence[str], None] = '9f94f7d47fc0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable the pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Create the document_embeddings table
    op.create_table(
        'document_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['project_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    # Add an index for faster similarity search
    # Note: For small datasets, we might not need HNSW yet, but it's good for scale.
    # For now, we'll rely on the default index if any.
    # op.execute("CREATE INDEX ON document_embeddings USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('document_embeddings')
    # We might not want to drop the extension as it could be used by other tables/apps
    # op.execute("DROP EXTENSION IF EXISTS vector")
