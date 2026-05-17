from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BINANCE_API_KEY: SecretStr = Field(default=SecretStr("dummy"), description="API Key")
    BINANCE_SECRET_KEY: SecretStr = Field(default=SecretStr("dummy"), description="Secret Key")
    ENABLE_TELEGRAM: bool = Field(default=False)
    TELEGRAM_BOT_TOKEN: SecretStr | None = Field(default=None)
    TELEGRAM_CHAT_ID: str | None = Field(default=None)
    TIMEFRAME: str = Field(default="5m")
    CONFIDENCE_THRESHOLD: float = Field(default=0.30, ge=0.0, le=1.0)
    RISK_REWARD_RATIO: float = Field(default=1.5, gt=1.0)
    
    # --- КРИТИЧНІ ПАРАМЕТРИ, ЯКІ ШУКАВ РУШІЙ ---
    MODEL_PATH: str = Field(default="data_storage/models/global_rf_v4.pkl")
    DEFAULT_SL_PCT: float = Field(default=0.02)
    DEFAULT_TP_PCT: float = Field(default=0.03)
    
    INITIAL_BALANCE: float = Field(default=1000.0, ge=0)
    MAX_CONCURRENT_POSITIONS: int = Field(default=3, ge=1, le=10)
    TRADE_FRACTION: float = Field(default=0.04, gt=0, le=1)
    MIN_TRADE_SIZE: float = Field(default=10.0, ge=0)
    MIN_BALANCE_USDT: float = Field(default=50.0, ge=0)
    TRAILING_STOP_ACTIVATION_PCT: float = Field(default=0.015, ge=0)
    TRAILING_OFFSET_PCT: float = Field(default=0.008, ge=0)
    TRADE_TIMEOUT_SECONDS: int = Field(default=7200, ge=60)
    RSI_BUY_LIMIT: float = Field(default=75.0, ge=0, le=100)
    TREND_FILTER: bool = Field(default=True)
    SCANNER_TOP_N: int = Field(default=10, ge=1, le=50)
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
