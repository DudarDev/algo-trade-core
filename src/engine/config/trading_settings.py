from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class TradingSettings(BaseSettings):
    # Використовуємо сучасний підхід Pydantic V2
    model_config = SettingsConfigDict(env_prefix="TRADING_", case_sensitive=False)

    # --- AI & SIGNAL FILTERS ---
    min_ai_confidence: float = Field(0.65, ge=0.5, le=1.0, description="Minimum AI probability to enter a trade")
    min_adx_trend: float = Field(25.0, ge=0.0, description="Minimum ADX value (25+ means strong trend)")

    # --- POSITION SIZING & CAPITAL MANAGEMENT (КРИТИЧНО) ---
    risk_per_trade_pct: float = Field(0.02, ge=0.01, le=0.10, description="Risk exactly 2% of total capital per trade")
    max_open_positions: int = Field(3, ge=1, le=10, description="Max concurrent trades to avoid overexposure")

    # --- DYNAMIC RISK MANAGEMENT (ATR) ---
    atr_sl_multiplier: float = Field(1.5, ge=1.0, description="Multiplier for Stop-Loss (1.5x ATR allows breathing room)")
    atr_tp_multiplier: float = Field(3.0, ge=1.0, description="Multiplier for Take-Profit (Creates a 1:2 Risk/Reward ratio)")

    # --- SCALING OUT ---
    partial_tp_ratio: float = Field(1.0, description="Risk multiplier for the first Take Profit (e.g., 1R)")
    partial_tp_size: float = Field(0.5, ge=0.1, le=1.0, description="Fraction of position to close at first TP")
    max_consecutive_losses: int = Field(3, ge=1, description="Number of losses before pausing a pair")

    # --- REALITY CHECK (БЕЗ ЦЬОГО БЕКТЕСТ БРЕШЕ) ---
    exchange_fee_pct: float = Field(0.001, ge=0.0, description="Standard Binance spot fee (0.1%)")
    slippage_pct: float = Field(0.0005, ge=0.0, description="Estimated execution slippage (0.05%)")

settings = TradingSettings()