import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import glob
import pandas as pd
from src.infrastructure.ai.feature_engineer import calculate_features

files = glob.glob('data_storage/history/*.csv')
for f in files[:3]:
    df = pd.read_csv(f)
    feat = calculate_features(df)
    print(f"--- {f} ---")
    print(f"ATR_PCT: mean={feat['ATR_PCT'].mean():.5f}, 50%={feat['ATR_PCT'].median():.5f}, 95%={feat['ATR_PCT'].quantile(0.95):.5f}, max={feat['ATR_PCT'].max():.5f}")
    print(f"ADX:     mean={feat['ADX'].mean():.3f}, 50%={feat['ADX'].median():.3f}, 95%={feat['ADX'].quantile(0.95):.3f}, max={feat['ADX'].max():.3f}")
