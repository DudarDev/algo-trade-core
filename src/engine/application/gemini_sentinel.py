import logging
import time
import json
import aiohttp
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class GeminiSentinel:
    """
    Квантовий ШІ-асистент та макро-стратег на базі Google Gemini 1.5 Flash.
    Забезпечує інтерактивний аналіз ринку, пояснення угод та оцінку системних ризиків.
    """
    def __init__(self, settings: Any = None):
        self.settings = settings
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        self._cache: Dict[str, Any] = {}

    def get_api_key(self) -> Optional[str]:
        if not self.settings:
            return None
        key = getattr(self.settings, 'GEMINI_API_KEY', None)
        if key:
            if hasattr(key, 'get_secret_value'):
                return key.get_secret_value()
            return str(key)
        return None

    async def ask_copilot(self, query: str, context: Dict[str, Any], lang: str = "ua") -> Dict[str, Any]:
        """
        Обробляє запит користувача, враховуючи повний контекст портфеля, активних позицій та макро-метрик.
        """
        api_key = self.get_api_key()

        # Якщо ключа немає - запускаємо розумний локальний квант-рушій
        if not api_key or api_key.strip() in ("", "dummy", "none", "None"):
            return self._local_quant_copilot(query, context, lang)

        system_instruction = (
            "Ти — старший кількісний аналітик (Senior Quant AI Copilot) торгової системи AlgoTrade PRO. "
            "Твоя мета: аналізувати угоди, пояснювати квантові метрики, оцінювати ризики скальпінгу та давати чіткі рекомендації. "
            f"Відповідай мовою: {'Українська' if lang == 'ua' else 'English'}. "
            "Відповідай лаконічно, структуровано, у форматі Markdown з корисними фінансовими інсайтами."
        )

        prompt = (
            f"ПОТОЧНИЙ СТАН ТОРГОВОГО РУШІЯ:\n"
            f"- Баланс / Equity: ${context.get('balance', 0):.2f} USDT (Вільна готівка: ${context.get('free_cash', 0):.2f})\n"
            f"- Загальний PnL: ${context.get('total_pnl', 0):.2f} USDT | Вінрейт: {context.get('win_rate', 0):.1f}% | Угод: {context.get('total_trades', 0)}\n"
            f"- Пульс ринку BTC: {context.get('btc_pulse', 'NORMAL')} | Macro Fear & Greed: {context.get('fg_score', 50)} ({context.get('fg_mode', 'BALANCED')})\n"
            f"- Активні відкриті позиції: {context.get('active_positions', [])}\n"
            f"- Останні закриті угоди: {context.get('recent_trades', [])[:5]}\n\n"
            f"ЗАПИТ ТРЕЙДЕРА: \"{query}\"\n\n"
            f"Надай експертний, чіткий розбір з конкретними цифрами та висновком."
        )

        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": f"{system_instruction}\n\n{prompt}"}]
            }],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 600
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}?key={api_key}"
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            reply_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            return {
                                "status": "success",
                                "source": "gemini-1.5-flash",
                                "reply": reply_text.strip()
                            }
                    logger.warning(f"⚠️ Gemini API статус {resp.status}. Перехід на локальний рушій.")
        except Exception as e:
            logger.debug(f"Gemini API запит завершився з помилкою: {e}. Перехід на локальний рушій.")

        return self._local_quant_copilot(query, context, lang)

    def _local_quant_copilot(self, query: str, context: Dict[str, Any], lang: str = "ua") -> Dict[str, Any]:
        """
        Вбудований локальний Rule-Based Quant Engine для миттєвих відповідей без затримок та API ключів.
        """
        q = query.lower()
        bal = context.get('balance', 967.56)
        pnl = context.get('total_pnl', -31.78)
        wr = context.get('win_rate', 55.9)
        trades = context.get('total_trades', 93)
        btc_pulse = context.get('btc_pulse', 'NORMAL')
        active_pos = context.get('active_positions', [])

        if lang == 'ua':
            if any(k in q for k in ['статус', 'стан', 'баланс', 'pnl', 'депозит']):
                text = (
                    f"### 📊 Огляд Квантового Станції\n"
                    f"* **Капітал (Equity):** `${bal:.2f} USDT`\n"
                    f"* **Реалізований PnL:** `${pnl:.2f} USDT`\n"
                    f"* **Точність (Win Rate):** `{wr:.1f}%` ({trades} закритих угод)\n"
                    f"* **Пульс BTC:** `{btc_pulse}` | **Відкритих позицій:** `{len(active_pos)}`\n\n"
                    f"**Оцінка ризику:** Увімкнено жорсткий стоп `$3.50 max loss` та Breakeven на `+0.7%`. "
                    f"Система утримує стабільне співвідношення прибутковості."
                )
            elif any(k in q for k in ['btc', 'біткоїн', 'ринок', 'пульс', 'тренд']):
                text = (
                    f"### 🌐 Макро-аналіз Ринку (BTC Pulse: {btc_pulse})\n"
                    f"* **Стан старшого таймфрейму (1h):** Біткоїн утримується у коридорі волатильності.\n"
                    f"* **Macro Sentiment:** Індекс Страху та Жадібності на рівні `50 (Neutral)`. Режим: `BALANCED`.\n"
                    f"* **Рекомендація системи:** Дозволено скальпінг-входи по топ-20 парах за умови наявності обсягу `Volume > $5M` та збігу імпульсу `ADX > 25`."
                )
            elif any(k in q for k in ['чому', 'угода', 'трейд', 'позиц', 'стоп']):
                text = (
                    f"### 🎯 Логіка Управління Позиціями\n"
                    f"* Бот використовує гібридну стратегію: **Dual AI Ensemble (RF 55% + LightGBM 45%)** з фільтром мікроструктури L2.\n"
                    f"* **Фіксація профіту:** 50% об'єму закривається на `+1.5% (TP1)`, а залишок переводиться в гарантований безубиток (+0.25%).\n"
                    f"* **Захист:** Якщо монета показує небезпечний спред (>0.25%) чи негативні новини, бот негайно блокує вхід."
                )
            else:
                text = (
                    f"### 🤖 Квантовий Асистент AlgoTrade PRO\n"
                    f"Система активна та моніторить ринок. Баланс: `${bal:.2f} USDT`, Вінрейт: `{wr:.1f}%`.\n\n"
                    f"*Ви можете запитати:*\n"
                    f"1. *«Який поточний статус та баланс?»*\n"
                    f"2. *«Яка ситуація по ринку біткоїна?»*\n"
                    f"3. *«Як працює логіка виходу та стоп-лосс?»*\n\n"
                    f"*(💡 Для необмеженого LLM аналізу підключіть Gemini API ключ у Налаштуваннях)*"
                )
        else:
            if any(k in q for k in ['status', 'balance', 'pnl', 'equity']):
                text = (
                    f"### 📊 Quant Terminal Executive Brief\n"
                    f"* **Total Equity:** `${bal:.2f} USDT`\n"
                    f"* **Realized PnL:** `${pnl:.2f} USDT`\n"
                    f"* **Win Rate:** `{wr:.1f}%` across `{trades}` closed scalps\n"
                    f"* **BTC Market Pulse:** `{btc_pulse}` | **Active Positions:** `{len(active_pos)}`\n\n"
                    f"**Risk Evaluation:** Operating under `$3.50 Hard Stop Cap` and `+0.7% Breakeven Lock`."
                )
            elif any(k in q for k in ['btc', 'bitcoin', 'market', 'trend']):
                text = (
                    f"### 🌐 Macro Market Intel (BTC Pulse: {btc_pulse})\n"
                    f"* **Higher TF (1h):** Market consolidating with healthy volume profile.\n"
                    f"* **Fear & Greed Index:** `50 (Neutral)` in `BALANCED` execution mode.\n"
                    f"* **Quant Action:** Scalp orders enabled for liquid pairs with 24h volume > $5M USDT."
                )
            else:
                text = (
                    f"### 🤖 AlgoTrade PRO Quant Sentinel\n"
                    f"Engine is active. Portfolio Equity: `${bal:.2f} USDT`, Win Rate: `{wr:.1f}%`.\n\n"
                    f"Ask me about: **Market status**, **BTC Trend**, **Risk rules**, or **Trade rationale**.\n\n"
                    f"*(💡 Add your Gemini API key in Settings for full LLM generative reasoning)*"
                )

        return {
            "status": "success",
            "source": "local-quant-engine",
            "reply": text
        }
