import pandas as pd
import numpy as np
import logging
import time
import sys
import glob
from pathlib import Path

# Додаємо корінь проєкту для імпортів
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.infrastructure.ai.predictor import GlobalTradingAI
from src.engine.application.risk_management import RiskManager, RiskConfig
from src.engine.application.strategy import HybridStrategy, SignalAction
from src.shared.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Backtester")

class PortfolioBacktester:
    def __init__(self, starting_balance: float = 1000.0):
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.settings = settings
        self.ai = GlobalTradingAI(settings=self.settings)
        self.strategy = HybridStrategy(settings=self.settings)
        
        # Жорстко задаємо скальперські ризики для бектесту
        self.risk_manager = RiskManager(config=RiskConfig(
            max_risk_pct=2.0, 
            min_risk_reward=1.2,  # Швидкий прибуток
            atr_multiplier=1.2    # Короткий стоп-лос
        ))
        
        self.global_trades = []
        self.total_fee_pct = 0.001  # 0.1%
        
    def run_on_file(self, data_path: str):
        symbol = Path(data_path).stem.split('_')[0] + "/USDT"
        logger.info(f"📊 Аналіз: {symbol}...")

        try:
            # OPTIMIZATION: Читаємо лише останні 10,000 рядків, щоб не "вбити" сервер по RAM
            with open(data_path, 'r') as f:
                total_rows = sum(1 for row in f)
            
            skip_rows = max(1, total_rows - 10000)
            
            if skip_rows > 1:
                df = pd.read_csv(data_path, skiprows=range(1, skip_rows))
            else:
                df = pd.read_csv(data_path)

            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms' if isinstance(df['timestamp'].iloc[0], (int, np.integer, float)) else None)
        except Exception as e:
            logger.error(f"Помилка при читанні {symbol}: {e}")
            return

        try:
            df_features = self.ai.prepare_features(df)
        except Exception as e:
            logger.error(f"Помилка генерації фіч {symbol}: {e}")
            return
            
        if df_features.empty or len(df_features) < 50:
            return

        if self.ai.model is None:
            logger.error("❌ Модель AI не знайдена!")
            return
            
        features = df_features[self.ai.feature_cols]
        df_features['ai_prob'] = self.ai.model.predict_proba(features)[:, 1]

        in_position = False
        entry_price = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        position_size = 0.0
        
        for i in range(50, len(df_features)):
            current_window = df_features.iloc[i-10 : i+1].copy()
            curr_row = df_features.iloc[i]
            current_price = float(curr_row['close'])

            # Захист від битих свічок
            if current_price <= 0:
                continue

            if in_position:
                if curr_row['low'] <= stop_loss:
                    loss_pct = (stop_loss - entry_price) / entry_price
                    pnl_usd = position_size * (loss_pct - self.total_fee_pct)
                    self.balance += pnl_usd
                    self.global_trades.append({'type': 'LOSS', 'pnl': pnl_usd})
                    in_position = False
                    
                elif curr_row['high'] >= take_profit:
                    profit_pct = (take_profit - entry_price) / entry_price
                    pnl_usd = position_size * (profit_pct - self.total_fee_pct)
                    self.balance += pnl_usd
                    self.global_trades.append({'type': 'WIN', 'pnl': pnl_usd})
                    in_position = False
                continue

            ai_prob = float(curr_row['ai_prob'])
            signal, meta = self.strategy.get_signal(current_window, ai_prob, in_position=False)

            # === ПРИМУСОВИЙ ДЕБАГ (ПОЧАТОК) ===
            # Змушуємо бота купувати, навіть якщо ШІ впевнений лише на 55%
            if ai_prob > 0.55: 
                signal = SignalAction.BUY
            # === ПРИМУСОВИЙ ДЕБАГ (КІНЕЦЬ) ===

            if signal == SignalAction.BUY:
                current_atr = float(curr_row.get('ATR_PCT', 0.01)) * current_price
                
                # Захист: якщо ATR нульовий
                if current_atr <= 0:
                    current_atr = current_price * 0.01

                try:
                    # === ПРИМУСОВИЙ ДЕБАГ (ПОЧАТОК) ===
                    # Множимо ATR на 2.0, щоб стоп-лос гарантовано пройшов перевірку Ризик-Менеджера
                    trade_params = self.risk_manager.evaluate_trade(
                        entry_price=current_price, 
                        atr=current_atr * 2.0, 
                        capital=self.balance, 
                        trade_type='BUY'
                    )
                    # === ПРИМУСОВИЙ ДЕБАГ (КІНЕЦЬ) ===
                    
                    if trade_params and trade_params.entry_price > 0 and trade_params.stop_loss > 0:
                        in_position = True
                        entry_price = trade_params.entry_price
                        stop_loss = trade_params.stop_loss
                        take_profit = trade_params.take_profit
                        position_size = trade_params.position_size_usdt
                except Exception as e:
                    pass

    def run_all(self):
        start_time = time.time()
        history_dir = BASE_DIR / "data_storage" / "history"
        
        all_files = glob.glob(str(history_dir / "*_5m.csv"))
        
        if not all_files:
             logger.warning("Не знайдено файлів 5m у папці history!")
             return
             
        for file in all_files:
            self.run_on_file(file)

        total_trades = len(self.global_trades)
        winning_trades = sum(1 for t in self.global_trades if t['type'] == 'WIN')
        losing_trades = sum(1 for t in self.global_trades if t['type'] == 'LOSS')
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        net_profit = self.balance - self.starting_balance
        
        gross_profit = sum(t['pnl'] for t in self.global_trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in self.global_trades if t['pnl'] < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        logger.info("\n" + "="*50)
        logger.info(f"🏆 ФІНАЛЬНИЙ ЗВІТ БЕКТЕСТУ (Останні 10к свічок)")
        logger.info("="*50)
        logger.info(f"Всього угод:        {total_trades}")
        logger.info(f"Win Rate:           {win_rate:.2f}% ({winning_trades}W / {losing_trades}L)")
        logger.info(f"Profit Factor:      {profit_factor:.2f}")
        logger.info(f"Чистий прибуток:    ${net_profit:.2f}")
        logger.info("="*50 + "\n")

if __name__ == "__main__":
    tester = PortfolioBacktester(starting_balance=1000.0)
    tester.run_all()