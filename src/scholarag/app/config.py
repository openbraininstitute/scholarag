"""Configuration."""

import os
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from scholarag.generative_question_answering import MESSAGES


class SettingsKeycloak(BaseModel):
    """Class retrieving keycloak info for authorization."""

    issuer: str = "https://openbluebrain.com/auth/realms/SBO"
    validate_token: bool = False
    # Useful only for service account (dev)
    client_id: str | None = None
    username: str | None = None
    password: SecretStr | None = None

    model_config = ConfigDict(frozen=True)

    @property
    def token_endpoint(self) -> str | None:
        """Define the token endpoint."""
        if self.validate_token:
            return f"{self.issuer}/protocol/openid-connect/token"
        else:
            return None

    @property
    def user_info_endpoint(self) -> str | None:
        """Define the user_info endpoint."""
        if self.validate_token:
            return f"{self.issuer}/protocol/openid-connect/userinfo"
        else:
            return None

    @property
    def server_url(self) -> str:
        """Server url."""
        return self.issuer.split("/auth")[0] + "/auth/"

    @property
    def realm(self) -> str:
        """Realm."""
        return self.issuer.rpartition("/realms/")[-1]


class SettingsDB(BaseModel):
    """Database settings."""

    db_type: Literal["opensearch", "elasticsearch"]
    index_paragraphs: str
    host: str
    port: int
    index_journals: str | None = None
    user: str | None = None
    password: SecretStr | None = None

    model_config = ConfigDict(frozen=True)


class SettingsRetrieval(BaseModel):
    """Retrieval settings."""

    max_length: int = 100000

    model_config = ConfigDict(frozen=True)


class SettingsCohereReranking(BaseModel):
    """Settings cohere reranker."""

    cohere_token: SecretStr | None = None

    model_config = ConfigDict(frozen=True)


class SettingsOpenAI(BaseModel):
    """OpenAI settings."""

    token: SecretStr | None = None
    model: str = "gpt-4o-mini"
    temperature: float = 0
    max_tokens: int | None = None

    model_config = ConfigDict(frozen=True)


class SettingsGenerative(BaseModel):
    """Generative QA settings."""

    openai: SettingsOpenAI = SettingsOpenAI()
    system_prompt: SecretStr = SecretStr(MESSAGES[0]["content"])

    model_config = ConfigDict(frozen=True)


class SettingsRedisCaching(BaseModel):
    """Redis settings."""

    host: str | None = None
    port: int | None = None
    expiry: float = 30.0  # Time in days

    model_config = ConfigDict(frozen=True)


class SettingsMetadata(BaseModel):
    """Metadata settings."""

    external_apis: bool = True
    timeout: int = 30

    model_config = ConfigDict(frozen=True)


class SettingsLogging(BaseModel):
    """Metadata settings."""

    level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    external_packages: Literal["debug", "info", "warning", "error", "critical"] = (
        "warning"
    )

    model_config = ConfigDict(frozen=True)


class SettingsMisc(BaseModel):
    """Other settings."""

    application_prefix: str = ""
    # list is not hashable, the cors_origins have to be provided as a string with
    # comma separated entries, i.e. "value_1, value_2, ..."
    cors_origins: str = ""

    model_config = ConfigDict(frozen=True)


class Settings(BaseSettings):
    """All settings."""

    db: SettingsDB
    retrieval: SettingsRetrieval = SettingsRetrieval()  # has no required
    reranking: SettingsCohereReranking = SettingsCohereReranking()  # has no required
    generative: SettingsGenerative = SettingsGenerative()  # has no required
    redis: SettingsRedisCaching = SettingsRedisCaching()  # has no required
    metadata: SettingsMetadata = SettingsMetadata()  # has no required
    logging: SettingsLogging = SettingsLogging()  # has no required
    keycloak: SettingsKeycloak = SettingsKeycloak()  # has no required
    misc: SettingsMisc = SettingsMisc()  # has no required

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SCHOLARAG__",
        env_nested_delimiter="__",
        frozen=True,
    )


# Load the remaining variables into the environment
# Necessary for things like SSL_CERT_FILE
config = dotenv_values()
for k, v in config.items():
    if k.lower().startswith("scholarag_"):
        continue
    if v is None:
        continue
    os.environ[k] = os.environ.get(k, v)  # environment has precedence
