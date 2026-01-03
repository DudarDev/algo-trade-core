import os
import time
import pandas as pd
from dotenv import load_dotenv
import logging
import ccxt

from app.ai_brain import TradingAI
from app.paper_trader import PaperTrader
from app.market_scanner import MarketScanner
import app.config as config

try:
    from app.telegram_interface import TelegramInterface

    tg_available = True
except ImportError:
    tg_available = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def get_data(exchange, symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker["last"]
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=config.TIMEFRAME, limit=300)
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        return price, df
    except:
        return None, pd.DataFrame()


def main():
    load_dotenv()
    print(f"🚀 Запуск AI-трейдера v6.2 (Stable)...")

    exchange = ccxt.binanceus()
    ai_bot = TradingAI()
    trader = PaperTrader(initial_balance=1000.0)
    scanner = MarketScanner()

    active_pairs = config.PAIRS
    last_scan_time = 0
    SCAN_INTERVAL = 4 * 60 * 60

    tg = None
    if tg_available:
        try:
            tg = TelegramInterface(trader)
            tg.send_alert("🚀 Bot v6.2 Started. All Systems Nominal.")
        except:
            tg = None

    while True:
        try:
            if time.time() - last_scan_time > SCAN_INTERVAL:
                new_pairs = scanner.get_top_volatile_pairs(limit=10)
                if new_pairs:
                    active_pairs = new_pairs
                    logging.info(f"📋 Нові пари: {active_pairs}")
                    if tg and tg.is_running:
                        tg.send_alert(f"🔄 Ринок змінився. Пари: {active_pairs}")
                last_scan_time = time.time()

            for symbol in active_pairs:
                price, df = get_data(exchange, symbol)
                if price is None or df.empty:
                    continue

                trader.update_high(symbol, price)

                if not ai_bot.is_trained:
                    ai_bot.train_new_model(df, symbol)

                signal = ai_bot.predict(df)

                # BUY
                if signal == "BUY":
                    if len(trader.positions) < config.MAX_POSITIONS:
                        trader.buy(symbol, price, config.TRADE_AMOUNT)
                        if tg and tg.is_running and symbol in trader.positions:
                            tg.send_alert(f"🟢 BUY {symbol} @ {price}")

                # SELL
                if symbol in trader.positions:
                    pos = trader.positions[symbol]
                    entry = pos["entry_price"]
                    high = pos["highest_price"]

                    pnl = (price - entry) / entry
                    drawdown = (high - price) / high

                    should_sell = False
                    reason = ""

                    if pnl < -config.STOP_LOSS_PCT:
                        should_sell = True
                        reason = "Stop Loss"
                    elif config.USE_TRAILING_STOP and pnl > config.TRAILING_START_PCT:
                        if drawdown > config.TRAILING_DROP_PCT:
                            should_sell = True
                            reason = "Trailing"
                    elif signal == "SELL" and pnl > 0.002:
                        should_sell = True
                        reason = "AI Signal"

                    if should_sell:
                        trader.sell(symbol, price, reason)
                        if tg and tg.is_running:
                            new_bal = trader.get_balance()
                            tg.send_alert(
                                f"🔴 SELL {symbol} @ {price}\nPnL: {pnl*100:.2f}% ({reason})\n💰 Bal: {new_bal}"
                            )

                time.sleep(1)

            time.sleep(300)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
