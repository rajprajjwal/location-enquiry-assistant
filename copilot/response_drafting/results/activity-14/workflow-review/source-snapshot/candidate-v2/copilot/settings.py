"""Configuration for the separate document embedding endpoint."""


from pydantic_settings import BaseSettings, SettingsConfigDict

from copilot.paths import PACKAGE_ROOT


class EmbeddingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PACKAGE_ROOT / ".env", PACKAGE_ROOT.parent / ".env"), extra="ignore"
    )

    embed_backend: str = "endpoint"
    embed_base_url: str = ""
    embed_api_key: str = ""
    embed_ca_bundle: str = ""
    embed_model_endpoint: str = "bge-small-en-v1.5"
    embed_model: str = "BAAI/bge-base-en-v1.5"


settings = EmbeddingSettings()
