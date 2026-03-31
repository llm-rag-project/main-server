from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "News Monitoring API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    refresh_token_expire_days: int = 14
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Dify / Workflow
    dify_base_url: str
    dify_api_key: str
    dify_request_timeout: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()