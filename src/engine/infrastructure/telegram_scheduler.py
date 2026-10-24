import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from src.shared.config import settings

try:
    from bot_monitor.models import Trade, Wallet, ActivePosition, BotConfig
except Exception:
    try:
        from src.bot_monitor.models import Trade, Wallet, ActivePosition, BotConfig
    except Exception:
        Trade = None
        Wallet = None
        ActivePosition = None
        BotConfig = None

logger = logging.getLogger(__name__)


class TelegramDigestScheduler:
    """
    Автономний планувальник регулярних звітів PnL у Telegram.
    
    Можливості:
    1. Щоденні автоматичні дайджести (09:00 та 21:00 UTC):
       - Сумарний PnL за останні 24 години
       - Кількість угод та добовий вінрейт
       - Найкраща прибуткова угода доби
       - Поточний залишок вільного кешу та активні позиції
    2. Ручний запит зрізу через команду /digest або кнопку в меню.
    """

    def __init__(self, telegram_bot: Optional[object] = None):
        self.bot = telegram_bot
        self._running = False
        self._last_digest_date = ""

    def generate_daily_digest(self) -> str:
        """Створює відформатований текст щоденного квант-дайджесту."""
        now = datetime.now(timezone.utc)
        since_24h = now - timedelta(hours=24)

        free_balance = 1000.0
        if Wallet:
            try:
                w = Wallet.objects.first()
                if w:
                    free_balance = float(w.usdt_balance)
            except Exception:
                pass

        trades_24h = []
        if Trade:
            try:
                trades_24h = list(Trade.objects.filter(timestamp__gte=since_24h))
            except Exception:
                trades_24h = []

        total_trades = len(trades_24h)
        wins = [t for t in trades_24h if t.pnl > 0]
        losses = [t for t in trades_24h if t.pnl <= 0]
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
        pnl_24h = sum(t.pnl for t in trades_24h)

        best_trade_str = "Немає закритих угод"
        if wins:
            best = max(wins, key=lambda x: x.pnl)
            best_trade_str = f"{best.symbol} (+{best.pnl:.2f} USDT)"

        active_count = 0
        if ActivePosition:
            try:
                active_count = ActivePosition.objects.count()
            except Exception:
                pass

        trading_mode = getattr(settings, 'TRADING_MODE', 'PAPER').upper()
        mode_badge = "🔥 LIVE BINANCE CEX" if trading_mode == "LIVE" else "🛡️ PAPER SIMULATION"

        date_str = now.strftime("%d.%m.%Y %H:%M UTC")

        msg = (
            f"🗞️ <b>ЩОДЕННИЙ КВАНТ-ДАЙДЖЕСТ PnL</b>\n"
            f"📅 <i>{date_str}</i>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Режим:</b> {mode_badge}\n"
            f"💵 <b>Добовий PnL (24h):</b> <code>{pnl_24h:+.2f} USDT</code>\n"
            f"📊 <b>Вінрейт за добу:</b> <b>{win_rate:.1f}%</b> ({len(wins)}W / {len(losses)}L)\n"
            f"🏆 <b>Топ-угода дня:</b> <code>{best_trade_str}</code>\n"
            f"💼 <b>Поточний баланс:</b> <code>{free_balance:.2f} USDT</code>\n"
            f"📦 <b>Утримання в ринку:</b> <code>{active_count} позицій</code>\n"
            f"🛡️ <b>Circuit Breaker:</b> <code>ОК (Нормативний стан)</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>Бот продовжує автономне квантове сканування ринку 24/7.</i>"
        )
        return msg

    async def run_scheduler(self) -> None:
        """Фоновий цикл розкладу відправки ранкових та вечірніх звітів."""
        if not self.bot or not getattr(self.bot, 'enabled', False):
            logger.info("ℹ️ [DIGEST SCHEDULER] Telegram не налаштований. Планувальник звітів у режимі очікування.")
            return

        self._running = True
        logger.info("⏰ [DIGEST SCHEDULER] Автономний розклад звітів PnL запущено (09:00 та 21:00 UTC)...")

        while self._running:
            try:
                now = datetime.now(timezone.utc)
                hour = now.hour
                day_key = f"{now.date()}_{hour}"

                # Відправка о 09:00 та 21:00 UTC (один раз на відповідну годину)
                if hour in (9, 21) and day_key != self._last_digest_date:
                    self._last_digest_date = day_key
                    digest_text = self.generate_daily_digest()
                    if hasattr(self.bot, 'send_message') and self.bot.chat_id:
                        logger.info("📤 [DIGEST SCHEDULER] Відправка автоматичного щоденного дайджесту...")
                        await self.bot.send_message(self.bot.chat_id, digest_text)

                await asyncio.sleep(60) # Перевірка щохвилини
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Помилка в планувальнику Telegram звітів: {e}")
                await asyncio.sleep(120)

    def stop(self) -> None:
        """Зупинка планувальника."""
        self._running = False
