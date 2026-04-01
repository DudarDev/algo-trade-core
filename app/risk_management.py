import logging
from typing import Optional, Literal
from dataclasses import dataclass
import pandas as pd
from app.config import settings

logger = logging.getLogger(__name__)

@dataclass
class RiskConfig:
    """Конфігурація ризик-менеджменту."""
    taker_fee: float = 0.001          
    min_risk_reward: float = settings.RISK_REWARD_RATIO # Синхронізація з глобальним конфігом
    max_risk_pct: float = 2.0         
    atr_multiplier: float = 1.5       

@dataclass
class TradeParameters:
    """Структура даних розрахованого ордера."""
    trade_type: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_usdt: float
    risk_reward_ratio: float

class RiskManager:
    """Головний клас для оцінки угод та розрахунку ризиків."""
    
    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()

    def evaluate_trade(
        self, 
        df_row: pd.Series, 
        entry_price: float, 
        capital: float, 
        trade_type: Literal['BUY', 'SELL'] = 'BUY'
    ) -> Optional[TradeParameters]:
        """Розраховує SL/TP, розмір позиції та валідує угоду."""
        
        if 'ATR' not in df_row or pd.isna(df_row['ATR']) or df_row['ATR'] <= 0:
            logger.warning("⚠️ Відсутній або некоректний ATR. Відміна розрахунку ризиків.")
            return None

        atr = float(df_row['ATR'])
        stop_loss_dist = atr * self.config.atr_multiplier
        fee_impact = entry_price * (self.config.taker_fee * 2) 
        
        if trade_type == 'BUY':
            stop_loss = entry_price - stop_loss_dist
            min_profit_dist = (stop_loss_dist * self.config.min_risk_reward) + fee_impact
            take_profit = entry_price + min_profit_dist
        elif trade_type == 'SELL':
            stop_loss = entry_price + stop_loss_dist
            min_profit_dist = (stop_loss_dist * self.config.min_risk_reward) + fee_impact
            take_profit = entry_price - min_profit_dist
        else:
            logger.error(f"❌ Невідомий тип угоди: {trade_type}.")
            return None

        max_loss_usdt = capital * (self.config.max_risk_pct / 100) 
        risk_per_coin = abs(entry_price - stop_loss)
        
        if risk_per_coin == 0:
            return None

        position_size_coins = max_loss_usdt / risk_per_coin
        position_size_usdt = position_size_coins * entry_price

        if position_size_usdt > capital:
            logger.debug("Об'єм позиції перевищує капітал. Використовуємо 98% від доступного.")
            position_size_usdt = capital * 0.98

        rr_ratio = abs(take_profit - entry_price) / risk_per_coin

        if rr_ratio < self.config.min_risk_reward:
            logger.info(f"🛑 Відхилено: R:R {rr_ratio:.2f} < {self.config.min_risk_reward}.")
            return None

        return TradeParameters(
            trade_type=trade_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_usdt=position_size_usdt,
            risk_reward_ratio=round(rr_ratio, 2)
        )
