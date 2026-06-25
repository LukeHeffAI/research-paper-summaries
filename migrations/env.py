"""Alembic migration environment.

Wired to:

* the SQLModel metadata (every ``table=True`` row in ``adapters/db/tables.py``),
  so ``--autogenerate`` diffs the models against the DB; and
* ``DATABASE_URL`` from :class:`~downlow.config.settings.Settings` (SQLite under
  ``DATA_DIR`` by default, a Postgres URL after a flip), so migrations target the
  same DB the app uses with no committed local path.

``render_as_batch`` is enabled for SQLite (batch mode rewrites tables for the
``ALTER`` operations SQLite cannot do in place) and is a no-op on Postgres, so the
same migrations apply cleanly on both backends.

``include_object`` excludes the named ``use_alter`` FK (``fk_user_host_voice_id``)
from autogenerate comparison: the mutual user<->voice FK is a documented Alembic
false-positive (alembic #519/#326) -- autogenerate cannot match a post-create
``use_alter`` FK against the reflected schema on Postgres, so ``alembic check``
re-detects it as an ``add_fk`` op on every run (SQLite's batch mode masked this).
The FK still exists and is created by the baseline migration; it is excluded only
from the no-op drift comparison so the 2.2a drift gate is clean on BOTH backends.
"""

from __future__ import annotations

from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy.engine import make_url

from downlow.adapters.db.engine import create_db_engine
from downlow.adapters.db.tables import metadata as sqlmodel_metadata
from downlow.config.settings import Settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate target: the full SQLModel schema.
target_metadata = sqlmodel_metadata()

# The mutual user<->voice FK is added as a post-create ALTER (``use_alter=True``);
# autogenerate cannot reconcile it on Postgres and would report a perpetual
# ``add_fk`` diff. Exclude it by name from the drift comparison (the FK is still
# created by the baseline migration -- this only silences the false positive).
_EXCLUDED_FK_NAMES = {"fk_user_host_voice_id"}


def _include_object(
    obj: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Exclude the ``use_alter`` FK false-positive from autogenerate comparison."""
    return not (type_ == "foreign_key_constraint" and name in _EXCLUDED_FK_NAMES)


def _database_url() -> str:
    """The DB URL: an explicit ``-x dburl=...`` override, else Settings."""
    x_args = context.get_x_argument(as_dictionary=True)
    return x_args.get("dburl") or Settings().database_url


def _is_sqlite(url: str) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DBAPI connection)."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(url),
        compare_type=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (against a live connection)."""
    url = _database_url()
    engine = create_db_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite(url),
            compare_type=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
