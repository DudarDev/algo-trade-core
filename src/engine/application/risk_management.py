import logging
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

class RiskConfig(BaseModel):
    taker_fee: float = Field(0.001, ge=0.0)
    min_risk_reward: float = Field(1.5, gt=0.0)
    max_risk_pct: float = Field(2.0, gt=0.0, le=10.0) # Захист від самогубства депозиту
    atr_multiplier: float = Field(2.0, gt=0.0)
    min_stop_loss_pct: float = Field(1.5, gt=0.0)
    max_stop_loss_pct: float = Field(5.0, gt=0.0)
    
    model_config = ConfigDict(strict=True)

class TradeParameters(BaseModel):
    trade_type: Literal['BUY', 'SELL']
    entry_price: float = Field(..., gt=0.0)
    stop_loss: float = Field(..., gt=0.0)
    take_profit: float = Field(..., gt=0.0)
    position_size_usdt: float = Field(..., gt=0.0)
    risk_reward_ratio: float = Field(..., gt=0.0)
    
    model_config = ConfigDict(strict=True)

class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config

    def evaluate_trade(
        self, 
        entry_price: float, 
        atr: float,
        capital: float, 
        trade_type: Literal['BUY', 'SELL'] = 'BUY'
    ) -> Optional[TradeParameters]:
        
        if atr <= 0 or capital <= 0:
            logger.warning("⚠️ Некоректні вхідні дані (ATR або Capital <= 0).")
            return None

        # 1. Розрахунок та обмеження Stop Loss
        stop_loss_dist = atr * self.config.atr_multiplier
        min_dist = entry_price * (self.config.min_stop_loss_pct / 100.0)
        max_dist = entry_price * (self.config.max_stop_loss_pct / 100.0)
        
        # Затискаємо дистанцію стопа в задані межі (Clamp)
        stop_loss_dist = max(min_dist, min(stop_loss_dist, max_dist))
        
        fee_impact = entry_price * (self.config.taker_fee * 2) 

        # 2. Визначення рівнів
        direction = 1 if trade_type == 'BUY' else -1
        stop_loss = entry_price - (stop_loss_dist * direction)
        
        min_profit_dist = (stop_loss_dist * self.config.min_risk_reward) + fee_impact
        take_profit = entry_price + (min_profit_dist * direction)

        # 3. Розрахунок розміру позиції (Position Sizing)
        max_loss_usdt = capital * (self.config.max_risk_pct / 100.0)
        risk_per_coin = abs(entry_price - stop_loss)
        
        if risk_per_coin == 0:
            return None

        position_size_usdt = (max_loss_usdt / risk_per_coin) * entry_price

        # Обмеження на максимальне плече / розмір депозиту
        max_allowed_position = capital * 0.98
        if position_size_usdt > max_allowed_position:
            logger.debug(f"Об'єм {position_size_usdt:.2f} перевищує ліміт. Урізано до {max_allowed_position:.2f}")
            position_size_usdt = max_allowed_position

        # 4. Фінальна перевірка Risk:Reward
        actual_rr_ratio = abs(take_profit - entry_price) / risk_per_coin

        if actual_rr_ratio < self.config.min_risk_reward:
            logger.info(f"🛑 Відхилено: R:R {actual_rr_ratio:.2f} < {self.config.min_risk_reward}")
            return None

        return TradeParameters(
            trade_type=trade_type,
            entry_price=round(entry_price, 4),
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            position_size_usdt=round(position_size_usdt, 2),
            risk_reward_ratio=round(actual_rr_ratio, 2)
        )