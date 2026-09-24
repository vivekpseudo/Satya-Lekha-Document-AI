from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    with factory() as session:
        yield session


def ping_database() -> bool:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1
