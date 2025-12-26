"""Configuration management module"""
import os
from pathlib import Path
from typing import Any
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)


def get_instance_path() -> Path:
    """Get the current instance path from environment or default"""
    instance_path = os.environ.get("MOSAIC_INSTANCE_PATH")
    if instance_path:
        return Path(instance_path).expanduser()
    return Path.home() / ".mosaic"


def get_config_file() -> Path | None:
    """Get config file path if it exists"""
    instance_path = get_instance_path()
    config_file = instance_path / "config.toml"
    if config_file.exists():
        return config_file
    return None


class Settings(BaseSettings):
    """System configuration settings"""

    # Application basic configuration
    app_name: str = "Mosaic"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database configuration
    database_url: str = "sqlite:///./data/mosaic.db"

    # Authentication configuration
    secret_key: str = (
        "change-me-in-production-please-use-a-secure-random-key"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Email service configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@mosaic.dev"
    smtp_from_name: str = "Mosaic"

    # Verification code configuration
    verification_code_expire_minutes: int = 10
    verification_code_length: int = 6

    # CORS configuration
    cors_origins: list[str] = ["http://localhost:3000"]

    # Server configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Logging configuration
    logging_backend_log: str = "./logs/backend.log"
    logging_runtime_log: str = "./logs/runtime.log"
    logging_level: str = "INFO"

    # Runtime configuration
    runtime_max_threads: int = 4
    runtime_zmq_pull_port: int = 5555
    runtime_zmq_pub_port: int = 5556

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to include TOML file"""
        config_file = get_config_file()
        if config_file:
            toml_settings = TomlConfigSettingsSource(
                settings_cls, toml_file=config_file
            )
            return (
                init_settings,
                env_settings,
                dotenv_settings,
                toml_settings,
                file_secret_settings,
            )
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


# Global settings instance
settings = Settings()
