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
        self.total_fee_pct = 0.001  # 0.1% (Комісія біржі)
        
    def run_on_file(self, data_path: str):
        symbol = Path(data_path).stem.split('_')[0] + "/USDT"
        logger.info(f"📊 Аналіз: {symbol}...")

        try:
            total_rows = sum(1 for _ in open(data_path, 'r'))
            
            # 🛡️ Автоматичний захист від битих/малих файлів
            if total_rows < 150:
                logger.warning(f"⚠️ Файл для {symbol} занадто малий ({total_rows} рядків). Пропускаю.")
                return

            skip_lines = max(1, total_rows - 5000)
            
            headers = pd.read_csv(data_path, nrows=0).columns
            df = pd.read_csv(data_path, skiprows=skip_lines, names=headers)

            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms' if isinstance(df['timestamp'].iloc[0], (int, np.integer, float)) else None)
        except Exception as e:
            logger.error(f"Помилка при читанні {symbol}: {e}")
            return

        try:
            # Генеруємо індикатори (ATR, RSI, MACD тощо)
            df_features = self.ai.prepare_features(df)
            df_features.dropna(inplace=True) 
            del df
            gc.collect()
        except Exception as e:
            logger.error(f"Помилка генерації фіч {symbol}: {e}")
            return
            
        if df_features.empty or len(df_features) < 50:
            logger.warning(f"⚠️ Недостатньо даних для {symbol} після генерації індикаторів.")
            return

        if self.ai.model is None:
            logger.error("❌ Модель AI не знайдена!")
            return
            
        # Розраховуємо ймовірності від штучного інтелекту для ВСІХ рядків
        features = df_features[self.ai.feature_cols]
        df_features['ai_prob'] = self.ai.model.predict_proba(features)[:, 1]

        in_position = False
        entry_price = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        position_size = 0.0
        
        logger.info(f"✅ Завантажено {len(df_features)} свічок для {symbol}. Запускаю торговий цикл...")

        for i in range(50, len(df_features)):
            curr_row = df_features.iloc[i]
            current_price = float(curr_row['close'])

            if current_price <= 0:
                continue

            # === ЛОГІКА ВИХОДУ З ПОЗИЦІЇ (RISK MANAGEMENT) ===
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
                continue # Чекаємо наступної свічки, якщо в позиції

            # === РЕАЛЬНА ТОРГОВА ЛОГІКА (ВХІД) ===
            # ✅ ВИПРАВЛЕНО: Замість неіснуючого SignalAction.HOLD використовуємо None
            signal = None
            ai_prob = float(curr_row['ai_prob'])

            # Якщо модель впевнена на >65%, що ціна піде вгору - купуємо
            if ai_prob >= 0.65:
                signal = SignalAction.BUY

            if signal == SignalAction.BUY:
                in_position = True
                entry_price = current_price
                
                # Динамічний RiskManager на основі ATR (якщо його немає, беремо 1.5% волатильності)
                atr = float(curr_row.get('atr', current_price * 0.015))
                
                # Налаштування: Стоп = 2 ATR, Тейк = 3 ATR (співвідношення 1:1.5)
                stop_loss = current_price - (atr * 2.0)
                take_profit = current_price + (atr * 3.0)
                
                # Динамічний сайз: входимо на 10% від ПОТОЧНОГО депозиту (складний відсоток)
                position_size = min(self.balance * 0.10, self.balance)
        
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
            # ✅ ВИПРАВЛЕНО: Повернуто пропуск битого файлу UNI, щоб сервер не падав
            if "UNI" in file:
                logger.warning(f"⚠️ Пропускаю проблемний файл: {file}")
                continue
            self.run_on_file(file)

        # === ПІДРАХУНОК СТАТИСТИКИ ===
        total_trades = len(self.global_trades)
        winning_trades = sum(1 for t in self.global_trades if t['type'] == 'WIN')
        losing_trades = sum(1 for t in self.global_trades if t['type'] == 'LOSS')
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        net_profit = self.balance - self.starting_balance
        
        gross_profit = sum(t['pnl'] for t in self.global_trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in self.global_trades if t['pnl'] < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        logger.info("\n" + "="*50)
        logger.info(f"🏆 ФІНАЛЬНИЙ ЗВІТ БЕКТЕСТУ (Реальна AI Модель)")
        logger.info("="*50)
        logger.info(f"Початковий баланс:  ${self.starting_balance:.2f}")
        logger.info(f"Кінцевий баланс:    ${self.balance:.2f}")
        logger.info(f"Всього угод:        {total_trades}")
        logger.info(f"Win Rate:           {win_rate:.2f}% ({winning_trades}W / {losing_trades}L)")
        logger.info(f"Profit Factor:      {profit_factor:.2f}")
        logger.info(f"Чистий прибуток:    ${net_profit:.2f}")
        logger.info(f"Час виконання:      {(time.time() - start_time):.2f} сек")
        logger.info("="*50 + "\n")

if __name__ == "__main__":
    tester = PortfolioBacktester(starting_balance=1000.0)
    tester.run_all()