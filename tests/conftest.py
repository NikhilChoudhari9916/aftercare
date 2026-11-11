import os

# Set before any app import so tests never read a developer's .env or touch a real database.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"

from collections.abc import Callable, Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.auth.google import get_identity_provider  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.db import get_session, init_db, make_engine  # noqa: E402
from app.documents.deps import get_job_runner, get_llm_or_503  # noqa: E402
from app.jobs.runner import InlineJobRunner  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.auth.helpers import FakeProvider, make_settings  # noqa: E402
from tests.fakes import FakeLLM  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(storage_dir=tmp_path / "storage")


@pytest.fixture
def make_app(engine: Engine, provider: FakeProvider, llm: FakeLLM) -> Callable[[Settings], FastAPI]:
    def build(settings: Settings) -> FastAPI:
        app = create_app()

        def session_override() -> Iterator[Session]:
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_identity_provider] = lambda: provider
        app.dependency_overrides[get_llm_or_503] = lambda: llm
        app.dependency_overrides[get_job_runner] = lambda: InlineJobRunner()
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
