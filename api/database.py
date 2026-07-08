"""Conexão SQLAlchemy (PostgreSQL padrão; SQLite opcional para testes)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from api.config import settings

_url = settings.database_url
_kwargs: dict = {"pool_pre_ping": True}

if _url.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Pool adequado a poucos clientes desktop concurrentes (rede local / servidor).
    _kwargs["pool_size"] = 5
    _kwargs["max_overflow"] = 10

engine = create_engine(_url, **_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
