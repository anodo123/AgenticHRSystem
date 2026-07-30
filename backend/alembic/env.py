"""Alembic configuration."""

# Alembic init script
import sys
from pathlib import Path

# Add app to path for model imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from app.core.config import get_settings
from app.db.base import Base

config = context.config

# Settings from environment
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Model imports
from app.models import *  # noqa: F401, F403

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
