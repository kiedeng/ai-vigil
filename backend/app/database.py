from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


settings = get_settings()

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    if ":///" in settings.database_url:
        sqlite_path = settings.database_url.split(":///", 1)[1]
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    has_alembic_version = "alembic_version" in table_names

    if has_alembic_version:
        _upgrade_alembic_head()
        return

    Base.metadata.create_all(bind=engine)
    _stamp_alembic_head()


def _stamp_alembic_head() -> None:
    command.stamp(_alembic_config(), "head")


def _upgrade_alembic_head() -> None:
    command.upgrade(_alembic_config(), "head")


def _alembic_config() -> Config:
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    return Config(str(alembic_ini))
