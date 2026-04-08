from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    BINANCE_API_KEY: str = Field(default="", description="API ключ")
    BINANCE_SECRET_KEY: str = Field(default="", description="Секретний ключ")
    CONFIDENCE_THRESHOLD: float = Field(default=0.10, ge=0.0, le=1.0, description="Поріг AI")
    RISK_REWARD_RATIO: float = Field(default=2.0, ge=1.0, description="R:R")
    DATABASE_URL: str = Field(default="sqlite:////app/data/bot_data.db", description="DB URL")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
