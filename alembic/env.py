import os
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# Import SQLModel metadata for Alembic auto-generation
from sqlmodel import (  # noqa: E402 - must be after load_dotenv to ensure env vars are available
    SQLModel,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def process_revision_directives(context, revision, directives):
    """Generate sequential revision IDs (001, 002, etc.)."""
    if config.cmd_opts and getattr(config.cmd_opts, 'autogenerate', False):
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            return

    # Find highest existing numeric revision
    from alembic.script import ScriptDirectory

    script_dir = ScriptDirectory.from_config(config)

    max_num = 0
    for rev in script_dir.walk_revisions():
        try:
            num = int(rev.revision)
            max_num = max(max_num, num)
        except (ValueError, TypeError):
            # Skip non-numeric revisions
            continue

    # Generate next sequential ID
    if directives and hasattr(directives[0], "rev_id"):
        directives[0].rev_id = f"{max_num + 1:03d}"


# Allow DATABASE_URL env var to override alembic.ini
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
