from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")

    allowed_user_ids: list[int] = Field(default_factory=list, alias="ALLOWED_USER_IDS")
    admin_user_ids: list[int] = Field(default_factory=list, alias="ADMIN_USER_IDS")

    daily_query_limit: int = Field(default=20, alias="DAILY_QUERY_LIMIT")
    max_question_length: int = Field(default=2000, alias="MAX_QUESTION_LENGTH")

    knowledge_dir: Path = Field(default=Path("./knowledge"), alias="KNOWLEDGE_DIR")
    chroma_persist_dir: Path = Field(default=Path("./data/chroma"), alias="CHROMA_PERSIST_DIR")
    sqlite_path: Path = Field(default=Path("./data/bot.db"), alias="SQLITE_PATH")

    llm_model: str = Field(default="openai/gpt-4o-mini", alias="LLM_MODEL")
    embedding_model: str = Field(default="openai/text-embedding-3-small", alias="EMBEDDING_MODEL")
    top_k_chunks: int = Field(default=5, alias="TOP_K_CHUNKS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="text", alias="LOG_FORMAT")

    analytics_store_questions: bool = Field(default=True, alias="ANALYTICS_STORE_QUESTIONS")
    analytics_question_retention_days: int = Field(
        default=90, alias="ANALYTICS_QUESTION_RETENTION_DAYS"
    )
    analytics_report_chat_id: int | None = Field(
        default=None, alias="ANALYTICS_REPORT_CHAT_ID"
    )
    admin_notify_chat_id: int | None = Field(default=None, alias="ADMIN_NOTIFY_CHAT_ID")
    analytics_schedule_enabled: bool = Field(
        default=True, alias="ANALYTICS_SCHEDULE_ENABLED"
    )
    analytics_daily_cron: str = Field(default="0 18 * * *", alias="ANALYTICS_DAILY_CRON")
    analytics_weekly_cron: str = Field(default="0 9 * * 1", alias="ANALYTICS_WEEKLY_CRON")
    analytics_report_max_llm_tokens: int = Field(
        default=4096, alias="ANALYTICS_REPORT_MAX_LLM_TOKENS"
    )
    analytics_summary_model: str | None = Field(default=None, alias="ANALYTICS_SUMMARY_MODEL")
    analytics_off_topic_similarity_threshold: float = Field(
        default=0.35, alias="ANALYTICS_OFF_TOPIC_SIMILARITY_THRESHOLD"
    )
    anomaly_no_answer_ratio: float = Field(default=0.5, alias="ANOMALY_NO_ANSWER_RATIO")
    anomaly_no_answer_count: int = Field(default=5, alias="ANOMALY_NO_ANSWER_COUNT")
    anomaly_limit_usage_ratio: float = Field(default=0.9, alias="ANOMALY_LIMIT_USAGE_RATIO")
    anomaly_token_user_daily: int = Field(default=10000, alias="ANOMALY_TOKEN_USER_DAILY")
    analytics_dashboard_enabled: bool = Field(
        default=False, alias="ANALYTICS_DASHBOARD_ENABLED"
    )
    analytics_dashboard_token: str | None = Field(
        default=None, alias="ANALYTICS_DASHBOARD_TOKEN"
    )
    analytics_dashboard_port: int = Field(default=8080, alias="ANALYTICS_DASHBOARD_PORT")

    chunk_size: int = 512
    chunk_overlap: int = 64

    @field_validator(
        "allowed_user_ids",
        "admin_user_ids",
        mode="before",
    )
    @classmethod
    def parse_id_list(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        if isinstance(value, int):
            return [value]
        return [int(part.strip()) for part in str(value).split(",") if part.strip()]

    @field_validator(
        "analytics_report_chat_id",
        "admin_notify_chat_id",
        mode="before",
    )
    @classmethod
    def parse_optional_int(cls, value: object) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    def is_allowed(self, user_id: int) -> bool:
        return user_id in self.allowed_user_ids

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_user_ids

    @property
    def effective_summary_model(self) -> str:
        return self.analytics_summary_model or self.llm_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
