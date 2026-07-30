"""Initial migration - Create all tables.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# For enum support
from sqlalchemy.dialects import postgresql
from app.db.base import Base
import app.models  # noqa: F401 - register model metadata

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial schema."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop all tables."""
    Base.metadata.drop_all(bind=op.get_bind())
