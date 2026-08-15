from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    app_name: str = "News Monitoring API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    database_pool_size: int = Field(default=15, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=15, alias="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=10, alias="DATABASE_POOL_TIMEOUT")
    database_pool_recycle: int = Field(default=1800, alias="DATABASE_POOL_RECYCLE")

    refresh_token_expire_days: int = 14
    database_url: str = Field(..., alias="DATABASE_URL")
    secret_key: str = Field(..., alias="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Chatflow
    dify_base_url: str = Field(..., alias="DIFY_BASE_URL")
    chatflow_api_key: str = Field(..., alias="CHATFLOW_API_KEY")

    # Workflow
    summary_workflow_api_key: str = Field(..., alias="SUMMARY_WORKFLOW_API_KEY")
    scoring_workflow_api_key: str = Field(..., alias="SCORING_WORKFLOW_API_KEY")
    analysis_workflow_api_key: str = Field(..., alias="ANALYSIS_WORKFLOW_API_KEY")
    news_editor_workflow_api_key: str = Field(default="", alias="NEWS_EDITOR_WORKFLOW_API_KEY")
    priority_insight_workflow_api_key: str = Field(default="", alias="PRIORITY_INSIGHT_WORKFLOW_API_KEY")

    # Knowledge
    knowledge_api_key: str = Field(..., alias="KNOWLEDGE_API_KEY")
    dify_dataset_id: str = Field(..., alias="DIFY_DATASET_ID")
    dify_article_id_metadata_field_id: str = Field(..., alias="DIFY_ARTICLE_ID_METADATA_FIELD_ID")

    dify_request_timeout: int = 180
    transnews_base_url: str = Field(..., alias="TRANSNEWS_BASE_URL")
    transnews_request_timeout: int = 60

    crawl_scheduler_interval_minutes: int = Field(default=30, alias="CRAWL_SCHEDULER_INTERVAL_MINUTES")

    # SMTP 이메일
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
