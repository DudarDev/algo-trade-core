import glob
import logging
import sys
from pathlib import Path
import pandas as pd
import numpy as np

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.infrastructure.ai.predictor import GlobalTradingAI
from src.engine.application.strategy import HybridStrategy, SignalAction
from src.shared.config import settings

logging.basicConfig(level=logging.WARNING)

def load_all_cached_data():
    ai = GlobalTradingAI(settings=settings)
    history_dir = BASE_DIR / "data_storage" / "history"
    all_files = glob.glob(str(history_dir / "*_5m.csv"))
    cached = []
    print("⏳ Precomputing features and AI inference for historical data...", flush=True)
    for f in all_files:
        df = pd.read_csv(f)
        if len(df) < 200:
            continue
        df_feat = ai.prepare_features(df)
        if df_feat.empty:
            continue
        features = df_feat[ai.feature_cols]
        probs = ai.model.predict_proba(features)[:, 1]
        df_feat['ai_prob'] = probs
        cached.append(df_feat)
    print(f"✅ Precomputed {len(cached)} historical assets.", flush=True)
    return cached

def run_simulation(cached_assets, threshold: float, rr_ratio: float = 1.5, stop_atr_mult: float = 2.0):
    custom_settings = settings.model_copy(update={
        'CONFIDENCE_THRESHOLD': threshold,
        'min_ai_confidence': threshold,
        'RISK_REWARD_RATIO': rr_ratio
    })
    strategy = HybridStrategy(settings=custom_settings)

    fee_pct = 0.001
    starting_balance = 1000.0
    balance = starting_balance
    trades = []

    for df_feat in cached_assets:
        in_pos = False
        entry_price = 0.0
        sl = 0.0
        tp = 0.0
        pos_size = 0.0

        for i in range(50, len(df_feat)):
            row = df_feat.iloc[i]
            price = float(row['close'])
            if price <= 0:
                continue

            if in_pos:
                if row['low'] <= sl:
                    loss_pct = (sl - entry_price) / entry_price
                    pnl = pos_size * (loss_pct - fee_pct)
                    balance += pnl
                    trades.append({'type': 'LOSS', 'pnl': pnl})
                    in_pos = False
                elif row['high'] >= tp:
                    profit_pct = (tp - entry_price) / entry_price
                    pnl = pos_size * (profit_pct - fee_pct)
                    balance += pnl
                    trades.append({'type': 'WIN', 'pnl': pnl})
                    in_pos = False
                continue

            prob = float(row['ai_prob'])
            action, meta = strategy.get_signal(df_feat.iloc[max(0, i-5):i+1], ai_confidence=prob, in_position=False)

            if action == SignalAction.BUY or action == "BUY":
                in_pos = True
                entry_price = price
                atr = float(row.get('ATR_PCT', 0.002)) * price
                sl = price - (atr * stop_atr_mult)
                tp = price + (atr * stop_atr_mult * rr_ratio)
                pos_size = balance * 0.05  # 5% ризику

    total_trades = len(trades)
    wins = sum(1 for t in trades if t['type'] == 'WIN')
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    net_profit = balance - starting_balance
    gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    return {
        'threshold': threshold,
        'rr_ratio': rr_ratio,
        'trades': total_trades,
        'wins': wins,
        'win_rate': round(win_rate, 1),
        'net_pnl': round(net_profit, 2),
        'profit_factor': round(profit_factor, 2),
        'final_balance': round(balance, 2)
    }

if __name__ == "__main__":
    cached = load_all_cached_data()
    print(f"\n{'Threshold':<10} | {'Trades':<8} | {'Win Rate':<10} | {'Profit Factor':<14} | {'Net PnL ($)':<12} | {'Final ($)':<10}", flush=True)
    print("-" * 75, flush=True)
    for th in [0.20, 0.22, 0.25, 0.28, 0.30, 0.33, 0.35]:
        res = run_simulation(cached, threshold=th)
        print(f"{res['threshold']:<10.2f} | {res['trades']:<8} | {res['win_rate']:<9.1f}% | {res['profit_factor']:<14.2f} | ${res['net_pnl']:<11.2f} | ${res['final_balance']:<10.2f}", flush=True)
