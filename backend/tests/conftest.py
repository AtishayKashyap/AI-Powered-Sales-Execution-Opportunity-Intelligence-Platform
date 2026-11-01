from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from salesforge import models
from salesforge.ai.providers import Provider
from salesforge.api import create_app
from salesforge.db import Base, get_session
from salesforge.pipeline.generate import GeneratorConfig
from salesforge.pipeline.run import run
from salesforge.seed import seed
from salesforge.settings import Settings

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://salesforge:salesforge@localhost:5432/salesforge_test"
)
SMALL = GeneratorConfig(seed=3, n_outlets=400, n_reps=12, n_territories=4)


@pytest.fixture(scope="session")
def seed_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("seed")
    run(out, with_evaluation=False, config=SMALL)
    return out


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = create_engine(Settings(database_url=TEST_DB).database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine, seed_dir: Path) -> Iterator[Session]:
    seed(engine, seed_dir)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def make_client(engine: Engine, provider: Provider | None = None, writes_per_minute: int = 1000) -> TestClient:
    app = create_app(Settings(database_url=TEST_DB, write_requests_per_minute=writes_per_minute), provider=provider)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def session() -> Iterator[Session]:
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = session
    return TestClient(app)


@pytest.fixture
def client(engine: Engine, db: Session) -> TestClient:
    return make_client(engine)


def first_queue_item(db: Session, otype: models.OpportunityType | None = None) -> models.Opportunity:
    q = db.query(models.Opportunity)
    if otype:
        q = q.filter(models.Opportunity.opportunity_type == otype)
    o = q.order_by(models.Opportunity.priority_score.desc()).first()
    assert o is not None
    return o
