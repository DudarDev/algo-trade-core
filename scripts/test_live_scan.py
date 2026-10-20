import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_panel.settings')
import django
django.setup()

from src.shared.config import settings
from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.engine.infrastructure.market_scanner import MarketScanner
from src.infrastructure.ai.predictor import GlobalTradingAI
from src.engine.application.strategy import HybridStrategy

async def test():
    exchange = ExchangeManager(settings=settings)
    scanner = MarketScanner(exchange_manager=exchange)
    ai = GlobalTradingAI(settings=settings)
    strategy = HybridStrategy(settings=settings)

    print("Fetching top volatile pairs...")
    pairs = await scanner.get_top_volatile_pairs(min_volume=500_000)
    print(f"Pairs ({len(pairs)}): {pairs[:10]}")

    for sym in pairs[:8]:
        try:
            df = await exchange.fetch_data(sym, timeframe=settings.TIMEFRAME, limit=100)
            if df is None or len(df) < 60:
                print(f"{sym}: insufficient data ({len(df) if df is not None else 0})")
                continue
            df_feat = ai.prepare_features(df)
            sig, prob = ai.predict(df_feat)
            action, meta = strategy.get_signal(df_feat, prob, in_position=False)
            curr = df_feat.iloc[-1]
            print(f"{sym}: close={curr['close']:.4f} | prob={prob:.3f} | ATR_PCT={curr['ATR_PCT']:.4f} | ADX={curr['ADX']:.3f} | Regime={meta.regime.value} | Action={action} | Reason={meta.reason}")
        except Exception as e:
            print(f"{sym} error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
