from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from salesforge.settings import Settings

from .conftest import TEST_DB


def test_migrations_build_the_same_schema_as_the_models(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    url = Settings(database_url=TEST_DB).database_url.replace("/salesforge_test", "/salesforge_migrations")
    admin = create_engine(Settings(database_url=TEST_DB).database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS salesforge_migrations"))
        conn.execute(text("CREATE DATABASE salesforge_migrations"))
    admin.dispose()

    from salesforge import db

    monkeypatch.setenv("DATABASE_URL", url)
    db.get_engine.cache_clear()
    from salesforge.settings import get_settings

    get_settings.cache_clear()
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        command.upgrade(cfg, "head")
        command.check(cfg)  # raises if the models and the migrations disagree
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
    finally:
        db.get_engine.cache_clear()
        get_settings.cache_clear()
