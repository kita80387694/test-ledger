from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import Session

from testledger.auth import password_hash
from testledger.config import Settings, get_auth_settings, get_settings
from testledger.db import get_db
from testledger.main import app
from testledger.models import Role, User

TEST_PASSWORD = "fixture-password-42"


class DatabaseTestSettings(BaseSettings):
    model_config = Settings.model_config

    test_database_url: str


@pytest.fixture(scope="session")
def test_engine():
    url = make_url(DatabaseTestSettings().test_database_url)
    primary_url = make_url(get_settings().database_url)
    if url.drivername != "postgresql+psycopg" or url.database != "test_ledger_test":
        pytest.fail("TEST_DATABASE_URL must point to PostgreSQL database test_ledger_test.")
    if primary_url.database == url.database:
        pytest.fail("DATABASE_URL must name a separate database from the test database.")

    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if connection.exec_driver_sql("SELECT current_database()").scalar_one() != url.database:
                pytest.fail("PostgreSQL connected to a different database than TEST_DATABASE_URL names.")
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["database_url"] = url
        command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db(test_engine):
    with test_engine.connect() as connection:
        outer = connection.begin()
        try:
            with Session(
                bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
            ) as session:
                yield session
        finally:
            outer.rollback()


@pytest.fixture(scope="session")
def encoded_test_password():
    return password_hash.hash(TEST_PASSWORD)


@pytest.fixture
def client(db, monkeypatch, encoded_test_password):
    monkeypatch.setenv("JWT_SECRET", "pytest-only-signing-secret-for-test-ledger")
    monkeypatch.setenv("TOKEN_TTL_MINUTES", "60")
    get_auth_settings.cache_clear()
    db.add_all(
        User(username=role.value, role=role, password_hash=encoded_test_password) for role in Role
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db)
        get_auth_settings.cache_clear()


@pytest.fixture
def login(client):
    def authenticate(username="tester"):
        response = client.post(
            "/auth/token",
            data={"grant_type": "password", "username": username, "password": TEST_PASSWORD},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return authenticate
