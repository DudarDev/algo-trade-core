import pandas as pd
import numpy as np
import logging
import time
import sys
import glob
from pathlib import Path
import gc

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
        
        self.global_trades = []
        self.total_fee_pct = 0.001  # 0.1%
        
    def run_on_file(self, data_path: str):
        symbol = Path(data_path).stem.split('_')[0] + "/USDT"
        logger.info(f"📊 Аналіз: {symbol}...")

        try:
            # Читаємо тільки останні 5000 рядків
            total_rows = sum(1 for _ in open(data_path, 'r'))
            skip_rows = max(1, total_rows - 5000)
            
            chunk_iter = pd.read_csv(data_path, skiprows=range(1, skip_rows), chunksize=1000)
            df = pd.concat(chunk_iter)

            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms' if isinstance(df['timestamp'].iloc[0], (int, np.integer, float)) else None)
        except Exception as e:
            logger.error(f"Помилка при читанні {symbol}: {e}")
            return

        try:
            df.dropna(inplace=True)
            df_features = self.ai.prepare_features(df)
            del df
            gc.collect()
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

            # === ПРИМУСОВИЙ ДЕБАГ: Змушуємо купувати при AI > 55% ===
            if ai_prob > 0.55: 
                signal = SignalAction.BUY

            if signal == SignalAction.BUY:
                # === ЖОРСТКИЙ ВХІД: Ігноруємо RiskManager ===
                in_position = True
                entry_price = current_price
                
                # Фіксований Стоп-Лос: 1%
                stop_loss = current_price * 0.99
                
                # Фіксований Тейк-Профіт: 2%
                take_profit = current_price * 1.02
                
                # Фіксований об'єм: $100 на угоду
                position_size = 100.0 
        
        del df_features
        gc.collect()

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
        logger.info(f"🏆 ФІНАЛЬНИЙ ЗВІТ БЕКТЕСТУ (Жорсткий Дебаг)")
        logger.info("="*50)
        logger.info(f"Всього угод:        {total_trades}")
        logger.info(f"Win Rate:           {win_rate:.2f}% ({winning_trades}W / {losing_trades}L)")
        logger.info(f"Profit Factor:      {profit_factor:.2f}")
        logger.info(f"Чистий прибуток:    ${net_profit:.2f}")
        logger.info("="*50 + "\n")

if __name__ == "__main__":
    tester = PortfolioBacktester(starting_balance=1000.0)
    tester.run_all()