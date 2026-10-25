import os
import sys

# Налаштовуємо UTF-8 для виводу в консоль Windows без charmap помилок
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import time
import json
import logging
from logging.handlers import RotatingFileHandler
import asyncio
import numpy as np
import django
from datetime import datetime, timezone
from sqlalchemy import text

# 1. ФІКС ШЛЯХІВ ТА ІНІЦІАЛІЗАЦІЯ DJANGO
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_panel.settings')
django.setup()

# 2. ФІКС ЛОГУВАННЯ (Після django.setup!)
data_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_storage')
os.makedirs(data_dir_path, exist_ok=True)
engine_log_file = os.path.join(data_dir_path, 'engine.log')

file_handler = RotatingFileHandler(engine_log_file, maxBytes=3_000_000, backupCount=2, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = [console_handler, file_handler]
logger = logging.getLogger("Main")

from src.shared.config import settings
from src.shared.db.session import SessionLocal
from src.shared.db.repositories import TradingRepository
from src.engine.domain.models import TradeSide, SignalAction
from src.engine.infrastructure.telegram_notifier import TelegramNotifier
from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.engine.infrastructure.market_scanner import MarketScanner
from src.infrastructure.ai.predictor import GlobalTradingAI
from src.engine.application.strategy import HybridStrategy
from src.engine.application.risk_management import RiskManager, RiskConfig
from src.engine.application.paper_trader import PaperTrader
from src.engine.application.live_trader import LiveBinanceTrader
from src.engine.application.adaptive_risk_controller import AdaptiveRiskController
from src.engine.infrastructure.order_book_analyzer import OrderBookAnalyzer
from src.engine.infrastructure.market_sentiment import MarketSentimentAnalyzer
from src.engine.infrastructure.news_analyzer import NewsAnalyzer


class CryptoBot:
    def __init__(self, db_session, exchange, scanner, ai, strategy, risk_manager, trader):
        logger.info("🚀 Ініціалізація Quantum Scalper Core (Senior Edition)...")
        self.db_session = db_session
        self.exchange = exchange
        self.scanner = scanner
        self.ai = ai
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.trader = trader
        self.concurrency_limit = asyncio.Semaphore(5)
        self.latest_scan_results = {}
        self.data_dir = data_dir_path
        self.htf_trend_cache = {}
        self.btc_market_pulse = "HEALTHY"
        self.btc_pulse_time = 0.0
        self.order_book_analyzer = OrderBookAnalyzer(exchange_manager=self.exchange)
        self.sentiment_analyzer = MarketSentimentAnalyzer()
        self.current_sentiment = {}
        self.news_analyzer = NewsAnalyzer()
        self.load_runtime_config()

    async def get_higher_timeframe_trend(self, symbol: str) -> str:
        """Аналізує старший таймфрейм 1h для відсікання контртрендових входів (MTF Filter)."""
        now = time.time()
        cached = self.htf_trend_cache.get(symbol)
        if cached and (now - cached[1] < 900):  # 15 хвилин кеш
            return cached[0]

        try:
            df_1h = await self.exchange.fetch_data(symbol, timeframe='1h', limit=60)
            if df_1h is not None and len(df_1h) >= 30:
                ema20 = float(df_1h['close'].ewm(span=20).mean().iloc[-1])
                ema50 = float(df_1h['close'].ewm(span=50).mean().iloc[-1])
                curr_price = float(df_1h['close'].iloc[-1])

                if curr_price > ema20 and ema20 > ema50:
                    trend = "BULLISH"
                elif curr_price < ema20 and ema20 < ema50:
                    trend = "BEARISH"
                else:
                    trend = "NEUTRAL"
            else:
                trend = "NEUTRAL"
        except Exception as e:
            logger.debug(f"Помилка аналізу 1h для {symbol}: {e}")
            trend = "NEUTRAL"

        self.htf_trend_cache[symbol] = (trend, now)
        return trend

    async def check_btc_market_pulse(self) -> str:
        """Перевіряє пульс ринку по BTC/USDT (5m). Якщо BTC скидають, блокує альткоїн-лонги."""
        now = time.time()
        if now - self.btc_pulse_time < 30:
            return self.btc_market_pulse

        try:
            df_btc = await self.exchange.fetch_data('BTC/USDT', timeframe='5m', limit=20)
            if df_btc is not None and len(df_btc) >= 5:
                curr_c = float(df_btc['close'].iloc[-1])
                curr_o = float(df_btc['open'].iloc[-1])
                prev_c = float(df_btc['close'].iloc[-2])

                candle_change = (curr_c - curr_o) / curr_o
                two_candle_change = (curr_c - prev_c) / prev_c
                ema20 = float(df_btc['close'].ewm(span=20).mean().iloc[-1])

                if candle_change < -0.0030 or two_candle_change < -0.0045 or (curr_c < ema20 and candle_change < -0.0018):
                    self.btc_market_pulse = "BEARISH_DUMP"
                    logger.warning(f"⚠️ BTC Pulse ALERT: Ринок під тиском (5m: {candle_change*100:.2f}%) -> Альткоїн-лонги заблоковано!")
                else:
                    self.btc_market_pulse = "HEALTHY"
            else:
                self.btc_market_pulse = "HEALTHY"
        except Exception as e:
            logger.debug(f"Помилка аналізу BTC Pulse: {e}")
            self.btc_market_pulse = "HEALTHY"

        self.btc_pulse_time = now
        return self.btc_market_pulse

    def load_runtime_config(self):
        """Динамічне завантаження налаштувань з вебпанелі без перезапуску."""
        cfg_file = os.path.join(self.data_dir, 'runtime_config.json')
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                if 'confidence_threshold' in cfg:
                    new_th = float(cfg['confidence_threshold'])
                    self.strategy.base_threshold = new_th
                    if hasattr(self.strategy, 'risk_controller') and self.strategy.risk_controller:
                        self.strategy.risk_controller.base_confidence = new_th
                    self.settings_obj = getattr(self, 'settings_obj', None)
                    settings.CONFIDENCE_THRESHOLD = new_th
                if 'risk_reward_ratio' in cfg:
                    new_rr = float(cfg['risk_reward_ratio'])
                    self.risk_manager.config.min_risk_reward = new_rr
                    settings.RISK_REWARD_RATIO = new_rr
                if 'max_positions' in cfg:
                    new_max = int(cfg['max_positions'])
                    settings.max_open_positions = new_max
                    settings.MAX_CONCURRENT_POSITIONS = new_max
                if 'trade_fraction' in cfg:
                    new_frac = float(cfg['trade_fraction'])
                    settings.TRADE_FRACTION = new_frac
                    if hasattr(self.trader, 'risk_controller') and self.trader.risk_controller:
                        self.trader.risk_controller.base_risk_pct = new_frac
                if 'min_adx_trend' in cfg:
                    new_adx = float(cfg['min_adx_trend'])
                    self.strategy.min_adx = new_adx
                    if hasattr(self.strategy, 'risk_controller') and self.strategy.risk_controller:
                        self.strategy.risk_controller.base_min_adx = new_adx
                    settings.min_adx_trend = new_adx
            except Exception as e:
                logger.debug(f"Помилка завантаження runtime_config: {e}")

    async def check_command_queue(self):
        """Обробка команд ручного керування (Close / Panic Sell) з вебпанелі."""
        cmd_file = os.path.join(self.data_dir, 'command_queue.json')
        if not os.path.exists(cmd_file):
            return
        try:
            with open(cmd_file, 'r', encoding='utf-8') as f:
                cmd_data = json.load(f)
            try:
                os.remove(cmd_file)
            except Exception:
                pass

            action = cmd_data.get('action')
            if action == 'close_position':
                symbol = cmd_data.get('symbol')
                if symbol and symbol in self.trader.positions:
                    current_price = await self.exchange.fetch_current_price(symbol)
                    if not current_price or current_price <= 0:
                        pos = self.trader.positions[symbol]
                        current_price = pos.highest_price or pos.entry_price
                    logger.info(f"🛑 [РУЧНЕ ЗАКРИТТЯ] Команда з дашборду для {symbol}")
                    await self.trader._close_position(symbol, current_price, reason="Ручне закриття з дашборду")
            elif action == 'close_all':
                logger.warning("🚨 [PANIC EXIT] Екстрене закриття ВСІХ відкритих позицій за командою з дашборду!")
                for symbol in list(self.trader.positions.keys()):
                    current_price = await self.exchange.fetch_current_price(symbol)
                    if not current_price or current_price <= 0:
                        pos = self.trader.positions.get(symbol)
                        current_price = (pos.highest_price or pos.entry_price) if pos else 0
                    if current_price > 0:
                        await self.trader._close_position(symbol, current_price, reason="Panic Exit All")
        except Exception as e:
            logger.error(f"❌ Помилка обробки command_queue: {e}")

    def save_market_radar(self):
        """Збереження знімка ринку та рішень ШІ для вебрадара."""
        radar_file = os.path.join(self.data_dir, 'market_radar.json')
        try:
            radar_list = list(self.latest_scan_results.values())
            radar_list.sort(key=lambda x: (x.get('action') == 'BUY', x.get('confidence', 0.0)), reverse=True)
            with open(radar_file, 'w', encoding='utf-8') as f:
                json.dump(radar_list, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"Помилка збереження market_radar: {e}")

    def is_bot_active(self) -> bool:
        """Безпечна перевірка статусу з автоматичним створенням рядка при потребі."""
        try:
            self.db_session.rollback()
            # 1. Спроба прочитати статус
            query = text("SELECT status FROM bot_config WHERE id=1")
            result = self.db_session.execute(query).scalar()

            if result is not None:
                return result == "active"

            # 2. Рядка немає – пробуємо вставити
            try:
                self.db_session.execute(
                    text("INSERT INTO bot_config (id, status, updated_at) VALUES (1, 'active', :now)"),
                    {"now": datetime.now(timezone.utc)}
                )
                self.db_session.commit()
                logger.info("🆕 bot_config ініціалізовано зі статусом 'active'")
                return True
            except Exception as insert_error:
                self.db_session.rollback()
                logger.warning(f"⚠️ Не вдалося створити bot_config: {insert_error}")
                # Можливо, рядок вже створив інший процес – спробуємо прочитати ще раз
                try:
                    result = self.db_session.execute(text("SELECT status FROM bot_config WHERE id=1")).scalar()
                    return result == "active" if result else False
                except Exception:
                    return False

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"❌ DB Error checking status: {e}")
            return False

    async def setup(self):
        await self.trader.initialize()

    async def cleanup(self):
        logger.info("🧹 Очищення ресурсів...")
        await self.exchange.close()

    async def process_pair(self, symbol: str):
        async with self.concurrency_limit:
            try:
                df = await self.exchange.fetch_data(symbol, timeframe=settings.TIMEFRAME, limit=100)
                if df is None or df.empty:
                    return

                if len(df) < 60:
                    return

                if symbol in self.trader.positions:
                    await self.trader.update_position(symbol, float(df.iloc[-1]['close']))
                    return

                df_features = await asyncio.to_thread(self.ai.prepare_features, df)
                if df_features.empty:
                    return

                final_signal, proba = self.ai.predict(df_features)
                htf_trend = await self.get_higher_timeframe_trend(symbol)

                # Оцінка стакану L2 та фандингу для перспективних сетапів (Етап 1: Win Rate 70%+)
                ob_status = "NEUTRAL"
                fund_sentiment = "HEALTHY_BALANCED"
                if proba >= 0.18:
                    try:
                        ob_res = await self.order_book_analyzer.analyze_order_book(symbol)
                        ob_status = ob_res.get("status", "NEUTRAL")
                        fund_res = await self.order_book_analyzer.get_funding_sentiment(symbol)
                        fund_sentiment = fund_res.get("sentiment", "HEALTHY_BALANCED")
                    except Exception:
                        pass

                signal_action, meta = self.strategy.get_signal(
                    df=df_features,
                    ai_confidence=proba,
                    in_position=(symbol in self.trader.positions),
                    htf_trend=htf_trend,
                    btc_pulse="HEALTHY" if symbol == 'BTC/USDT' else self.btc_market_pulse,
                    order_book_status=ob_status,
                    funding_sentiment=fund_sentiment
                )

                                curr_row = df_features.iloc[-1]
                current_price = float(curr_row['close'])
                adx_val = float(curr_row.get('ADX', 0.0)) * 100.0
                rsi_val = float(curr_row.get('RSI', 0.5)) * 100.0
                vol_spike_val = round(float(curr_row.get('VOL_SPIKE', 1.0)), 2)

                is_buy = (signal_action == "BUY" or signal_action == SignalAction.BUY)
                action_str = "BUY" if is_buy else "HOLD"
                reason_str = meta.reason if hasattr(meta, 'reason') else "Evaluating"

                # Захисний мораторій від екстрених негативних новин (Black Swan Blackout)
                is_news_blocked, news_block_reason = self.news_analyzer.is_symbol_blacklisted_by_news(symbol)
                if is_news_blocked and is_buy:
                    logger.warning(f"🚨 [NEWS BLACKOUT] Вхід у {symbol} заблоковано: {news_block_reason}")
                    is_buy = False
                    action_str = "BLOCKED_NEWS"
                    reason_str = news_block_reason

                self.latest_scan_results[symbol] = {
                    "symbol": symbol,
                    "price": current_price,
                    "confidence": round(proba, 2),
                    "quant_score": getattr(meta, 'quant_score', 0.0),
                    "ensemble_conf": getattr(meta, 'ensemble_conf', round(proba, 2)),
                    "regime": meta.regime.value if hasattr(meta, 'regime') else "CHOPPY_FLAT",
                    "action": action_str,
                    "reason": reason_str,
                    "htf_trend": htf_trend,
                    "btc_pulse": self.btc_market_pulse,
                    "order_book": ob_status,
                    "funding": fund_sentiment,
                    "vol_spike": vol_spike_val,
                    "adx": round(adx_val, 1),
                    "rsi": round(rsi_val, 1),
                    "updated_at": datetime.now(timezone.utc).strftime("%H:%M:%S")
                }

                if is_buy:
                    current_atr = float(curr_row.get('ATR_PCT', 0.002)) * current_price
                    trade_params = self.risk_manager.evaluate_trade(
                        entry_price=current_price, atr=current_atr,
                        capital=self.trader.balance, trade_type='BUY'
                    )
                    if trade_params:
                        logger.info(f"🔥 ВХІД: {symbol} | Conf: {proba:.2f} | R:R: {trade_params.risk_reward_ratio:.2f} | Причина: {reason_str}")
                        
                        # Збираємо числовий зріз ринку для Feature Store
                        features_dict = {}
                        for col_k, col_v in curr_row.items():
                            try:
                                v_flt = float(col_v)
                                if not (np.isnan(v_flt) or np.isinf(v_flt)):
                                    features_dict[str(col_k)] = round(v_flt, 6)
                            except (ValueError, TypeError):
                                continue

                        await self.trader.open_position(
                            symbol=symbol,
                            side=TradeSide.BUY,
                            price=trade_params.entry_price,
                            sl=trade_params.stop_loss,
                            tp=trade_params.take_profit,
                            regime=meta.regime.value if hasattr(meta, 'regime') else "CHOPPY_FLAT",
                            ai_confidence=float(proba),
                            features_snapshot=features_dict
                        )
                else:
                    logger.info(f"📊 {symbol}: Conf={proba:.2f} | {meta.regime.value} | {reason_str}")
            except Exception as e:
                logger.error(f"❌ Помилка обробки {symbol}: {e}")

    async def monitor_open_positions(self):
        """Швидкий моніторинг відкритих позицій кожні 10 секунд (SL / TP / Trailing Stop) та черги команд."""
        while True:
            try:
                await self.check_command_queue()
                if self.trader.positions:
                    for symbol in list(self.trader.positions.keys()):
                        current_price = await self.exchange.fetch_current_price(symbol)
                        if current_price and current_price > 0:
                            await self.trader.update_position(symbol, current_price)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Помилка швидкого моніторингу: {e}")
            await asyncio.sleep(10)

    async def run_cycle(self):
        # 1. Оцінюємо пульс Біткоїна та макро сентимент
        await self.check_btc_market_pulse()
        try:
            self.current_sentiment = await self.sentiment_analyzer.get_market_sentiment()
            logger.info(f"🌐 [Macro Sentiment] F&G Score: {self.current_sentiment.get('score')} ({self.current_sentiment.get('classification')}) | Mode: {self.current_sentiment.get('risk_mode')}")
        except Exception as e:
            logger.debug(f"Sentiment check warning: {e}")
        # 2. Оновлення свіжих новин та активних блекаутів
        try:
            await self.news_analyzer.fetch_latest_news()
            blackouts = self.news_analyzer.get_active_blackouts()
            if blackouts:
                logger.warning(f"🛡️ [News Blackouts Active] Пари під захисним баном: {list(blackouts.keys())}")
        except Exception as e:
            logger.debug(f"News fetch warning: {e}")

        logger.info(f"📡 Пошук волатильних пар (BTC Pulse: {self.btc_market_pulse})...")
        active_pairs = await self.scanner.get_top_volatile_pairs(min_volume=2_000_000)
        open_positions = list(self.trader.positions.keys())
        all_pairs = list(dict.fromkeys(open_positions + (active_pairs or [])))
        if not all_pairs:
            logger.info("ℹ️ Немає активних пар для сканування.")
            return
        tasks = [self.process_pair(symbol) for symbol in all_pairs]
        await asyncio.gather(*tasks)
        self.save_market_radar()
        logger.info(f"✅ Цикл завершено. Баланс: {self.trader.balance:.2f} USDT | Активних позицій: {len(self.trader.positions)}")
        # Очищення пам'яті та кешу для стабільної роботи на 1GB VPS (Zero-Leak Protection)
        if len(self.htf_trend_cache) > 50:
            now_ts = time.time()
            self.htf_trend_cache = {k: v for k, v in self.htf_trend_cache.items() if now_ts - v[1] < 1800}
        import gc
        gc.collect()

    async def start(self):
        logger.info("🟢 Бот запущено! Очікування команди з дашборду...")
        monitor_task = asyncio.create_task(self.monitor_open_positions())
        try:
            while True:
                if not self.is_bot_active():
                    logger.info("⏸️ Бот на паузі. Очікування команди START...")
                    await asyncio.sleep(10)
                    continue
                try:
                    self.load_runtime_config()
                    start_time = time.time()
                    await self.run_cycle()
                    elapsed = time.time() - start_time
                    sleep_time = max(10, 60 - elapsed)
                    await asyncio.sleep(sleep_time)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"❌ Помилка циклу: {e}")
                    await asyncio.sleep(30)
        finally:
            monitor_task.cancel()


