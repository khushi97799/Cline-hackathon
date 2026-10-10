"""Database engine/session setup. SQLite locally, Postgres via DATABASE_URL."""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_URL = f"sqlite:///{ROOT / 'scheme_sniper.db'}"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_SQLITE_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_missing_columns() -> None:
    """Tiny forward-only migration: `create_all` never alters existing tables, so any
    column added to a model after a database was created is added here. Only adds
    nullable columns; never drops or rewrites data."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in have or not col.nullable and col.default is None and col.server_default is None:
                continue
            ddl_type = col.type.compile(dialect=engine.dialect)
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}'))


def init_db():
    from app import models  # noqa: F401  ensure models are registered
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
