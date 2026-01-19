"""Alembic migration environment configuration.

Configured for async SQLAlchemy with PostgreSQL.
Loads database URL from environment variable DATABASE_URL.
"""

import asyncio
import os
import sys
from urllib.parse import urlparse
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Add app to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Import Base and all models for autogenerate support
from app.stores.postgres import Base
from app.models import GoldenSku, Merchant, Offer, RawOffer, PatternPhrase, PatternSuggestion  # noqa: F401

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment.

    Converts Railway's postgresql:// URL to postgresql+asyncpg:// for async migrations.
    """
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/market_compass",
    )
    # Railway provides postgresql:// but we need postgresql+asyncpg:// for async
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    url = get_url()
    host = urlparse(url).hostname or ""
    connect_args: dict[str, object] = {}
    # Railway internal Postgres rejects SSL negotiation; disable SSL explicitly.
    if host.endswith(".railway.internal"):
        connect_args = {"ssl": False, "timeout": 20}

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
