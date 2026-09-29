"""Alembic environment configuration."""

from __future__ import annotations

import importlib.util
import os
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.core.config import settings
from backend.app.models import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for 'autogenerate' support
target_metadata = Base.metadata


def _resolve_db_url(url: str) -> str:
    clean = url.strip()
    if clean.startswith("jdbc:"):
        clean = clean[5:]
    if clean.startswith("postgres://"):
        clean = "postgresql://" + clean[11:]
    if clean.startswith("postgresql://") and importlib.util.find_spec("psycopg") is None:
        clean = "postgresql+psycopg2://" + clean[len("postgresql://"):]
    return clean


# Override sqlalchemy.url with dynamic application settings
resolved_db_url = _resolve_db_url(settings.DATABASE_URL)
config.set_main_option("sqlalchemy.url", resolved_db_url)


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
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = resolved_db_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
