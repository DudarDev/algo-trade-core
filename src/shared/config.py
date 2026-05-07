from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys: Використовуємо SecretStr, щоб уникнути випадкового логування ключів
    # Немає дефолтних значень -> Pydantic впаде при старті, якщо їх немає в .env
    BINANCE_API_KEY: SecretStr = Field(..., description="Binance Public API Key")
    BINANCE_SECRET_KEY: SecretStr = Field(..., description="Binance Secret Key")
    
    # Telegram
    ENABLE_TELEGRAM: bool = Field(default=False, description="Enable Telegram notifications")
    # Робимо їх опціональними, оскільки вони потрібні тільки якщо ENABLE_TELEGRAM = True
    TELEGRAM_BOT_TOKEN: SecretStr | None = Field(default=None, description="Telegram Bot Token")
    TELEGRAM_CHAT_ID: str | None = Field(default=None, description="Telegram Admin Chat ID")
    
    # Trading logic: Додаємо жорстку математичну валідацію
    TIMEFRAME: str = Field(default="5m", description="Candle timeframe (e.g., 1m, 5m, 1h)")
    CONFIDENCE_THRESHOLD: float = Field(
        default=0.30, 
        ge=0.0, le=1.0, # ge = greater/equal, le = less/equal
        description="AI confidence threshold (0.0 to 1.0)"
    )
    RISK_REWARD_RATIO: float = Field(
        default=1.5, 
        gt=1.0, # gt = greater than. R:R завжди має бути більше 1
        description="Minimum Risk/Reward ratio"
    )

    # Сучасний Pydantic V2 підхід до конфігурації
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Створюємо єдиний інстанс (Singleton), який будемо імпортувати в інші модулі
settings = Settings()