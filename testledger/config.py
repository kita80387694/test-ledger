from functools import lru_cache
from typing import Annotated

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DemoPassword = Annotated[SecretStr, Field(min_length=8, max_length=256)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    database_url: str


class AuthSettings(BaseSettings):
    model_config = Settings.model_config

    jwt_secret: Annotated[SecretStr, Field(min_length=32)]
    token_ttl_minutes: Annotated[int, Field(ge=1, le=1440)] = 60


class DemoViewerSettings(BaseSettings):
    model_config = Settings.model_config

    demo_viewer_password: DemoPassword


class DemoHTTPSettings(DemoViewerSettings):
    demo_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8000")


class DemoSettings(DemoHTTPSettings):
    demo_tester_password: DemoPassword


class DemoSeedSettings(DemoViewerSettings):
    demo_tester_password: DemoPassword
    demo_admin_password: DemoPassword


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
