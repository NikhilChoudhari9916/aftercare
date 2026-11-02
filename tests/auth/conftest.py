from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.auth.google import get_identity_provider
from app.config import Settings, get_settings
from app.db import get_session, init_db, make_engine
from app.main import create_app
from tests.auth.helpers import FakeProvider, make_settings


@pytest.fixture
def engine() -> Engine:
    engine = make_engine("sqlite://")
    init_db(engine)
    return engine


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def make_app(engine: Engine, provider: FakeProvider) -> Callable[[Settings], FastAPI]:
    def build(settings: Settings) -> FastAPI:
        app = create_app()

        def session_override() -> Iterator[Session]:
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_identity_provider] = lambda: provider
        return app

    return build


@pytest.fixture
def app(make_app: Callable[[Settings], FastAPI], settings: Settings) -> FastAPI:
    return make_app(settings)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def new_client(app: FastAPI) -> Callable[[], TestClient]:
    """Another browser: same app, its own cookies."""
    return lambda: TestClient(app, follow_redirects=False)