async def main():
    db_session = SessionLocal()
    exchange_mgr = ExchangeManager(settings=settings)
    
    # Створюємо єдиний контролер адаптивного ризику (Етап 3)
    risk_controller = AdaptiveRiskController(
        base_confidence=getattr(settings, 'CONFIDENCE_THRESHOLD', 0.55),
        base_min_adx=getattr(settings, 'MIN_ADX_TREND', 25.0),
        base_risk_pct=getattr(settings, 'TRADE_FRACTION', 0.02)
    )

    bot = CryptoBot(
        db_session=db_session,
        exchange=exchange_mgr,
        scanner=MarketScanner(exchange_manager=exchange_mgr),
        ai=GlobalTradingAI(settings=settings),
        strategy=HybridStrategy(settings=settings, risk_controller=risk_controller),
        risk_manager=RiskManager(config=RiskConfig(max_risk_pct=2.0, min_risk_reward=settings.RISK_REWARD_RATIO)),
        trader=LiveBinanceTrader(
            settings=settings,
            repo=TradingRepository(session=db_session),
            notifier=TelegramNotifier() if settings.ENABLE_TELEGRAM else None,
            risk_controller=risk_controller,
            exchange_manager=exchange_mgr
        )
    )
    try:
        await bot.setup()
        await bot.start()
    finally:
        await bot.cleanup()
        db_session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинено вручну.")