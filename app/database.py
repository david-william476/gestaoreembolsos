from collections.abc import Generator
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Classe comum usada para declarar as tabelas do banco."""
    pass


# SQLite precisa desta opção para funcionar corretamente com o TestClient.
def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db(request: Request) -> Generator[Session, None, None]:
    factory = request.app.state.session_factory
    with factory() as session:
        yield session
