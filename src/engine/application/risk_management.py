import logging
from typing import Optional, Literal
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RiskConfig:
    """Конфігурація ризик-менеджменту."""
    taker_fee: float = 0.001          
    min_risk_reward: float = 1.5 
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
    
    def __init__(self, config: RiskConfig):
        # 💉 DI: Конфіг завжди передається ззовні (з main.py)
        self.config = config

    def evaluate_trade(
        self, 
        entry_price: float, 
        atr: float, # ✅ Приймаємо просто число, ніяких pd.Series
        capital: float, 
        trade_type: Literal['BUY', 'SELL'] = 'BUY'
    ) -> Optional[TradeParameters]:
        """Розраховує SL/TP, розмір позиції та валідує угоду."""
        
        if atr <= 0:
            logger.warning("⚠️ Некоректний ATR (<= 0). Відміна розрахунку ризиків.")
            return None

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

        # Максимальний збиток у доларах, який ми готові понести
        max_loss_usdt = capital * (self.config.max_risk_pct / 100) 
        risk_per_coin = abs(entry_price - stop_loss)
        
        if risk_per_coin == 0:
            return None

        position_size_coins = max_loss_usdt / risk_per_coin
        position_size_usdt = position_size_coins * entry_price

        # Перевірка на нестачу маржі
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
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            position_size_usdt=round(position_size_usdt, 2),
            risk_reward_ratio=round(rr_ratio, 2)
        )