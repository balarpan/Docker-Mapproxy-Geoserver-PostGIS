import os
from pathlib import Path
import socket
from pathlib import Path
from typing import Annotated, Tuple, Type
from pydantic import BaseModel, SecretStr, StrictStr, StrictInt, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    JsonConfigSettingsSource,
)

_conf_pref = Path('.') / Path ('config')

class AuthSettingsPUser(BaseModel):
    """Пользователь по умолчанию в БД"""
    nickname: str
    pwd: SecretStr
    name: str | None = None
    email: str | None = None
    comment: str | None = None
    role: list[str] = []

class AuthSettings(BaseModel):
    """Настройки аутентификации и связанных с ней сервисов"""
    SECRET_KEY: Annotated[SecretStr, Field(description="Generate once via 'openssl rand -hex 32' and put into .env -> MIA__AUTH__SECRET_KEY=\"..\" or in json config (less secure)")]
    ALGORITHM: StrictStr = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 15*60
    REFRESH_TOKEN_EXPIRE_SECONDS: int = 1*24*60*60
    REFRESH_TOKEN_MIN_LIFESPAN_SECONDS: Annotated[int, Field(description="Минимальное время жизни refresh token без его отзыва- используется при получении нового access token")] = 0
    persist_users: list[AuthSettingsPUser] = []

    # model_config = SettingsConfigDict(env_prefix="MIA__AUTH_", env_file=os.path.join(os.path.dirname(__file__),".auth.env"), env_file_encoding="utf-8", env_nested_delimiter='_')
    #
    # @field_validator("SECRET_KEY", mode="after")
    # @classmethod
    # def validate_auth_secret_key(cls, val: str) -> str:
    #     """Always use the value from the environment if it's available."""
    #     print('input val', val)
    #     if env_val := os.getenv(f"{cls.model_config['env_prefix']}SECRET_KEY"):
    #         print('using env variable file for SECRET_KEY value')
    #         return env_val
    #     return val

    @field_validator("ACCESS_TOKEN_EXPIRE_SECONDS", mode="before")
    def validate_at_minutes(cls, v):
        if isinstance(v, (int, float, str)):
            v = int(v)
        if v < 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_SECONDS must be greater than 0")
        return v
    @field_validator("REFRESH_TOKEN_EXPIRE_SECONDS", mode="before")
    def validate_rt_minutes(cls, v):
        if isinstance(v, (int, float, str)):
            v = int(v)
        if v < 0:
            raise ValueError("REFRESH_TOKEN_EXPIRE_SECONDS must be greater than 0")
        return v

class DatabaseSettings(BaseModel):
    host: StrictStr
    port: StrictInt
    user: StrictStr
    upw: SecretStr
    database: StrictStr
    db_schema: StrictStr

class Settings(BaseSettings):
    app_name: str
    db: DatabaseSettings
    auth: AuthSettings

    # Optional: configure behavior (e.g., prefix env variables)
    model_config = SettingsConfigDict(env_prefix="MIA__", env_file=os.path.join(os.path.dirname(__file__),".env"), env_file_encoding="utf-8", env_nested_delimiter='__')

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """
        Define the loading order and sources (First item wins over subsequent items)

        To target a nested field in .env, join the parent model name and the child field name using a double underscore __.
        Example of overriding db user value: MIA_db__user=osmreader 
        """
        localconf = _conf_pref / Path('config.' + socket.getfqdn() + '.json')
        if localconf.is_file():
            print(f"using local config overrides from {localconf}")
            return (
                init_settings,
                dotenv_settings,
                env_settings,
                JsonConfigSettingsSource(settings_cls, json_file= localconf),
                JsonConfigSettingsSource(settings_cls, json_file=_conf_pref / Path("config.json")),
            )
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            JsonConfigSettingsSource(settings_cls, json_file=Path('.')/Path('config')/Path("config.json")),
        )

settings = Settings()
