"""
Market Sentiment & Macro Fear and Greed Index Analyzer.
Queries real-time crypto macro sentiment and provides adaptive regime tuning for trading strategies.
"""
import logging
import time
import aiohttp
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MarketSentimentAnalyzer:
    def __init__(self, cache_ttl: int = 600):
        self.cache_ttl = cache_ttl
        self._cached_data: Optional[Dict[str, Any]] = None
        self._last_fetch_time: float = 0.0

    async def get_market_sentiment(self) -> Dict[str, Any]:
        """
        Отримує актуальний індекс Fear & Greed з альтернативного API (alternative.me)
        або повертає надійне збалансоване кешоване значення з адаптивними квантовими рекомендаціями.
        """
        now = time.time()
        if self._cached_data and (now - self._last_fetch_time < self.cache_ttl):
            return self._cached_data

        url = "https://api.alternative.me/fng/?limit=1"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4.0)) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        payload = await response.json()
                        data_list = payload.get("data", [])
                        if data_list:
                            raw_val = int(data_list[0].get("value", 50))
                            classification = data_list[0].get("value_classification", "Neutral")
                            result = self._format_sentiment(raw_val, classification)
                            self._cached_data = result
                            self._last_fetch_time = now
                            return result
        except Exception as e:
            logger.debug(f"Не вдалося отримати Fear & Greed онлайн: {e}")

        if self._cached_data:
            return self._cached_data

        fallback = self._format_sentiment(50, "Neutral")
        return fallback

    def _format_sentiment(self, score: int, classification: str) -> Dict[str, Any]:
        """Форматує квантові параметри управління ризиком на основі індексу сентименту."""
        score = max(0, min(100, int(score)))
        
        if score < 25:
            risk_mode = "DEFENSIVE"
            advice = "Екстремальний страх на ринку: підвищено поріг входу (+0.06), захист депозиту від різких каскадних ліквідацій."
            conf_adjustment = 0.06
            size_multiplier = 0.65
            badge_color = "red"
        elif score < 45:
            risk_mode = "CAUTIOUS"
            advice = "Помірний страх: обережні покупки на підтверджених відскоках з динамічними коротшими стопами."
            conf_adjustment = 0.02
            size_multiplier = 0.85
            badge_color = "amber"
        elif score <= 55:
            risk_mode = "BALANCED"
            advice = "Нейтральний ринок: стандартне збалансоване виконання за технічними імбалансами та L2 стаканом."
            conf_adjustment = 0.0
            size_multiplier = 1.0
            badge_color = "blue"
        elif score <= 75:
            risk_mode = "MOMENTUM"
            advice = "Помірний оптимізм (Greed): сприятливий ринок для трендових лонгів та швидкого закріплення часткового прибутку."
            conf_adjustment = -0.02
            size_multiplier = 1.15
            badge_color = "emerald"
        else:
            risk_mode = "CAUTIOUS_TAKE_PROFIT"
            advice = "Екстремальна ейфорія: ризик раптової корекції. Трейлінг-стоп підтягнуто, входи на вертикальних піках обмежено."
            conf_adjustment = 0.04
            size_multiplier = 0.75
            badge_color = "purple"

        return {
            "score": score,
            "classification": classification,
            "risk_mode": risk_mode,
            "advice": advice,
            "confidence_adjustment": conf_adjustment,
            "size_multiplier": size_multiplier,
            "badge_color": badge_color
        }
