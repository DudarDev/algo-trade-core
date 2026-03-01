import logging
import time
import os
import requests
from typing import Dict, Any, Optional, List
from app.database import DatabaseManager
from app.config import Config
from dotenv import load_dotenv

logger = logging.getLogger("PaperTrader")

# ==========================================
# 1. КЛАС ТЕЛЕГРАМ-СПОВІЩЕНЬ
# ==========================================
class TelegramNotifier:
    def __init__(self):
        load_dotenv()
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.token and self.chat_id)
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, message):
        """Відправляє просто текст у Telegram"""
        if not self.enabled:
            return
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            requests.post(url, data=payload, timeout=5)
        except Exception as e:
            logger.error(f"⚠️ Помилка Telegram: {e}")

# ==========================================
# 2. ГОЛОВНИЙ КЛАС ТОРГІВЛІ
# ==========================================
class PaperTrader:
    def __init__(self, initial_balance: float = 1000.0, fee_rate: float = 0.001):
        self.db = DatabaseManager()
        self.fee_rate = fee_rate
        self.notifier = TelegramNotifier()
        
        # Завантаження стану
        self.usdt_balance = self.db.load_balance(initial_balance)
        self.positions: Dict[str, Any] = self.db.load_open_positions()
        
        self.cooldowns: Dict[str, float] = {}
        self.cooldown_duration = 3 * 3600  # 3 години
        
        logger.info(f"💾 Баланс завантажено: {self.usdt_balance:.2f} USDT")
        if self.notifier.enabled:
            self.notifier.send(f"🤖 <b>Бот Успішно Запущений!</b>\n💰 Поточний баланс: <code>{self.usdt_balance:.2f} USDT</code>")

    # 🔥 ОНОВЛЕНО: Додано параметр ai_conf
    def buy(self, symbol: str, price: float, atr: float, reason: str = "", ai_conf: float = 0.5):
        """Відкриття позиції з динамічним лотом, ATR-захистом та збереженням AI впевненості."""
        if symbol in self.positions:
            return

        if symbol in self.cooldowns:
            if time.time() - self.cooldowns[symbol] < self.cooldown_duration:
                return
            else:
                del self.cooldowns[symbol]

        suggested_amount = self.usdt_balance * Config.POSITION_SIZE_FRACTION
        trade_amount = max(Config.USDT_PER_TRADE, min(suggested_amount, self.usdt_balance))
        
        if trade_amount < 10.0:
            logger.warning(f"⚠️ Недостатньо балансу для {symbol} ({self.usdt_balance:.2f})")
            return

        fee_cost = trade_amount * self.fee_rate
        coin_amount = (trade_amount - fee_cost) / price

        sl_level = price - (atr * Config.STOP_LOSS_ATR_MULT)
        tp_level = price + (atr * Config.TAKE_PROFIT_ATR_MULT)

        pos_data = {
            "amount": coin_amount,
            "entry_price": price,
            "highest_price": price,
            "cost": trade_amount,
            "stop_loss": sl_level,
            "take_profit": tp_level,
            "atr_at_entry": atr,
            "trailing_active": False,
            "current_conf": ai_conf  # 🔥 НОВЕ: Зберігаємо початкову впевненість
        }

        self.usdt_balance -= trade_amount
        self.positions[symbol] = pos_data

        try:
            self.db.save_balance(self.usdt_balance)
            self.db.save_position(symbol, pos_data)
            self.db.log_trade(symbol, "BUY", price, coin_amount, trade_amount)
            
            logger.info(f"🟢 [BUY {symbol}] Entry: {price} | SL: {sl_level:.2f} | TP: {tp_level:.2f}")
            
            msg = (
                f"🟢 <b>BUY {symbol}</b>\n"
                f"💵 Ціна: <code>{price:.4f}</code>\n"
                f"🎯 TP: <code>{tp_level:.4f}</code>\n"
                f"🛑 SL: <code>{sl_level:.4f}</code>\n"
                f"🧠 Логіка: <i>{reason}</i>"
            )
            self.notifier.send(msg)
            
        except Exception as e:
            logger.error(f"❌ DB Error (Buy): {e}")

    # 🔥 НОВЕ: Метод для оновлення впевненості моделі для відкритої позиції
    def update_position_confidence(self, symbol: str, new_conf: float):
        if symbol in self.positions:
            self.positions[symbol]["current_conf"] = new_conf

    # 🔥 ОНОВЛЕНО: Прибрано параметр brain, тепер перевіряємо збережене значення
    def check_auto_exits(self, symbol: str, current_price: float):
        """Перевірка SL/TP, Trailing Stop та Розумний вихід через ШІ."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        
        if current_price > pos["highest_price"]:
            pos["highest_price"] = current_price

        # --- Trailing Stop Logic ---
        activation_threshold = pos["entry_price"] * 1.007
        
        if not pos.get("trailing_active", False):
            if current_price >= activation_threshold:
                pos["trailing_active"] = True
                breakeven_sl = pos["entry_price"] * 1.003
                
                if breakeven_sl > pos["stop_loss"]:
                    pos["stop_loss"] = breakeven_sl
                    logger.info(f"⚓ {symbol}: Trailing Stop ACTIVATED. Stop moved to Breakeven ({breakeven_sl:.4f})")
                    self.notifier.send(f"🛡 <b>{symbol}</b>: Трейлінг-стоп активовано!")

        if pos.get("trailing_active", False):
            new_sl = current_price * 0.995 
            if new_sl > pos["stop_loss"]:
                pos["stop_loss"] = new_sl

        # --- 🔥 ОНОВЛЕНО: AI-SMART EXIT LOGIC ---
        # Читаємо впевненість, яку оновив main.py. Якщо вона впала нижче 0.35, а ми в профіті — виходимо.
        if current_price > pos["entry_price"]:
            current_conf = pos.get("current_conf", 0.5)
            if current_conf < 0.35:
                logger.info(f"🧠 AI-Exit: Низька впевненість ({current_conf:.2f}). Закриваємо {symbol} превентивно.")
                self.sell(symbol, current_price, reason="AI_SMART_EXIT 🧠")
                return

        # --- Standard Exits ---
        if current_price <= pos["stop_loss"]:
            reason = "TRAILING_STOP 📉" if pos.get("trailing_active") else "STOP_LOSS 🛑"
            self.sell(symbol, current_price, reason=reason)
        
        elif current_price >= pos["take_profit"]:
            self.sell(symbol, current_price, reason="TAKE_PROFIT 🎯")

    def sell(self, symbol: str, price: float, reason: str = "Signal"):
        """Закриття позиції та очистка стану."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        slippage = 0.9995 if "TAKE_PROFIT" not in reason else 1.0
        execution_price = price * slippage
        
        net_revenue = (pos["amount"] * execution_price) * (1 - self.fee_rate)
        profit_usdt = net_revenue - pos["cost"]
        profit_pct = (profit_usdt / pos["cost"]) * 100

        self.usdt_balance += net_revenue
        
        if "STOP_LOSS" in reason:
            self.cooldowns[symbol] = time.time()
            logger.warning(f"⏳ {symbol} відправлено в карантин.")
        
        try:
            self.db.save_balance(self.usdt_balance)
            self.db.delete_position(symbol)
            self.db.log_trade(symbol, "SELL", execution_price, pos["amount"], net_revenue, profit_pct)
            
            del self.positions[symbol]
            
            color = "🤑" if profit_usdt > 0 else "🔻"
            logger.info(f"🔴 [SELL {symbol}] {reason} | PnL: {profit_pct:.2f}% | Bal: {self.usdt_balance:.2f}")
            
            msg = (
                f"{color} <b>SELL {symbol}</b>\n"
                f"Причина: <b>{reason}</b>\n"
                f"PnL: <b>{profit_pct:.2f}%</b> (<code>{profit_usdt:.2f} USDT</code>)\n"
                f"💼 Баланс: <code>{self.usdt_balance:.2f} USDT</code>"
            )
            self.notifier.send(msg)
            
        except Exception as e:
            logger.error(f"❌ DB Error (Sell): {e}")