"""Shared pytest configuration and fixtures for ShootingStar test suite."""

import os
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shootingstar.adapters.db.session import get_database_url


@pytest.fixture(scope="session")
def migrated_test_engine():
    """Ensures test database is fully migrated via Alembic, testing migration integrity."""
    test_url = get_database_url(test_mode=True)
    os.environ["SHOOTINGSTAR_DATABASE_URL"] = test_url

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(test_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_test_engine):
    with Session(migrated_test_engine) as session:
        yield session
        session.rollback()
