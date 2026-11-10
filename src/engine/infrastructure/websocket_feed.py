import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List
import aiohttp

logger = logging.getLogger(__name__)

class WebSocketFeed:
    """
    Високопродуктивний асинхронний стрім котирувань через WebSockets (Binance & Bybit).
    Забезпечує суб-мілісекундний доступ до Best Bid / Best Ask (BBO) без затримок REST API.
    """
    def __init__(self, symbols: Optional[List[str]] = None):
        self.symbols = symbols or [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
            'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'LINK/USDT', 'NEAR/USDT',
            'SUI/USDT', 'APT/USDT', 'DOT/USDT', 'ARB/USDT', 'OP/USDT',
            'TIA/USDT', 'INJ/USDT', 'BCH/USDT', 'LTC/USDT', 'UNI/USDT'
        ]
        self.prices: Dict[str, Dict[str, Dict[str, float]]] = {
            "binance": {},
            "bybit": {}
        }
        self.latencies: Dict[str, float] = {
            "binance": 0.0,
            "bybit": 0.0
        }
        self.ticks_count = 0
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._session: Optional[aiohttp.ClientSession] = None

    def _normalize_symbol(self, raw_symbol: str) -> str:
        s = raw_symbol.upper().replace("/", "").replace("-", "")
        if s.endswith("USDT"):
            base = s[:-4]
            return f"{base}/USDT"
        return raw_symbol

    def _to_binance_stream_name(self, symbol: str) -> str:
        clean = symbol.lower().replace("/", "")
        return f"{clean}@bookTicker"

    def _to_bybit_symbol(self, symbol: str) -> str:
        return symbol.upper().replace("/", "")

    def get_bbo(self, symbol: str, exchange: str = "binance") -> Optional[Dict[str, float]]:
        """Повертає свіжий BBO (Best Bid / Ask / Last) або None, якщо даних немає або вони старі (>3с)."""
        data = self.prices.get(exchange, {}).get(symbol)
        if not data:
            return None
        if time.time() - data.get("timestamp", 0) > 4.0:
            return None
        return data

    def get_price(self, symbol: str, exchange: str = "binance") -> Optional[float]:
        """Повертає актуальну середню або останню ціну інструменту."""
        bbo = self.get_bbo(symbol, exchange)
        if bbo:
            return bbo.get("last") or (bbo.get("bid", 0.0) + bbo.get("ask", 0.0)) / 2.0
        return None

    def get_stats(self) -> Dict[str, Any]:
        now = time.time()
        bin_active = any(now - v.get("timestamp", 0) < 4.0 for v in self.prices.get("binance", {}).values())
        byb_active = any(now - v.get("timestamp", 0) < 4.0 for v in self.prices.get("bybit", {}).values())
        return {
            "status": "online" if (bin_active or byb_active) else "connecting",
            "binance_active": bin_active,
            "bybit_active": byb_active,
            "binance_pairs": len(self.prices.get("binance", {})),
            "bybit_pairs": len(self.prices.get("bybit", {})),
            "binance_latency_ms": round(self.latencies.get("binance", 0.0), 1),
            "bybit_latency_ms": round(self.latencies.get("bybit", 0.0), 1),
            "total_ticks": self.ticks_count
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._session = aiohttp.ClientSession()
        self._tasks.append(asyncio.create_task(self._binance_loop()))
        self._tasks.append(asyncio.create_task(self._bybit_loop()))
        logger.info(f"⚡ [WebSocket Feed] Запущено стрім котирувань для {len(self.symbols)} пар (Binance & Bybit)...")

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("🛑 [WebSocket Feed] Зупинено фонові сокети.")

    async def _binance_loop(self) -> None:
        streams = "/".join([self._to_binance_stream_name(s) for s in self.symbols])
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        backoff = 1.0

        while self._running:
            try:
                t0 = time.time()
                async with self._session.ws_connect(url, timeout=10.0, heartbeat=20.0) as ws:
                    self.latencies["binance"] = (time.time() - t0) * 1000.0
                    backoff = 1.0
                    logger.info(f"✅ [WebSocket Feed] Binance WS підключено ({self.latencies['binance']:.1f}ms).")

                    async for msg in ws:
                        if not self._running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                payload = json.loads(msg.data)
                                data = payload.get("data", {})
                                raw_sym = data.get("s", "")
                                if not raw_sym:
                                    continue
                                symbol = self._normalize_symbol(raw_sym)
                                bid = float(data.get("b", 0.0))
                                ask = float(data.get("a", 0.0))
                                if bid > 0 and ask > 0:
                                    self.prices["binance"][symbol] = {
                                        "bid": bid,
                                        "ask": ask,
                                        "last": (bid + ask) / 2.0,
                                        "timestamp": time.time()
                                    }
                                    self.ticks_count += 1
                            except Exception:
                                pass
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"⚠️ [WebSocket Feed] Binance WS реконнект через {backoff:.1f}с: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 10.0)

    async def _bybit_loop(self) -> None:
        url = "wss://stream.bybit.com/v5/public/spot"
        bybit_syms = [self._to_bybit_symbol(s) for s in self.symbols]
        args = [f"orderbook.1.{s}" for s in bybit_syms]
        sub_msg = json.dumps({"op": "subscribe", "args": args})
        backoff = 1.0

        while self._running:
            try:
                t0 = time.time()
                async with self._session.ws_connect(url, timeout=10.0, heartbeat=20.0) as ws:
                    self.latencies["bybit"] = (time.time() - t0) * 1000.0
                    backoff = 1.0
                    await ws.send_str(sub_msg)
                    logger.info(f"✅ [WebSocket Feed] Bybit WS підключено ({self.latencies['bybit']:.1f}ms).")

                    last_ping = time.time()
                    while self._running:
                        try:
                            msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
                        except asyncio.TimeoutError:
                            if time.time() - last_ping > 18.0:
                                await ws.send_str(json.dumps({"op": "ping"}))
                                last_ping = time.time()
                            continue

                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                payload = json.loads(msg.data)
                                topic = payload.get("topic", "")
                                if topic.startswith("orderbook.1."):
                                    data = payload.get("data", {})
                                    raw_sym = data.get("s", "")
                                    symbol = self._normalize_symbol(raw_sym)
                                    bids = data.get("b", [])
                                    asks = data.get("a", [])
                                    bid = float(bids[0][0]) if bids else 0.0
                                    ask = float(asks[0][0]) if asks else 0.0
                                    if bid > 0 and ask > 0:
                                        self.prices["bybit"][symbol] = {
                                            "bid": bid,
                                            "ask": ask,
                                            "last": (bid + ask) / 2.0,
                                            "timestamp": time.time()
                                        }
                                        self.ticks_count += 1
                            except Exception:
                                pass
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"⚠️ [WebSocket Feed] Bybit WS реконнект через {backoff:.1f}с: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 10.0)

ws_feed = WebSocketFeed()
