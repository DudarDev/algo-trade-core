"""
RealTrader / LiveBinanceTrader Execution Module.
Забезпечує повну зворотну сумісність для викликів RealTrader із сучасним асинхронним ядром LiveBinanceTrader.
"""
from src.engine.application.live_trader import LiveBinanceTrader

# Псевдонім для зворотної сумісності
RealTrader = LiveBinanceTrader

__all__ = ["LiveBinanceTrader", "RealTrader"]
