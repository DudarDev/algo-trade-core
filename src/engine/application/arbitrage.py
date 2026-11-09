# src/engine/application/arbitrage.py
import os
import json
import time
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.shared.config import Settings
from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.engine.domain.models import ArbitrageOpportunity
import ccxt.async_support as ccxt_async
from src.engine.infrastructure.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data_storage"


class ArbitrageEngine:
    """
    Міжбіржовий арбітражний радар (Binance ↔ Bybit).
    Асинхронно відстежує цінові розриви (Gross та Net спреди з урахуванням біржових комісій).
    Працює через анонімні публічні клієнти без необхідності приватних API-ключів.
    """
    def __init__(
        self,
        settings: Settings,
        exchanges: Optional[Dict[str, ExchangeManager]] = None,
        data_dir: Optional[str] = None
    ):
        self.settings = settings
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.radar_file = self.data_dir / "arbitrage_radar.json"
        self.funding_file = self.data_dir / "funding_radar.json"
        self.telegram = TelegramNotifier()
        self._futures_binance = None
        self._futures_bybit = None

        if exchanges:
            self.exchanges = exchanges
            self._owns_exchanges = False
        else:
            self.exchanges = {
                "binance": ExchangeManager(settings, exchange_id="binance"),
                "bybit": ExchangeManager(settings, exchange_id="bybit")
            }
            self._owns_exchanges = True

        self.recent_alerts: List[Dict[str, Any]] = []
        self.max_recent_alerts = 30
        self.scan_count = 0
        logger.info(f"🌍 [Arbitrage Radar] Ініціалізація. Біржі: {list(self.exchanges.keys())}")

    async def _fetch_ticker_safe(self, name: str, mgr: ExchangeManager, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            # 🛡️ Захист від зависання біржі (8.0s timeout)
            ticker = await asyncio.wait_for(mgr.exchange.fetch_ticker(symbol), timeout=8.0)
            if not isinstance(ticker, dict):
                return None
            bid = float(ticker.get('bid') or 0.0)
            ask = float(ticker.get('ask') or 0.0)
            last = float(ticker.get('last') or 0.0)

            # Fallback якщо bid/ask порожні
            if bid <= 0 and last > 0:
                bid = last
            if ask <= 0 and last > 0:
                ask = last

            if bid > 0 and ask > 0:
                return {
                    'exchange': name,
                    'bid': bid,
                    'ask': ask,
                    'last': last
                }
        except asyncio.TimeoutError:
            logger.debug(f"⚠️ [Arbitrage] API Timeout for {name} ({symbol})")
        except Exception as e:
            logger.debug(f"⚠️ [Arbitrage] Error {name} for {symbol}: {e}")
        return None

    async def _fetch_exchange_tickers(self, name: str, mgr: ExchangeManager, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        # Fast bulk fetch_tickers for all symbols in 1 network request
        try:
            if hasattr(mgr.exchange, 'fetch_tickers'):
                raw = await asyncio.wait_for(mgr.exchange.fetch_tickers(symbols), timeout=15.0)
                if isinstance(raw, dict) and raw:
                    result = {}
                    for sym in symbols:
                        t = raw.get(sym)
                        if isinstance(t, dict):
                            bid = float(t.get('bid') or 0.0)
                            ask = float(t.get('ask') or 0.0)
                            last = float(t.get('last') or 0.0)
                            if bid <= 0 and last > 0: bid = last
                            if ask <= 0 and last > 0: ask = last
                            if bid > 0 and ask > 0:
                                result[sym] = {
                                    'exchange': name,
                                    'bid': bid,
                                    'ask': ask,
                                    'last': last
                                }
                    if len(result) > 0:
                        return result
        except Exception:
            pass

        # Fallback to single fetches
        res = {}
        for s in symbols:
            item = await self._fetch_ticker_safe(name, mgr, s)
            if item:
                res[s] = item
        return res

    async def get_prices(self, symbol: str) -> Dict[str, Dict[str, Any]]:
        tasks = [
            self._fetch_ticker_safe(name, mgr, symbol) 
            for name, mgr in self.exchanges.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices: Dict[str, Dict[str, Any]] = {}
        for res in results:
            if isinstance(res, dict) and 'exchange' in res:
                prices[res['exchange']] = res
        return prices

    async def find_opportunity(self, symbol: str) -> Optional[ArbitrageOpportunity]:
        prices = await self.get_prices(symbol)
        
        if len(prices) < 2:
            return None 

        buy_exchange = min(prices, key=lambda x: prices[x]['ask'])
        buy_price = prices[buy_exchange]['ask']

        sell_exchange = max(prices, key=lambda x: prices[x]['bid'])
        sell_price = prices[sell_exchange]['bid']

        if buy_exchange == sell_exchange or buy_price <= 0:
            return None

        gross_spread_pct = ((sell_price - buy_price) / buy_price) * 100.0
        
        # Комісія 0.1% на кожній біржі = 0.2% roundtrip
        fee_pct = (getattr(self.settings, 'ARBITRAGE_FEE_PCT', 0.001) * 100.0) * 2.0
        net_spread_pct = gross_spread_pct - fee_pct
        min_spread = float(getattr(self.settings, 'ARBITRAGE_MIN_SPREAD_PCT', 0.5))

        if net_spread_pct > min_spread:
            logger.info(
                f"🚨 [АРБІТРАЖНЕ ВІКНО]: {symbol} | "
                f"BUY {buy_exchange}({buy_price}) ➔ SELL {sell_exchange}({sell_price}) | "
                f"Gross: {gross_spread_pct:+.2f}% | Net: {net_spread_pct:+.2f}%"
            )
            return ArbitrageOpportunity(
                symbol=symbol,
                buy_exchange=buy_exchange,
                buy_price=buy_price,
                sell_exchange=sell_exchange,
                sell_price=sell_price,
                gross_spread_pct=round(gross_spread_pct, 4),
                net_spread_pct=round(net_spread_pct, 4)
            )
        
        return None

    async def scan_radar(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Комплексне сканування пулу пар для радар-панелі.
        Повертає живі спреди, активні арбітражні вікна та зберігає стан у JSON/Redis.
        """
        self.scan_count += 1
        start_ts = time.time()
        
        fee_pct = (getattr(self.settings, 'ARBITRAGE_FEE_PCT', 0.001) * 100.0) * 2.0
        min_spread = float(getattr(self.settings, 'ARBITRAGE_MIN_SPREAD_PCT', 0.5))

        # Одночасне паралельне батч-сканування бірж
        tasks = [self._fetch_exchange_tickers(name, mgr, symbols) for name, mgr in self.exchanges.items()]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        exchange_map: Dict[str, Dict[str, Any]] = {}
        for (name, _), res in zip(self.exchanges.items(), batch_results):
            if isinstance(res, dict):
                exchange_map[name] = res
            else:
                exchange_map[name] = {}

        binance_tickers = exchange_map.get('binance', {})
        bybit_tickers = exchange_map.get('bybit', {})

        live_spreads: List[Dict[str, Any]] = []
        active_opportunities: List[Dict[str, Any]] = []

        for symbol in symbols:
            binance_p = binance_tickers.get(symbol)
            bybit_p = bybit_tickers.get(symbol)

            if not binance_p or not bybit_p:
                continue

            bin_bid, bin_ask = binance_p['bid'], binance_p['ask']
            byb_bid, byb_ask = bybit_p['bid'], bybit_p['ask']

            # Варіант А: Купівля на Binance, продаж на Bybit
            spread_bin_to_byb = ((byb_bid - bin_ask) / bin_ask) * 100.0 if bin_ask > 0 else -999.0
            # Варіант Б: Купівля на Bybit, продаж на Binance
            spread_byb_to_bin = ((bin_bid - byb_ask) / byb_ask) * 100.0 if byb_ask > 0 else -999.0

            if spread_bin_to_byb >= spread_byb_to_bin:
                best_buy = 'Binance'
                buy_price = bin_ask
                best_sell = 'Bybit'
                sell_price = byb_bid
                gross_spread = spread_bin_to_byb
            else:
                best_buy = 'Bybit'
                buy_price = byb_ask
                best_sell = 'Binance'
                sell_price = bin_bid
                gross_spread = spread_byb_to_bin

            net_spread = gross_spread - fee_pct
            is_opp = net_spread >= min_spread

            spread_item = {
                "symbol": symbol,
                "binance_bid": round(bin_bid, 4),
                "binance_ask": round(bin_ask, 4),
                "bybit_bid": round(byb_bid, 4),
                "bybit_ask": round(byb_ask, 4),
                "best_buy": best_buy,
                "buy_price": round(buy_price, 4),
                "best_sell": best_sell,
                "sell_price": round(sell_price, 4),
                "gross_spread_pct": round(gross_spread, 3),
                "net_spread_pct": round(net_spread, 3),
                "fee_pct": round(fee_pct, 2),
                "is_opportunity": is_opp,
                "timestamp": round(start_ts, 2)
            }
            live_spreads.append(spread_item)

            if is_opp:
                opp_dict = {
                    "symbol": symbol,
                    "route": f"{best_buy} ➔ {best_sell}",
                    "buy_exchange": best_buy,
                    "buy_price": round(buy_price, 4),
                    "sell_exchange": best_sell,
                    "sell_price": round(sell_price, 4),
                    "gross_spread_pct": round(gross_spread, 3),
                    "net_spread_pct": round(net_spread, 3),
                    "time_str": time.strftime("%H:%M:%S", time.gmtime(start_ts)),
                    "timestamp": round(start_ts, 2)
                }
                active_opportunities.append(opp_dict)
                self.record_alert(opp_dict)

        # Сортування: найбільший спред вгорі
        live_spreads.sort(key=lambda x: x["net_spread_pct"], reverse=True)
        max_spread = live_spreads[0]["net_spread_pct"] if live_spreads else 0.0

        payload = {
            "status": "active",
            "updated_at": round(start_ts, 2),
            "updated_time": time.strftime("%H:%M:%S UTC", time.gmtime(start_ts)),
            "scan_count": self.scan_count,
            "pairs_scanned": len(live_spreads),
            "active_opportunities_count": len(active_opportunities),
            "max_spread_pct": round(max_spread, 3),
            "fee_threshold_pct": round(fee_pct, 2),
            "min_spread_threshold_pct": round(min_spread, 2),
            "exchanges": ["Binance", "Bybit"],
            "opportunities": active_opportunities,
            "live_spreads": live_spreads,
            "recent_alerts": self.recent_alerts[:15]
        }

        self.save_radar_state(payload)
        return payload

    def record_alert(self, opp: Dict[str, Any]) -> None:
        # Уникаємо однакових спам-алертів підряд протягом 15 секунд
        for existing in self.recent_alerts[:3]:
            if existing.get('symbol') == opp.get('symbol') and existing.get('route') == opp.get('route'):
                if abs(existing.get('timestamp', 0) - opp.get('timestamp', 0)) < 15.0:
                    return

        self.recent_alerts.insert(0, opp)
        if len(self.recent_alerts) > self.max_recent_alerts:
            self.recent_alerts = self.recent_alerts[:self.max_recent_alerts]

        # Відправка миттєвого сповіщення в Telegram
        try:
            self.telegram.notify_arbitrage_opportunity(
                symbol=opp.get('symbol', ''),
                route=opp.get('route', ''),
                gross_pct=float(opp.get('gross_spread_pct', 0.0)),
                net_pct=float(opp.get('net_spread_pct', 0.0)),
                best_buy=opp.get('buy_exchange', ''),
                buy_price=float(opp.get('buy_price', 0.0)),
                best_sell=opp.get('sell_exchange', ''),
                sell_price=float(opp.get('sell_price', 0.0))
            )
        except Exception:
            pass

    def save_radar_state(self, payload: Dict[str, Any]) -> None:
        try:
            tmp_file = self.radar_file.with_suffix('.tmp')
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
            tmp_file.replace(self.radar_file)
        except Exception as e:
            logger.debug(f"⚠️ [Arbitrage] Помилка збереження radar.json: {e}")

        # Спроба зберегти в Redis (якщо є redis)
        try:
            import redis
            r = redis.Redis.from_url(getattr(self.settings, 'REDIS_URL', 'redis://127.0.0.1:6379/0'))
            r.set("arbitrage:radar", json.dumps(payload), ex=30)
        except Exception:
            pass

    def _ensure_futures(self) -> None:
        if self._futures_binance is None:
            self._futures_binance = ccxt_async.binance({
                'options': {'defaultType': 'future'},
                'enableRateLimit': True,
                'apiKey': '',
                'secret': ''
            })
        if self._futures_bybit is None:
            self._futures_bybit = ccxt_async.bybit({
                'options': {'defaultType': 'linear'},
                'enableRateLimit': True,
                'apiKey': '',
                'secret': ''
            })

    async def scan_funding_rates(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Сканує ставки фінансування (Funding Rates) на безстрокових ф'ючерсах Binance та Bybit.
        Вираховує річну дохідність (APY) для Дельта-Нейтрального арбітражу (Long Spot + Short Futures).
        """
        self._ensure_futures()
        start_ts = time.time()
        clean_symbols = [s for s in symbols if '/' in s]
        futures_symbols = [f"{s}:USDT" for s in clean_symbols]

        try:
            res_bin, res_byb = await asyncio.gather(
                asyncio.wait_for(self._futures_binance.fetch_funding_rates(futures_symbols), timeout=12.0),
                asyncio.wait_for(self._futures_bybit.fetch_funding_rates(futures_symbols), timeout=12.0),
                return_exceptions=True
            )
        except Exception as e:
            logger.debug(f"⚠️ [Funding Radar] Помилка отримання ставок: {e}")
            res_bin, res_byb = {}, {}

        funding_table = []
        top_opportunity = None

        for s in clean_symbols:
            fs = f"{s}:USDT"
            b_info = res_bin.get(fs, {}) if isinstance(res_bin, dict) else {}
            y_info = res_byb.get(fs, {}) if isinstance(res_byb, dict) else {}
            b_rate = float(b_info.get('fundingRate') or 0.0)
            y_rate = float(y_info.get('fundingRate') or 0.0)

            # 8h rate переводимо в річні APY: rate * 3 рази на добу * 365 днів * 100%
            b_apy = round(b_rate * 3.0 * 365.0 * 100.0, 2)
            y_apy = round(y_rate * 3.0 * 365.0 * 100.0, 2)
            spread_apy = round(abs(b_apy - y_apy), 2)
            best_delta_neutral_apy = max(b_apy, y_apy)

            is_opp = best_delta_neutral_apy >= 10.0 or spread_apy >= 5.0
            row = {
                "symbol": s,
                "binance_8h_pct": round(b_rate * 100.0, 4),
                "binance_apy": b_apy,
                "bybit_8h_pct": round(y_rate * 100.0, 4),
                "bybit_apy": y_apy,
                "best_delta_neutral_exchange": "Binance" if b_apy >= y_apy else "Bybit",
                "spot_futures_apy": best_delta_neutral_apy,
                "cross_exchange_spread_apy": spread_apy,
                "is_opportunity": is_opp,
                "timestamp": round(start_ts, 2)
            }
            funding_table.append(row)

            if is_opp and (top_opportunity is None or best_delta_neutral_apy > top_opportunity['spot_futures_apy']):
                top_opportunity = row

        funding_table.sort(key=lambda x: x["spot_futures_apy"], reverse=True)
        max_apy = funding_table[0]["spot_futures_apy"] if funding_table else 0.0

        payload = {
            "status": "active",
            "updated_at": round(start_ts, 2),
            "updated_time": time.strftime("%H:%M:%S UTC", time.gmtime(start_ts)),
            "pairs_scanned": len(funding_table),
            "max_funding_apy": max_apy,
            "top_opportunity": top_opportunity,
            "funding_rates": funding_table
        }

        self.save_funding_state(payload)
        return payload

    def save_funding_state(self, payload: Dict[str, Any]) -> None:
        try:
            tmp_file = self.funding_file.with_suffix('.tmp')
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
            tmp_file.replace(self.funding_file)
        except Exception as e:
            logger.debug(f"⚠️ [Funding Radar] Помилка збереження JSON: {e}")

        try:
            import redis
            r = redis.Redis.from_url(getattr(self.settings, 'REDIS_URL', 'redis://127.0.0.1:6379/0'))
            r.set("arbitrage:funding", json.dumps(payload), ex=90)
        except Exception:
            pass

    async def close(self) -> None:
        """Звільнення з'єднань асинхронних клієнтів."""
        if self._futures_binance and hasattr(self._futures_binance, 'close'):
            try:
                await self._futures_binance.close()
            except Exception:
                pass
        if self._futures_bybit and hasattr(self._futures_bybit, 'close'):
            try:
                await self._futures_bybit.close()
            except Exception:
                pass

        """Звільнення з'єднань асинхронних клієнтів."""
        if self._owns_exchanges:
            for name, mgr in self.exchanges.items():
                try:
                    await mgr.close()
                except Exception as e:
                    logger.debug(f"Помилка закриття {name}: {e}")
