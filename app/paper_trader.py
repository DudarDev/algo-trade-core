import logging
from typing import Dict, Any, Optional, List
from app.database import DatabaseManager
from app.config import Config

logger = logging.getLogger("PaperTrader")

class PaperTrader:
    def __init__(self, initial_balance: float = 1000.0, fee_rate: float = 0.001):
        self.db = DatabaseManager()
        self.fee_rate = fee_rate
        
        # Завантаження стану
        self.usdt_balance = self.db.load_balance(initial_balance)
        self.positions: Dict[str, Any] = self.db.load_open_positions()
        
        logger.info(f"💾 Баланс завантажено: {self.usdt_balance:.2f} USDT")

    def buy(self, symbol: str, price: float, atr: float):
        """Відкриття позиції з динамічним лотом та ATR-захистом."""
        if symbol in self.positions:
            return

        # Динамічний розмір позиції (напр. 95% від балансу / к-ть слотів), але не менше Config
        suggested_amount = self.usdt_balance * Config.POSITION_SIZE_FRACTION
        trade_amount = max(Config.USDT_PER_TRADE, min(suggested_amount, self.usdt_balance))
        
        if trade_amount < 10.0: # Мінімальний лот для бірж
            logger.warning(f"⚠️ Недостатньо балансу для {symbol} (Available: {self.usdt_balance:.2f})")
            return

        fee_cost = trade_amount * self.fee_rate
        coin_amount = (trade_amount - fee_cost) / price

        # Розрахунок рівнів виходу
        # SL = Ціна - (ATR * Множник)
        sl_level = price - (atr * Config.STOP_LOSS_ATR_MULT)
        # TP = Ціна + (ATR * Множник)
        tp_level = price + (atr * Config.TAKE_PROFIT_ATR_MULT)

        pos_data = {
            "amount": coin_amount,
            "entry_price": price,
            "highest_price": price,
            "cost": trade_amount,
            "stop_loss": sl_level,
            "take_profit": tp_level,
            "atr_at_entry": atr,
            "trailing_active": False
        }

        self.usdt_balance -= trade_amount
        self.positions[symbol] = pos_data

        try:
            self.db.save_balance(self.usdt_balance)
            self.db.save_position(symbol, pos_data)
            self.db.log_trade(symbol, "BUY", price, coin_amount, trade_amount)
            logger.info(f"🟢 [BUY {symbol}] Entry: {price} | SL: {sl_level:.2f} | TP: {tp_level:.2f}")
        except Exception as e:
            logger.error(f"❌ DB Error (Buy): {e}")

    def check_auto_exits(self, symbol: str, current_price: float):
        """Перевірка SL/TP та ОНОВЛЕНА логіка Trailing Stop."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        
        # 1. Оновлення максимуму (High Watermark)
        if current_price > pos["highest_price"]:
            pos["highest_price"] = current_price

        # -----------------------------------------------------------
        # 🔥 ВИПРАВЛЕНА ЛОГІКА TRAILING STOP 🔥
        # -----------------------------------------------------------
        # Активуємо ТІЛЬКИ якщо чистий прибуток > 0.7% (щоб покрити комісії і дати запас)
        # Раніше було 50% від шляху до TP, що на флеті давало мінуси.
        activation_threshold = pos["entry_price"] * 1.007
        
        if not pos.get("trailing_active", False):
            if current_price >= activation_threshold:
                pos["trailing_active"] = True
                logger.info(f"⚓ {symbol}: Trailing Stop ACTIVATED (Profit > 0.7%)")

        # Якщо трейлінг активний - підтягуємо SL
        if pos.get("trailing_active", False):
            # Новий стоп = Поточна ціна - (ATR * 1.5)
            # Ми використовуємо ATR, щоб стоп був "дихаючим" і не вибивався шумом
            new_sl = current_price - (pos["atr_at_entry"] * Config.STOP_LOSS_ATR_MULT)
            
            # Стоп може рухатися ТІЛЬКИ вгору
            if new_sl > pos["stop_loss"]:
                pos["stop_loss"] = new_sl
                # logger.debug(f"⚓ {symbol}: SL moved up to {new_sl:.2f}")

        # -----------------------------------------------------------
        # 2. Перевірка виходу (Sell Condition)
        # -----------------------------------------------------------
        
        # Або ціна впала нижче стопу
        if current_price <= pos["stop_loss"]:
            reason = "TRAILING_STOP 📉" if pos.get("trailing_active") else "STOP_LOSS 🛑"
            self.sell(symbol, current_price, reason=reason)
        
        # Або ціна досягла Take Profit
        elif current_price >= pos["take_profit"]:
            self.sell(symbol, current_price, reason="TAKE_PROFIT 🎯")

    def sell(self, symbol: str, price: float, reason: str = "Signal"):
        """Закриття позиції та очистка стану."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        
        # Імітація прослизання (Slippage) 0.05% для реалістичності тестів
        slippage = 0.9995 if reason != "Signal" else 1.0
        execution_price = price * slippage
        
        # Розрахунок чистого доходу (з вирахуванням комісії 0.1% * 2 = 0.2% приблизно)
        # revenue = (amount * price) * (1 - fee)
        net_revenue = (pos["amount"] * execution_price) * (1 - self.fee_rate)
        
        profit_usdt = net_revenue - pos["cost"]
        profit_pct = (profit_usdt / pos["cost"]) * 100

        self.usdt_balance += net_revenue
        
        try:
            self.db.save_balance(self.usdt_balance)
            self.db.delete_position(symbol)
            
            # Логуємо як закриту угоду
            self.db.log_trade(symbol, "SELL", execution_price, pos["amount"], net_revenue, profit_pct)
            
            del self.positions[symbol]
            
            color = "🤑" if profit_usdt > 0 else "🔻"
            logger.info(f"🔴 [SELL {symbol}] {reason} | PnL: {profit_pct:.2f}% | Bal: {self.usdt_balance:.2f} {color}")
            
        except Exception as e:
            logger.error(f"❌ DB Error (Sell): {e}")