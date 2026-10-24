"""
AI Crypto News Intelligence & Black Swan Blackout Filter.
Fetches real-time crypto news feeds, runs NLP sentiment & impact analysis,
and provides institutional protection (Blackout Filter) against high-risk breaking events.
"""
import logging
import time
import re
import aiohttp
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class NewsAnalyzer:
    FEEDS = [
        {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
        {"name": "Decrypt", "url": "https://decrypt.co/feed"},
    ]

    COIN_PATTERNS = {
        "BTC": [r"\bbtc\b", r"\bbitcoin\b"],
        "ETH": [r"\beth\b", r"\bethereum\b", r"\bether\b"],
        "SOL": [r"\bsol\b", r"\bsolana\b"],
        "BNB": [r"\bbnb\b", r"\bbinance coin\b"],
        "XRP": [r"\bxrp\b", r"\bripple\b"],
        "DOGE": [r"\bdoge\b", r"\bdogecoin\b"],
        "ADA": [r"\bada\b", r"\bcardano\b"],
        "AVAX": [r"\bavax\b", r"\bavalanche\b"],
        "LINK": [r"\blink\b", r"\bchainlink\b"],
        "NEAR": [r"\bnear\b", r"\bnear protocol\b"],
        "SUI": [r"\bsui\b"],
        "PEPE": [r"\bpepe\b"],
    }

    BULLISH_KEYWORDS = [
        "surge", "surges", "surging", "record", "high", "approval", "approved",
        "inflow", "inflows", "etf", "rally", "rallies", "bullish", "gain", "gains",
        "pump", "jump", "jumps", "soar", "soars", "buying", "accumulate", "accumulation",
        "milestone", "ath", "all-time high", "breakout", "partnership", "adoption",
        "upgrade", "launch", "support", "stimulus", "institutional"
    ]

    BEARISH_KEYWORDS = [
        "hack", "hacked", "exploit", "exploited", "lawsuit", "sec", "sue", "sues",
        "ban", "banned", "crash", "crashes", "plunge", "plunges", "dump", "dumps",
        "liquidation", "liquidated", "fraud", "scam", "outage", "freeze", "frozen",
        "halt", "halted", "breach", "subpoena", "investigation", "collapse",
        "insolvency", "default", "warning", "attack", "theft", "stolen"
    ]

    HIGH_IMPACT_TRIGGERS = [
        "hack", "exploit", "sec", "lawsuit", "ban", "outage", "halt", "collapse",
        "etf approval", "all-time high", "record", "liquidation", "breach"
    ]

    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self._cached_news: List[Dict[str, Any]] = []
        self._last_fetch_time: float = 0.0
        self._active_blackouts: Dict[str, Dict[str, Any]] = {}  # {symbol: {"reason": ..., "expires_at": ...}}

    async def fetch_latest_news(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Асинхронно отримує свіжі новини з провідних світових джерел (Cointelegraph, Decrypt),
        проганяє через AI NLP аналізатор та оновлює список блекаутів.
        """
        now = time.time()
        if not force_refresh and self._cached_news and (now - self._last_fetch_time < self.cache_ttl):
            return self._cached_news

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        all_articles = []

        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=6.0)) as session:
            for feed in self.FEEDS:
                try:
                    async with session.get(feed["url"]) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            parsed = self._parse_rss(content, feed["name"])
                            all_articles.extend(parsed)
                except Exception as e:
                    logger.debug(f"Помилка завантаження RSS {feed['name']}: {e}")

        if all_articles:
            # Сортуємо новини за часом (найсвіжіші першими)
            all_articles.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            self._cached_news = all_articles[:40]
            self._last_fetch_time = now
            self._update_blackouts()
            return self._cached_news

        return self._cached_news or []

    def _parse_rss(self, xml_bytes: bytes, source_name: str) -> List[Dict[str, Any]]:
        articles = []
        try:
            root = ET.fromstring(xml_bytes)
            items = root.findall(".//item")
            for item in items:
                title_el = item.find("title")
                link_el = item.find("link")
                pub_el = item.find("pubDate")
                desc_el = item.find("description")

                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                link = link_el.text.strip() if link_el is not None and link_el.text else ""
                pub_date = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
                desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

                if not title:
                    continue

                # Очищаємо HTML-теги з опису
                clean_desc = re.sub(r"<[^>]+>", "", desc)

                # NLP AI аналіз
                analysis = self.analyze_text(title, clean_desc)

                articles.append({
                    "id": f"{source_name}_{hash(link or title)}",
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "pub_date": pub_date,
                    "timestamp": time.time(),
                    "symbols": analysis["symbols"],
                    "sentiment": analysis["sentiment"],
                    "sentiment_score": analysis["sentiment_score"],
                    "impact": analysis["impact"],
                    "ai_takeaway": analysis["ai_takeaway"],
                })
        except Exception as e:
            logger.debug(f"Помилка парсингу XML {source_name}: {e}")
        return articles

    def analyze_text(self, title: str, description: str = "") -> Dict[str, Any]:
        """
        Аналізує текст новини на згадки криптоактивів, розраховує сентимент та рівень впливу (Impact).
        """
        full_text = f"{title} {description}".lower()

        # 1. Детекція монет
        detected_symbols = []
        for sym, patterns in self.COIN_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, full_text):
                    detected_symbols.append(sym)
                    break

        if not detected_symbols:
            detected_symbols = ["CRYPTO"]

        # 2. Розрахунок сентименту
        bull_score = sum(1 for kw in self.BULLISH_KEYWORDS if re.search(r"\b" + kw + r"\b", full_text))
        bear_score = sum(1 for kw in self.BEARISH_KEYWORDS if re.search(r"\b" + kw + r"\b", full_text))

        total_kw = bull_score + bear_score
        if total_kw > 0:
            raw_score = (bull_score - bear_score) / total_kw
        else:
            raw_score = 0.0

        if raw_score >= 0.20:
            sentiment = "BULLISH"
        elif raw_score <= -0.20:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"

        # 3. Визначення рівня впливу (Impact)
        impact = "LOW"
        for trig in self.HIGH_IMPACT_TRIGGERS:
            if re.search(r"\b" + trig + r"\b", full_text):
                impact = "HIGH"
                break
        if impact == "LOW" and total_kw >= 2:
            impact = "MEDIUM"

        # 4. Формування лаконічного висновку ШІ (AI Key Takeaway)
        symbols_str = ", ".join(detected_symbols)
        if sentiment == "BULLISH" and impact == "HIGH":
            ai_takeaway = f"🔥 Сильний бичачий каталізатор для {symbols_str}: потенційний імпульс зростання та приплив ліквідності."
        elif sentiment == "BULLISH":
            ai_takeaway = f"📈 Позитивний новинний фон для {symbols_str}: помірна підтримка висхідного руху."
        elif sentiment == "BEARISH" and impact == "HIGH":
            ai_takeaway = f"🚨 Критичний ризик для {symbols_str}! Можливі каскадні розпродажі — рекомендовано захисний мораторій."
        elif sentiment == "BEARISH":
            ai_takeaway = f"⚠️ Негативний тиск на {symbols_str}: підвищена обережність на коротких таймфреймах."
        else:
            ai_takeaway = f"ℹ️ Нейтральний інфопривід щодо {symbols_str}: помітний вплив на ціну малоймовірний."

        return {
            "symbols": detected_symbols,
            "sentiment": sentiment,
            "sentiment_score": round(raw_score, 2),
            "impact": impact,
            "ai_takeaway": ai_takeaway
        }

    def _update_blackouts(self):
        """Оновлює список активів під захисним блекаутом на основі свіжих HIGH BEARISH новин."""
        now = time.time()
        # Очищаємо застарілі блекаути (тривалість 90 хвилин)
        self._active_blackouts = {
            sym: data for sym, data in self._active_blackouts.items()
            if data["expires_at"] > now
        }

        # Шукаємо нові критичні загрози
        for article in self._cached_news:
            if article["sentiment"] == "BEARISH" and article["impact"] == "HIGH":
                for sym in article["symbols"]:
                    if sym != "CRYPTO":
                        self._active_blackouts[sym] = {
                            "symbol": sym,
                            "reason": article["title"],
                            "source": article["source"],
                            "expires_at": now + (90 * 60)  # 90 хвилин захисного бану
                        }
                        logger.warning(f"🚨 [NEWS BLACKOUT ACTIVATED] Захисне блокування {sym}/USDT: {article['title']}")

    def is_symbol_blacklisted_by_news(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """
        Перевіряє, чи актив знаходиться під захисним мораторієм через екстрені негативні новини.
        """
        base_asset = symbol.replace("/USDT", "").replace("USDT", "").upper()
        now = time.time()
        blackout = self._active_blackouts.get(base_asset)
        if blackout:
            if blackout["expires_at"] > now:
                mins_left = int((blackout["expires_at"] - now) / 60)
                return True, f"Захисний блекаут ({mins_left} хв залишилось): {blackout['reason']}"
            else:
                del self._active_blackouts[base_asset]

        return False, None

    def get_active_blackouts(self) -> Dict[str, Any]:
        """Повертає поточні активні блекаути з залишковим часом."""
        now = time.time()
        result = {}
        for sym, data in list(self._active_blackouts.items()):
            if data["expires_at"] > now:
                mins_left = max(1, int((data["expires_at"] - now) / 60))
                result[sym] = {
                    "reason": data["reason"],
                    "source": data["source"],
                    "minutes_remaining": mins_left
                }
            else:
                del self._active_blackouts[sym]
        return result
