from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # app
    app_name: str = "Main Server"
    debug: bool = True

    # db / auth
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # dify
    dify_base_url: str
    dify_api_key: str
    dify_request_timeout: int = 30

    # transnews
    transnews_base_url: str = "http://localhost:8000"
    transnews_request_timeout: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()