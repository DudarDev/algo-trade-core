import pandas as pd
import numpy as np
import logging
import time
from app.ai_brain import GlobalTradingAI
from app.risk_management import RiskManager, RiskConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Backtester")

class Backtester:
    """Швидкий бектестер для оцінки ефективності AI-моделі та Risk Manager."""
    
    def __init__(self, symbol: str, data_path: str, starting_balance: float = 1000.0):
        self.symbol = symbol
        self.data_path = data_path
        self.balance = starting_balance
        self.ai = GlobalTradingAI()
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

        # 2. Векторизоване передбачення (щоб не чекати годинами)
        logger.info("🧠 AI аналізує історію...")
        features = df[self.ai.feature_cols]
        # Отримуємо ймовірності класу "1" (BUY) для всього датасету одразу
        probabilities = self.ai.model.predict_proba(features)[:, 1]
        df['ai_prob'] = probabilities
        logger.info(f'📊 Макс впевненість AI: {df["ai_prob"].max():.4f}')
        logger.info(f'📊 Сер впевненість AI: {df["ai_prob"].mean():.4f}')
        
        # 3. Симуляція торгів
        in_position = False
        entry_price = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        position_size = 0.0
        
        trades = []
        
        for index, row in df.iterrows():
            current_price = row['close']
            
            # --- ЛОГІКА ВИХОДУ ---
            if in_position:
                # Перевіряємо, чи зачепило SL або TP (спрощено по close, в ідеалі по high/low)
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
                    
                continue # Якщо в позиції, нові не відкриваємо
                
            # --- ЛОГІКА ВХОДУ ---
            if row['ai_prob'] >= self.ai.confidence_threshold:
                trade_params = self.risk_manager.evaluate_trade(
                    df_row=row, 
                    entry_price=current_price, 
                    capital=self.balance,
                    trade_type='BUY'
                )
                
                if trade_params:
                    in_position = True
                    entry_price = trade_params.entry_price
                    stop_loss = trade_params.stop_loss
                    take_profit = trade_params.take_profit
                    position_size = trade_params.position_size_usdt

        # 4. Розрахунок метрик
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t['type'] == 'WIN'])
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
    # Тестуємо на BTC та SOL
    tester_btc = Backtester("BTC/USDT", "app/data/history/BTC_USDT_5m.csv")
    tester_btc.run()
    
    tester_sol = Backtester("SOL/USDT", "app/data/history/SOL_USDT_5m.csv")
    tester_sol.run()