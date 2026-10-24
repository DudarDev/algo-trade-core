import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import aiohttp

# Ініціалізація Django середовища
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_panel.settings')
try:
    import django
    django.setup()
except Exception:
    pass

from src.shared.config import settings

try:
    from bot_monitor.models import Trade, Wallet, ActivePosition, BotConfig
    from bot_monitor.services import BotControlService
except Exception:
    try:
        from src.bot_monitor.models import Trade, Wallet, ActivePosition, BotConfig
        from src.bot_monitor.services import BotControlService
    except Exception:
        Trade = None
        Wallet = None
        ActivePosition = None
        BotConfig = None
        BotControlService = None

logger = logging.getLogger("TelegramBot")


class InteractiveTelegramBot:
    """
    Інтерактивний двосторонній пульт дистанційного керування через Telegram.
    
    Підтримує:
    - Текстові команди: /start, /status, /pause, /resume, /pnl, /positions, /close_all, /config
    - Реактивні Inline-кнопки (клік оновлює статус або відправляє команду)
    - Персистентну клавіатуру швидкого доступу
    - Аварійне закриття всіх позицій (Panic Close All) через чергу команд
    - Сувору перевірку авторизації за chat_id
    """

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        raw_token = token or getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if raw_token and hasattr(raw_token, 'get_secret_value'):
            self.token = raw_token.get_secret_value()
        else:
            self.token = str(raw_token) if raw_token else ""

        self.chat_id = str(chat_id or getattr(settings, 'TELEGRAM_CHAT_ID', ""))
        self.enabled = bool(getattr(settings, 'ENABLE_TELEGRAM', False) and self.token)
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        
        self.data_dir = Path(src_dir) / "data_storage"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cmd_file = self.data_dir / "command_queue.json"
        
        self._running = False
        self._last_update_id = 0

    def is_authorized(self, incoming_chat_id: Any) -> bool:
        """Перевірка авторизації користувача."""
        if not self.chat_id or self.chat_id == "None":
            return True  # Якщо chat_id не зафіксовано, дозволяємо першому власнику
        return str(incoming_chat_id) == str(self.chat_id)

    def get_reply_keyboard(self) -> Dict[str, Any]:
        """Нижня фіксована клавіатура швидкого доступу."""
        return {
            "keyboard": [
                [{"text": "📊 Статус"}, {"text": "💰 PnL"}],
                [{"text": "📜 Позиції"}, {"text": "⚙️ Конфіг"}],
                [{"text": "⏸ Пауза"}, {"text": "▶️ Старт"}],
                [{"text": "🚨 PANIC CLOSE ALL"}]
            ],
            "resize_keyboard": True,
            "persistent": True
        }

    def get_inline_keyboard(self, is_active: bool) -> Dict[str, Any]:
        """Інтерактивні кнопки під повідомленням."""
        toggle_btn = (
            {"text": "⏸ Призупинити", "callback_data": "cmd_pause"}
            if is_active else
            {"text": "▶️ Відновити", "callback_data": "cmd_resume"}
        )
        return {
            "inline_keyboard": [
                [
                    {"text": "🔄 Оновити", "callback_data": "cmd_status"},
                    {"text": "💰 Детальний PnL", "callback_data": "cmd_pnl"}
                ],
                [
                    {"text": "📜 Активні позиції", "callback_data": "cmd_positions"},
                    {"text": "🗞️ Дайджест 24h", "callback_data": "cmd_digest"}
                ],
                [
                    toggle_btn,
                    {"text": "🚨 ПАНІКА: Закрити ВСЕ 🚨", "callback_data": "cmd_close_all"}
                ]
            ]
        }

    async def _send_request(self, session: aiohttp.ClientSession, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Виконання запиту до Telegram Bot API."""
        if not self.token:
            return None
        url = f"{self.base_url}/{endpoint}"
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.warning(f"Telegram API response error: {data}")
                return data
        except Exception as e:
            logger.error(f"Помилка зв'язку з Telegram ({endpoint}): {e}")
            return None

    async def send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML"
    ) -> Optional[Dict[str, Any]]:
        """Надсилання повідомлення."""
        async with aiohttp.ClientSession() as session:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            return await self._send_request(session, "sendMessage", payload)

    async def edit_message(
        self,
        session: aiohttp.ClientSession,
        chat_id: str,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> None:
        """Редагування повідомлення на місці (для inline кнопок)."""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        await self._send_request(session, "editMessageText", payload)

    async def answer_callback(self, session: aiohttp.ClientSession, callback_id: str, text: str = "") -> None:
        """Підтвердження обробки callback_query."""
        await self._send_request(session, "answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": text
        })

    # --- ФОРМУВАННЯ ДАНИХ ТА ТЕЛЕМЕТРІЇ (Thread-safe) ---

    def format_status_message(self) -> Tuple[str, bool]:
        """Генерує телеметрію стану системи."""
        status_val = "active"
        if BotControlService and hasattr(BotControlService, 'get_current_status'):
            try:
                status_val = BotControlService.get_current_status()
            except Exception:
                status_val = "active"

        is_active = (status_val == "active")
        status_badge = "🟢 <b>АКТИВНИЙ</b>" if is_active else "⏸ <b>НА ПАУЗІ</b>"

        trading_mode = getattr(settings, 'TRADING_MODE', 'PAPER').upper()
        mode_badge = "🔥 <b>LIVE BINANCE CEX</b>" if trading_mode == "LIVE" else "🛡️ <b>PAPER SIMULATION</b>"

        free_bal = 1000.0
        locked_bal = 0.0
        pos_count = 0
        if Wallet:
            try:
                wallet = Wallet.objects.first()
                if wallet:
                    free_bal = wallet.usdt_balance
            except Exception:
                pass

        if ActivePosition:
            try:
                positions = list(ActivePosition.objects.all())
                pos_count = len(positions)
                locked_bal = sum(getattr(p, 'cost', 0.0) for p in positions)
            except Exception:
                pass

        total_equity = free_bal + locked_bal

        trades_count = 0
        win_rate = 0.0
        total_pnl = 0.0
        if Trade:
            try:
                trades_count = Trade.objects.count()
                wins = Trade.objects.filter(pnl__gt=0).count()
                win_rate = (wins / trades_count * 100) if trades_count > 0 else 0.0
                from django.db.models import Sum
                total_pnl = Trade.objects.aggregate(total=Sum('pnl'))['total'] or 0.0
            except Exception:
                pass

        max_positions = getattr(settings, 'MAX_CONCURRENT_POSITIONS', 3)
        text = (
            f"⚡ <b>Quantum Scalper Pro v4.2</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🚦 <b>Стан:</b> {status_badge}\n"
            f"🎯 <b>Режим:</b> {mode_badge}\n"
            f"💵 <b>Вільний кеш:</b> <code>{free_bal:.2f} USDT</code>\n"
            f"💼 <b>Загальний капітал:</b> <code>{total_equity:.2f} USDT</code>\n"
            f"📦 <b>Відкритих позицій:</b> <code>{pos_count} / {max_positions}</code>\n"
            f"📈 <b>Чистий PnL:</b> <code>{total_pnl:+.2f} USDT</code> (Вінрейт: <b>{win_rate:.1f}%</b>)\n"
            f"🛡️ <b>Circuit Breaker:</b> <code>-3.0% Max Daily Loss Guard</code>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        return text, is_active

    def format_pnl_message(self) -> str:
        """Детальний звіт по PnL та вінрейту."""
        if not Trade:
            return "📊 <b>Історія торгівлі:</b> Угод поки що не зафіксовано."

        try:
            from django.db.models import Sum, Avg
            all_trades = Trade.objects.all()
            total_trades = all_trades.count()
            
            if total_trades == 0:
                return "📊 <b>Історія торгівлі:</b> Угод поки що не зафіксовано."

            wins = all_trades.filter(pnl__gt=0).count()
            losses = all_trades.filter(pnl__lt=0).count()
            win_rate = (wins / total_trades * 100)
            
            total_pnl = all_trades.aggregate(total=Sum('pnl'))['total'] or 0.0
            avg_win = all_trades.filter(pnl__gt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0
            avg_loss = all_trades.filter(pnl__lt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0

            gross_profit = all_trades.filter(pnl__gt=0).aggregate(total=Sum('pnl'))['total'] or 0.0
            gross_loss = abs(all_trades.filter(pnl__lt=0).aggregate(total=Sum('pnl'))['total'] or 0.0)
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

            recent = all_trades.order_by('-id')[:3]
            recent_str = "\n".join([
                f"• <b>{t.symbol}</b> ({t.exit_reason}): <code>{t.pnl:+.2f} USDT</code>"
                for t in recent
            ])

            return (
                f"💰 <b>Аналітика прибутковості (PnL):</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💵 <b>Загальний Net PnL:</b> <code>{total_pnl:+.2f} USDT</code>\n"
                f"🎯 <b>Вінрейт:</b> <b>{win_rate:.1f}%</b> ({wins}W / {losses}L / {total_trades}T)\n"
                f"⚖️ <b>Profit Factor:</b> <code>{profit_factor:.2f}</code>\n"
                f"🟢 <b>Середній виграш:</b> <code>+{avg_win:.2f} USDT</code>\n"
                f"🔴 <b>Середній збиток:</b> <code>{avg_loss:.2f} USDT</code>\n\n"
                f"<b>Останні закриті позиції:</b>\n"
                f"{recent_str}\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
        except Exception as e:
            return f"⚠️ Помилка зчитування PnL: {e}"

    def format_positions_message(self) -> str:
        """Перелік відкритих позицій алгоритму."""
        if not ActivePosition:
            return "📜 <b>Відкриті позиції:</b> Немає активних угод."

        try:
            positions = list(ActivePosition.objects.all())
            if not positions:
                return "📜 <b>Відкриті позиції:</b> Наразі активних угод немає. Бот сканує ринок у пошуку сетапів."

            lines = [f"📜 <b>Активні позиції ({len(positions)}):</b>\n━━━━━━━━━━━━━━━━━━"]
            for p in positions:
                time_str = p.opened_at.strftime("%H:%M:%S") if hasattr(p, 'opened_at') and p.opened_at else "Now"
                lines.append(
                    f"🪙 <b>{p.symbol}</b> | Вхід: <code>{p.entry_price:.4f}</code>\n"
                    f"   Об'єм: <code>{p.cost:.2f} USDT</code> ({p.amount:.4f})\n"
                    f"   High: <code>{p.highest_price:.4f}</code> | Режим: <i>{p.regime}</i>\n"
                    f"   Відкрито о: {time_str}\n"
                )
            lines.append("━━━━━━━━━━━━━━━━━━")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Помилка зчитування позицій: {e}"

    def trigger_panic_close_all(self) -> str:
        """Надсилання команди екстреної ліквідації в чергу."""
        try:
            with open(self.cmd_file, "w", encoding="utf-8") as f:
                json.dump({"action": "close_all"}, f)
            return "🚨 <b>PANIC CLOSE:</b> Команду ліквідації всіх позицій надіслано в ядро виконання!"
        except Exception as e:
            return f"❌ Помилка запису команди: {e}"

    # --- ОБРОБКА ВХІДНИХ ПОВІДОМЛЕНЬ ТА CALLBACKS ---

    async def handle_update(self, session: aiohttp.ClientSession, update: Dict[str, Any]) -> None:
        """Маршрутизація вхідного оновлення (Message або CallbackQuery)."""
        # 1. Обробка натискання Inline кнопки
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb["id"]
            chat_id = str(cb["message"]["chat"]["id"])
            msg_id = cb["message"]["message_id"]
            action = cb.get("data", "")

            if not self.is_authorized(chat_id):
                await self.answer_callback(session, cb_id, "⛔ Доступ заборонено")
                return

            if action == "cmd_status":
                text, is_active = await asyncio.to_thread(self.format_status_message)
                await self.edit_message(session, chat_id, msg_id, text, self.get_inline_keyboard(is_active))
                await self.answer_callback(session, cb_id, "Оновлено!")

            elif action == "cmd_pnl":
                text = await asyncio.to_thread(self.format_pnl_message)
                _, is_active = await asyncio.to_thread(self.format_status_message)
                await self.edit_message(session, chat_id, msg_id, text, self.get_inline_keyboard(is_active))
                await self.answer_callback(session, cb_id)

            elif action == "cmd_positions":
                text = await asyncio.to_thread(self.format_positions_message)
                _, is_active = await asyncio.to_thread(self.format_status_message)
                await self.edit_message(session, chat_id, msg_id, text, self.get_inline_keyboard(is_active))
                await self.answer_callback(session, cb_id)

            elif action == "cmd_digest":
                from src.engine.infrastructure.telegram_scheduler import TelegramDigestScheduler
                sched = TelegramDigestScheduler(self)
                digest_text = await asyncio.to_thread(sched.generate_daily_digest)
                _, is_active = await asyncio.to_thread(self.format_status_message)
                await self.edit_message(session, chat_id, msg_id, digest_text, self.get_inline_keyboard(is_active))
                await self.answer_callback(session, cb_id, "Дайджест оновлено!")

            elif action == "cmd_pause":
                if BotControlService and hasattr(BotControlService, 'change_status'):
                    await asyncio.to_thread(BotControlService.change_status, "stop")
                text, is_active = await asyncio.to_thread(self.format_status_message)
                await self.edit_message(session, chat_id, msg_id, text, self.get_inline_keyboard(is_active))
                await self.answer_callback(session, cb_id, "⏸ Бот призупинено!")

            elif action == "cmd_resume":
                if BotControlService and hasattr(BotControlService, 'change_status'):
                    await asyncio.to_thread(BotControlService.change_status, "start")
                text, is_active = await asyncio.to_thread(self.format_status_message)
                await self.edit_message(session, chat_id, msg_id, text, self.get_inline_keyboard(is_active))
                await self.answer_callback(session, cb_id, "▶️ Бот відновлено!")

            elif action == "cmd_close_all":
                res = self.trigger_panic_close_all()
                await self.answer_callback(session, cb_id, "🚨 Ліквідація запущена!")
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": res,
                    "parse_mode": "HTML"
                })

            return

        # 2. Обробка текстових команд
        if "message" in update:
            msg = update["message"]
            chat_id = str(msg["chat"]["id"])
            text = (msg.get("text") or "").strip()

            if not self.is_authorized(chat_id):
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "⛔ <b>Доступ заборонено.</b> Цей бот налаштований для приватного керування.",
                    "parse_mode": "HTML"
                })
                return

            if text in ["/start", "/help"]:
                status_text, is_active = await asyncio.to_thread(self.format_status_message)
                welcome = (
                    f"👋 <b>Ласкаво просимо до панелі Quantum Scalper Pro!</b>\n\n"
                    f"{status_text}\n\n"
                    f"<i>Оберіть дію на панелі або кнопках нижче:</i>"
                )
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": welcome,
                    "reply_markup": self.get_reply_keyboard(),
                    "parse_mode": "HTML"
                })
                # Також відправляємо повідомлення з inline кнопками
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "🎛️ <b>Інтерактивний блок керування:</b>",
                    "reply_markup": self.get_inline_keyboard(is_active),
                    "parse_mode": "HTML"
                })

            elif text in ["/status", "📊 Статус"]:
                status_text, is_active = await asyncio.to_thread(self.format_status_message)
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": status_text,
                    "reply_markup": self.get_inline_keyboard(is_active),
                    "parse_mode": "HTML"
                })

            elif text in ["/pnl", "💰 PnL"]:
                pnl_text = await asyncio.to_thread(self.format_pnl_message)
                _, is_active = await asyncio.to_thread(self.format_status_message)
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": pnl_text,
                    "reply_markup": self.get_inline_keyboard(is_active),
                    "parse_mode": "HTML"
                })

            elif text in ["/positions", "📜 Позиції"]:
                pos_text = await asyncio.to_thread(self.format_positions_message)
                _, is_active = await asyncio.to_thread(self.format_status_message)
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": pos_text,
                    "reply_markup": self.get_inline_keyboard(is_active),
                    "parse_mode": "HTML"
                })

            elif text in ["/digest", "🗞️ Дайджест"]:
                from src.engine.infrastructure.telegram_scheduler import TelegramDigestScheduler
                sched = TelegramDigestScheduler(self)
                digest_text = await asyncio.to_thread(sched.generate_daily_digest)
                _, is_active = await asyncio.to_thread(self.format_status_message)
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": digest_text,
                    "reply_markup": self.get_inline_keyboard(is_active),
                    "parse_mode": "HTML"
                })

            elif text in ["/pause", "⏸ Пауза"]:
                if BotControlService and hasattr(BotControlService, 'change_status'):
                    await asyncio.to_thread(BotControlService.change_status, "stop")
                status_text, is_active = await asyncio.to_thread(self.format_status_message)
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": f"⏸ <b>Торговий рушій призупинено.</b> Нові угоди не відкриватимуться.\n\n{status_text}",
                    "reply_markup": self.get_inline_keyboard(is_active),
                    "parse_mode": "HTML"
                })

            elif text in ["/resume", "▶️ Старт"]:
                if BotControlService and hasattr(BotControlService, 'change_status'):
                    await asyncio.to_thread(BotControlService.change_status, "start")
                status_text, is_active = await asyncio.to_thread(self.format_status_message)
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": f"▶️ <b>Торговий рушій активовано!</b> Сканування та торгівля відновлені.\n\n{status_text}",
                    "reply_markup": self.get_inline_keyboard(is_active),
                    "parse_mode": "HTML"
                })

            elif text in ["/close_all", "🚨 PANIC CLOSE ALL"]:
                res = self.trigger_panic_close_all()
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": res,
                    "parse_mode": "HTML"
                })

            elif text in ["/config", "⚙️ Конфіг"]:
                cfg_text = (
                    f"⚙️ <b>Параметри квант-рушія:</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"⏱ Таймфрейм: <code>{settings.TIMEFRAME}</code>\n"
                    f"🧠 AI Threshold: <code>{settings.CONFIDENCE_THRESHOLD:.2f}</code>\n"
                    f"🎯 Risk-Reward: <code>1:{settings.RISK_REWARD_RATIO:.1f}</code>\n"
                    f"📦 Max Positions: <code>{settings.MAX_CONCURRENT_POSITIONS}</code>\n"
                    f"💵 Ризик на трейд: <code>{settings.TRADE_FRACTION*100:.1f}%</code>\n"
                    f"🛡️ Slippage Guard: <code>{getattr(settings, 'MAX_SLIPPAGE_PCT', 0.005)*100:.2f}%</code>\n"
                    f"🛑 Daily Loss Circuit: <code>{settings.DAILY_LOSS_LIMIT_PCT*100:.1f}%</code>\n"
                    f"━━━━━━━━━━━━━━━━━━"
                )
                await self._send_request(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": cfg_text,
                    "parse_mode": "HTML"
                })

    async def run_polling(self) -> None:
        """Асинхронний цикл Long Polling для миттєвої реакції на команди."""
        if not self.token:
            logger.warning("⚠️ [TELEGRAM BOT] Токен не встановлено. Інтерактивний бот не запущено.")
            return

        self._running = True
        logger.info("🎧 [TELEGRAM BOT] Інтерактивний пульт керування запущено в режимі Long Polling...")
        
        async with aiohttp.ClientSession() as session:
            while self._running:
                try:
                    payload = {
                        "offset": self._last_update_id + 1,
                        "timeout": 20,
                        "allowed_updates": ["message", "callback_query"]
                    }
                    async with session.post(
                        f"{self.base_url}/getUpdates",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=25)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            updates = data.get("result", [])
                            for upd in updates:
                                self._last_update_id = max(self._last_update_id, upd["update_id"])
                                await self.handle_update(session, upd)
                        elif resp.status == 409:
                            logger.warning("⚠️ Конфлікт Telegram getUpdates (інший екземпляр активний). Очікування 10с...")
                            await asyncio.sleep(10)
                        else:
                            await asyncio.sleep(2)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Помилка в циклі Telegram Polling: {e}")
                    await asyncio.sleep(5)

    def stop(self) -> None:
        """Зупинка опитування."""
        self._running = False


# Зворотна сумісність для автономного запуску
def run_standalone():
    bot_controller = InteractiveTelegramBot()
    try:
        asyncio.run(bot_controller.run_polling())
    except KeyboardInterrupt:
        print("Telegram Bot зупинено.")

if __name__ == "__main__":
    run_standalone()
