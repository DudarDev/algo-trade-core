from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Keys
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET_KEY: str = ""
    
    # Telegram
    ENABLE_TELEGRAM: bool = False
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    # Trading logic
    TIMEFRAME: str = "5m"
    CONFIDENCE_THRESHOLD: float = 0.30
    MIN_R_R_RATIO: float = 1.5
    RISK_REWARD_RATIO: float = 1.5  # Додаємо це для risk_management.py

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
