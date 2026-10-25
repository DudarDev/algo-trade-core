from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    TRADING_MODE: str = Field(default="PAPER", description="Execution mode: PAPER or LIVE")
    BINANCE_API_KEY: SecretStr = Field(default=SecretStr("dummy"), description="API Key")
    BINANCE_SECRET_KEY: SecretStr = Field(default=SecretStr("dummy"), description="Secret Key")
    MAX_SLIPPAGE_PCT: float = Field(default=0.005, ge=0.0, description="Max allowed execution slippage (0.5%)")
    MIN_NOTIONAL_USDT: float = Field(default=10.0, ge=0.0, description="Min notional trade size on Binance")
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
    max_open_positions: int = Field(default=3, ge=1, le=10)
    TRADE_FRACTION: float = Field(default=0.04, gt=0, le=1)
    risk_per_trade_pct: float = Field(default=0.02, gt=0, le=0.10)
    exchange_fee_pct: float = Field(default=0.001, ge=0.0)
    slippage_pct: float = Field(default=0.0005, ge=0.0)
    MIN_TRADE_SIZE: float = Field(default=10.0, ge=0)
    MIN_BALANCE_USDT: float = Field(default=50.0, ge=0)
    TRAILING_STOP_ACTIVATION_PCT: float = Field(default=0.015, ge=0)
    TRAILING_OFFSET_PCT: float = Field(default=0.008, ge=0)
    BREAK_EVEN_TRIGGER_PCT: float = Field(default=0.007, ge=0)
    MAX_TRADE_LOSS_USDT: float = Field(default=3.50, ge=0.5, description="Max dollar loss allowed per trade")
    MIN_24H_VOLUME: float = Field(default=5_000_000.0, ge=0.0, description="Min 24h quote volume in USDT")
    MAX_SPREAD_PCT: float = Field(default=0.002, ge=0.0, description="Max allowed bid/ask spread (0.20%)")
    PARTIAL_TP_PCT: float = Field(default=0.015, ge=0)
    PARTIAL_TP_RATIO: float = Field(default=0.50, gt=0.0, le=1.0)
    DAILY_LOSS_LIMIT_PCT: float = Field(default=0.030, gt=0.0, le=0.20)
    TRADE_TIMEOUT_SECONDS: int = Field(default=7200, ge=60)
    RSI_BUY_LIMIT: float = Field(default=75.0, ge=0, le=100)
    TREND_FILTER: bool = Field(default=True)
    min_adx_trend: float = Field(default=25.0, ge=0.0)
    MIN_ATR_PCT: float = Field(default=0.0010, ge=0.0)
    min_atr_pct: float = Field(default=0.0010, ge=0.0)
    min_ai_confidence: float = Field(default=0.65, ge=0.0, le=1.0)
    ARBITRAGE_FEE_PCT: float = Field(default=0.001, ge=0.0)
    ARBITRAGE_MIN_SPREAD_PCT: float = Field(default=0.5, ge=0.0)
    SCANNER_TOP_N: int = Field(default=10, ge=1, le=50)

    # Redis & Celery Institutional Infrastructure
    REDIS_URL: str = Field(default="redis://127.0.0.1:6379/0", description="Redis connection URL")
    CELERY_BROKER_URL: str = Field(default="redis://127.0.0.1:6379/0", description="Celery broker URL")
    LIGHTGBM_MODEL_PATH: str = Field(default="data_storage/models/global_lgbm_v1.pkl", description="LightGBM model artifact path")
    ENABLE_QUANT_DUAL_ENSEMBLE: bool = Field(default=True, description="Enable RF + LightGBM dual ensemble")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
