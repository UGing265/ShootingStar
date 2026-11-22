"""Shared pytest configuration and fixtures for ShootingStar test suite."""

import os
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shootingstar.adapters.db.session import get_database_url, load_env_file

load_env_file(override=True)


@pytest.fixture(scope="session")
def migrated_test_engine():
    """Migrates and connects to the main database (SHOOTINGSTAR_DATABASE_URL).

    Project rule (user decision 2026-11-22): tests run directly on the main DB.
    Tests must only create rows with their own ids and delete exactly those rows
    in a finally block; never bulk delete, truncate, drop or downgrade.
    """
    test_url = get_database_url()

    ini_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini")
    if not os.path.exists(ini_path):
        ini_path = "alembic.ini"
    alembic_cfg = Config(ini_path)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(test_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_test_engine):
    with Session(migrated_test_engine) as session:
        yield session
        session.rollback()
