import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(..., alias="BOT_TOKEN")
    database_url: str = Field(..., alias="DATABASE_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    admin_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        alias="ADMIN_IDS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> object:
        if value in (None, "", []):
            return []
        if isinstance(value, str):
            raw_value = value.strip()
            if raw_value.startswith("["):
                return json.loads(raw_value)
            return [int(item.strip()) for item in raw_value.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
