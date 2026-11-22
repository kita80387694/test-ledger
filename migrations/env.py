from alembic import context
from sqlalchemy import create_engine, pool

from testledger.config import get_settings
from testledger.models import Base

config = context.config
database_url = config.attributes.get("database_url") or get_settings().database_url


def run_migrations() -> None:
    options = {"target_metadata": Base.metadata, "compare_type": True, "compare_server_default": True}
    if context.is_offline_mode():
        context.configure(url=database_url, literal_binds=True, **options)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(database_url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, **options)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
