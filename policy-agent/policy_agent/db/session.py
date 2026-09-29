from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from policy_agent.config import Settings, get_settings
from policy_agent.db.models import Base


@dataclass(slots=True)
class Database:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        Base.metadata.drop_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()


def create_database(settings: Settings | None = None) -> Database:
    resolved_settings = settings or get_settings()
    connect_args = {"check_same_thread": False} if resolved_settings.database_url.startswith("sqlite") else {}
    engine = create_engine(
        resolved_settings.database_url,
        connect_args=connect_args,
        future=True,
    )
    return Database(
        settings=resolved_settings,
        engine=engine,
        session_factory=sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        ),
    )


@lru_cache(maxsize=1)
def get_database() -> Database:
    return create_database()
