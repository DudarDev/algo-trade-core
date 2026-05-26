from pydantic import Field
from pydantic_settings import BaseSettings

class TradingSettings(BaseSettings):
    # Змінили ліміти, щоб дозволити стратегії самій керувати порогами
    min_ai_confidence: float = Field(0.65, ge=0.0, le=1.0, description="Minimum AI confidence")
    CONFIDENCE_THRESHOLD: float = Field(0.65, ge=0.0, le=1.0, description="Minimum AI confidence")
    min_adx_trend: float = Field(25.0, ge=0.0, description="Minimum ADX value to confirm a trend") # Підняли до 25!
    partial_tp_ratio: float = Field(1.0, description="Risk multiplier for the first Take Profit (e.g., 1R)")
    partial_tp_size: float = Field(0.5, ge=0.1, le=1.0, description="Fraction of position to close at first TP")
    max_consecutive_losses: int = Field(3, ge=1, description="Number of losses before banning a pair")
    
    class Config:
        env_prefix = "TRADING_"

settings = TradingSettings()