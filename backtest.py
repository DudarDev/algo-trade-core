import pandas as pd
import numpy as np
import logging
import time
import sys
from pathlib import Path

# Додаємо корінь проєкту для імпортів
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.engine.application.ai_brain import GlobalTradingAI
from src.engine.application.risk_management import RiskManager, RiskConfig
from src.shared.config import Settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Backtester")

class Backtester:
    def __init__(self, symbol: str, data_path: str, starting_balance: float = 1000.0):
        self.symbol = symbol
        self.data_path = data_path
        self.balance = starting_balance
        self.settings = Settings()  # використовує змінні оточення з .env
        self.ai = GlobalTradingAI(settings=self.settings)
        self.risk_manager = RiskManager(RiskConfig(max_risk_pct=2.0, min_risk_reward=1.5))

    def run(self):
        logger.info(f"📊 Запуск бектесту для {self.symbol}...")
        start_time = time.time()

        # 1. Завантаження та підготовка даних
        try:
            df = pd.read_csv(self.data_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        except FileNotFoundError:
            logger.error(f"❌ Файл {self.data_path} не знайдено.")
            return

        df = self.ai.prepare_features(df)
        if df.empty:
            logger.error("Недостатньо даних після генерації фіч.")
            return

        # 2. Векторизоване передбачення
        if self.ai.model is None:
            logger.error("Модель не завантажена, бектест неможливий.")
            return

        features = df[self.ai.feature_cols]
        probabilities = self.ai.model.predict_proba(features)[:, 1]
        df['ai_prob'] = probabilities

        # 3. Симуляція торгів
        in_position = False
        entry_price = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        position_size = 0.0
        trades = []

        for index, row in df.iterrows():
            current_price = row['close']

            if in_position:
                if row['low'] <= stop_loss:
                    loss = position_size * ((stop_loss - entry_price) / entry_price)
                    self.balance += loss
                    trades.append({'type': 'LOSS', 'pnl': loss, 'balance': self.balance})
                    in_position = False
                elif row['high'] >= take_profit:
                    profit = position_size * ((take_profit - entry_price) / entry_price)
                    self.balance += profit
                    trades.append({'type': 'WIN', 'pnl': profit, 'balance': self.balance})
                    in_position = False
                continue

            if row['ai_prob'] >= self.ai.confidence_threshold:
                atr_value = row.get('ATR', 0)
                trade_params = self.risk_manager.evaluate_trade(
                    entry_price=current_price,
                    atr=atr_value,
                    capital=self.balance,
                    trade_type='BUY'
                )
                if trade_params:
                    in_position = True
                    entry_price = trade_params.entry_price
                    stop_loss = trade_params.stop_loss
                    take_profit = trade_params.take_profit
                    position_size = trade_params.position_size_usdt

        # 4. Аналіз результатів
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['type'] == 'WIN')
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        logger.info("\n" + "="*40)
        logger.info(f"📈 РЕЗУЛЬТАТИ БЕКТЕСТУ: {self.symbol}")
        logger.info(f"Час виконання: {time.time() - start_time:.2f} сек")
        logger.info(f"Початковий баланс: $1000.00")
        logger.info(f"Кінцевий баланс:   ${self.balance:.2f}")
        logger.info(f"Чистий прибуток (PnL): ${self.balance - 1000.00:.2f} ({(self.balance - 1000.00)/10:.2f}%)")
        logger.info(f"Всього угод:       {total_trades}")
        logger.info(f"Win Rate:          {win_rate:.2f}%")
        logger.info("="*40 + "\n")

if __name__ == "__main__":
    # Використовуй шляхи до реальних CSV-файлів
    tester_btc = Backtester("BTC/USDT", "data_storage/history/BTC_USDT_5m.csv")
    tester_btc.run()

    tester_sol = Backtester("SOL/USDT", "data_storage/history/SOL_USDT_5m.csv")
    tester_sol.run()
