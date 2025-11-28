import sys
import io
import time
import threading
import os
import logging
from dotenv import load_dotenv

# --- 🛠 ВИПРАВЛЕННЯ КОДУВАННЯ ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# --- ІМПОРТИ МОДУЛІВ ---
from app.exchange_manager import ExchangeManager
from app.strategy import Strategy
# 👇 ЗМІНА: Використовуємо PaperTrader (Симулятор) для тестів без грошей
from app.paper_trader import PaperTrader 
from app.telegram_bot import run_bot 

# --- НАЛАШТУВАННЯ ЛОГУВАННЯ ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("CryptoBot")

class CryptoTradingBot:
    def __init__(self):
        """Ініціалізація SIMULATION бота"""
        logger.info("🎮 Ініціалізація Crypto Algo Pro (PAPER TRADING MODE)...")
        load_dotenv()
        
        # Конфігурація
        self.symbol = 'BTC/USDT' # Для симулятора краще BTC або ETH
        self.timeframe = '1m'
        self.is_running = True

        # Ініціалізація компонентів
        try:
            # Kraken дозволяє читати публічні дані (ціни) БЕЗ ключів
            self.exchange = ExchangeManager(exchange_id='kraken') 
            self.strategy = Strategy()
            
            # 👇 ЗМІНА: Підключаємо Симулятор з віртуальними $1000
            self.trader = PaperTrader(initial_balance=1000.0)
            
            logger.info("✅ Модулі симуляції завантажено. Віртуальний баланс: $1000")
        except Exception as e:
            logger.error(f"❌ Критична помилка запуску: {e}")
            sys.exit(1)

    def start_telegram_service(self):
        """Запускає Telegram"""
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        logger.info("✅ Служба Telegram активна.")

    def analyze_market(self):
        """Цикл аналізу"""
        try:
            df = self.exchange.fetch_candles(self.symbol, self.timeframe, limit=100)
            
            if df.empty:
                logger.warning("⚠️ Пусті дані. Перевірка з'єднання...")
                return

            df = self.strategy.calculate_indicators(df)
            
            # Отримуємо сигнал
            signal = self.strategy.get_signal(
                df, 
                in_position=self.trader.in_position, 
                entry_price=self.trader.entry_price
            )
            
            current_price = df.iloc[-1]['close']
            current_time = df.iloc[-1]['timestamp']
            rsi = df.iloc[-1]['rsi']

            # Логіка торгівлі (Симуляція)
            if signal == "BUY":
                logger.info(f"💵 СИГНАЛ BUY! Ціна: {current_price}")
                self.trader.buy(self.symbol, current_price, current_time)
            
            elif signal == "SELL":
                logger.info(f"💴 СИГНАЛ SELL! Ціна: {current_price}")
                self.trader.sell(self.symbol, current_price, current_time)

            print(f"🎲 {self.symbol} | ${current_price:.2f} | RSI: {rsi:.1f} | SIMULATION")

        except Exception as e:
            logger.error(f"⚠️ Помилка циклу: {e}")

    def run(self):
        self.start_telegram_service()
        logger.info(f"🔥 Починаю віртуальну торгівлю: {self.symbol}")

        while self.is_running:
            try:
                self.analyze_market()
                time.sleep(10) # 10 секунд пауза
            except KeyboardInterrupt:
                logger.info("🛑 Зупинка бота.")
                self.is_running = False
            except Exception as e:
                logger.critical(f"💥 Збій: {e}")
                time.sleep(5)

if __name__ == "__main__":
    bot_app = CryptoTradingBot()
    bot_app.run()