import time
import logging
from app.exchange_manager import ExchangeManager
from app.market_scanner import MarketScanner
from app.strategy import Strategy
from app.ai_brain import GlobalTradingAI
from app.risk_management import RiskManager, RiskConfig
from app.paper_trader import PaperTrader

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("Main")

class CryptoBot:
    def __init__(self):
        logger.info("🚀 Ініціалізація Quantum Scalper Core...")
        
        # Ініціалізація інфраструктури
        self.exchange = ExchangeManager() 
        self.scanner = MarketScanner()  # ВИПРАВЛЕНО: без аргументів
        
        # Ініціалізація Quant-модулів
        self.strategy = Strategy()
        self.ai = GlobalTradingAI()
        self.risk_manager = RiskManager(RiskConfig(max_risk_pct=2.0, min_risk_reward=1.5))
        
        # Ініціалізація симулятора торгів
        self.trader = PaperTrader(initial_balance=1000.0)

    def run_cycle(self):
        logger.info("📡 Пошук волатильних пар...")
        # ВИПРАВЛЕНО: правильна назва методу
        active_pairs = self.scanner.get_top_volatile_pairs(min_volume=500_000)
        
        if not active_pairs:
            logger.warning("⚠️ Ринок неліквідний. Чекаю...")
            return

        for symbol in active_pairs:
            try:
                # 1. Отримуємо сирі дані
                df = self.exchange.fetch_data(symbol, timeframe='5m', limit=100)
                if df is None or df.empty:
                    continue
                    
                # 2. Перевіряємо відкриті позиції
                if self.trader.has_open_position(symbol):
                    self.trader.update_position(symbol, df.iloc[-1]['close'])
                    continue
                
                # 3. Генерація фіч (потрібна для отримання ATR для Risk Manager)
                df_features = self.ai.prepare_features(df)
                if df_features.empty:
                    continue
                    
                # 4. Прогноз AI (ВИПРАВЛЕНО: передаємо сирий df, як очікує метод)
                signal, confidence = self.ai.predict(df)
                
                # 5. Фільтрація через Risk Management
                if signal == "BUY":
                    current_price = df_features.iloc[-1]['close']
                    trade_params = self.risk_manager.evaluate_trade(
                        df_row=df_features.iloc[-1], # Містить ATR для розрахунку стопів
                        entry_price=current_price, 
                        capital=self.trader.get_balance(),
                        trade_type='BUY'
                    )
                    
                    # 6. Відкриття ордера
                    if trade_params:
                        logger.info(f"🔥 ВХІД: {symbol} | Conf: {confidence:.2f} | R:R: {trade_params.risk_reward_ratio:.2f}")
                        self.trader.open_position(
                            symbol=symbol,
                            side="BUY",
                            amount_usdt=trade_params.position_size_usdt,
                            price=trade_params.entry_price,
                            sl=trade_params.stop_loss,
                            tp=trade_params.take_profit
                        )
            except Exception as e:
                logger.error(f"❌ Помилка обробки {symbol}: {e}", exc_info=True)

    def start(self):
        logger.info("🟢 Бот запущено!")
        while True:
            try:
                self.run_cycle()
                logger.info("💤 Очікування наступного циклу (5хв)...")
                time.sleep(300)
            except KeyboardInterrupt:
                logger.info("🛑 Зупинка бота користувачем.")
                break
            except Exception as e:
                logger.error(f"❌ Критична помилка у головному циклі: {e}", exc_info=True)
                time.sleep(60)

if __name__ == "__main__":
    bot = CryptoBot()
    bot.start()