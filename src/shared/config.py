from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys
    BINANCE_API_KEY: SecretStr = Field(..., description="Binance Public API Key")
    BINANCE_SECRET_KEY: SecretStr = Field(..., description="Binance Secret Key")
    
    # Telegram
    ENABLE_TELEGRAM: bool = Field(default=False, description="Enable Telegram notifications")
    TELEGRAM_BOT_TOKEN: SecretStr | None = Field(default=None, description="Telegram Bot Token")
    TELEGRAM_CHAT_ID: str | None = Field(default=None, description="Telegram Admin Chat ID")
    
    # Trading logic
    TIMEFRAME: str = Field(default="5m", description="Candle timeframe")
    CONFIDENCE_THRESHOLD: float = Field(default=0.30, ge=0.0, le=1.0, description="AI confidence threshold")
    RISK_REWARD_RATIO: float = Field(default=1.5, gt=1.0, description="Minimum Risk/Reward ratio")
    
    # AI & Prediction (Додано шлях до моделі)
    MODEL_PATH: str = Field(default="data_storage/models/global_rf_v4.pkl", description="Шлях до натренованої AI моделі")
    
    # NEW: обмеження торгівлі
    INITIAL_BALANCE: float = Field(default=1000.0, ge=0, description="Початковий баланс paper trading")
    MAX_CONCURRENT_POSITIONS: int = Field(default=3, ge=1, le=10, description="Максимальна кількість одночасних позицій")
    TRADE_FRACTION: float = Field(default=0.04, gt=0, le=1, description="Розмір позиції у відсотках від балансу (0.04 = 4%)")
    MIN_TRADE_SIZE: float = Field(default=10.0, ge=0, description="Мінімальний розмір угоди в USDT")
    MIN_BALANCE_USDT: float = Field(default=50.0, ge=0, description="Мінімальний баланс для відкриття нової позиції")
    
    # NEW: Базові стопи (Додано, бо PaperTrader вимагає їх при ініціалізації)
    DEFAULT_SL_PCT: float = Field(default=0.02, description="Базовий Stop Loss (0.02 = 2%)")
    DEFAULT_TP_PCT: float = Field(default=0.03, description="Базовий Take Profit (0.03 = 3%)")
    
    # Налаштування трейлінг-стопу (Імена та десяткові значення виправлено)
    TRAILING_STOP_ACTIVATION_PCT: float = Field(default=0.015, ge=0, description="Прибуток у %, після якого активується трейлінг-стоп (0.015 = 1.5%)")
    TRAILING_OFFSET_PCT: float = Field(default=0.008, ge=0, description="Відстань трейлінг-стопу від максимуму (0.008 = 0.8%)")
    
    # Таймаут угоди (Перейменовано на SECONDS)
    TRADE_TIMEOUT_SECONDS: int = Field(default=7200, ge=60, description="Максимальний час утримання позиції (секунди)")
    
    # Фільтри
    RSI_BUY_LIMIT: float = Field(default=75.0, ge=0, le=100, description="Максимальне значення RSI для входу")
    TREND_FILTER: bool = Field(default=True, description="Враховувати тренд (EMA) перед входом")
    
    # Сканер
    SCANNER_TOP_N: int = Field(default=10, ge=1, le=50, description="Кількість найбільш волатильних пар для аналізу")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()