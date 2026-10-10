"""Database session and engine management."""

import contextlib
import os
from pathlib import Path
from typing import Generator, Iterator, Optional
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

_ENGINE: Optional[Engine] = None
_SESSION_FACTORY: Optional[sessionmaker[Session]] = None


def load_env_file() -> None:
    """Loads key-value pairs from .env into os.environ if present."""
    env_path = Path(".env")
    if not env_path.exists():
        repo_env = Path(__file__).resolve().parents[4] / ".env"
        if repo_env.is_file():
            env_path = repo_env
        else:
            return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = val
def get_database_url(test_mode: bool = False) -> str:
    """Returns database connection URL from environment.

    STRICT SECURITY INVARIANT: No credentials hardcoded in source files.
    """
    load_env_file()
    env_var = "SHOOTINGSTAR_TEST_DATABASE_URL" if test_mode else "SHOOTINGSTAR_DATABASE_URL"
    url = os.environ.get(env_var)
    if not url:
        raise RuntimeError(
            f"Database configuration missing: environment variable '{env_var}' is not set. "
            f"Please configure it in environment or git-ignored .env file."
        )
    return url
def get_engine(database_url: Optional[str] = None, echo: bool = False) -> Engine:
    """Creates or returns SQLAlchemy engine."""
    url = database_url or get_database_url()
    return create_engine(url, echo=echo, pool_pre_ping=True)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextlib.contextmanager
def get_db_session(engine: Optional[Engine] = None) -> Iterator[Session]:
    """Yields a database session and commits upon clean exit."""
    active_engine = engine or get_engine()
    factory = get_session_factory(active_engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
