import asyncio
import logging
import urllib.request
import json
from typing import Optional
from src.shared.config import settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Асинхронний та синхронний диспетчер сповіщень Telegram."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or (settings.TELEGRAM_BOT_TOKEN.get_secret_value() if hasattr(settings.TELEGRAM_BOT_TOKEN, 'get_secret_value') else str(settings.TELEGRAM_BOT_TOKEN or ""))
        self.chat_id = chat_id or str(getattr(settings, 'TELEGRAM_CHAT_ID', '') or '')
        self.enabled = bool(getattr(settings, 'ENABLE_TELEGRAM', False) and self.token and self.chat_id)

    def _sync_post(self, text: str) -> None:
        if not self.enabled or not self.token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
        except Exception as e:
            logger.debug(f"Telegram send error: {e}")

    async def send_message(self, text: str) -> None:
        if not self.enabled or not self.token or not self.chat_id:
            return
        await asyncio.to_thread(self._sync_post, text)

    def notify_trade_open(self, symbol: str, entry_price: float, size_usdt: float, regime: str, conf: float) -> None:
        """Сповіщення про відкриття позиції."""
        if not self.enabled:
            return
        text = (
            f"🚀 <b>[ВХІД У ПОЗИЦІЮ]</b> #{symbol}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Ціна входу:</b> <code>${entry_price:,.4f}</code>\n"
            f"📦 <b>Об'єм:</b> <code>${size_usdt:,.2f} USDT</code>\n"
            f"🧭 <b>Режим:</b> <code>{regime}</code>\n"
            f"🤖 <b>ШІ впевненість:</b> <code>{conf:.2f}</code>\n"
            f"🛡️ <b>Захист:</b> Trailing Profit Ladder активний"
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_message(text))
        except RuntimeError:
            self._sync_post(text)

    def notify_trade_close(self, symbol: str, exit_price: float, net_pnl: float, pnl_pct: float, reason: str) -> None:
        """Сповіщення про закриття позиції."""
        if not self.enabled:
            return
        emoji = "🟢" if net_pnl >= 0 else "🔴"
        tag = "ПРИБУТОК" if net_pnl >= 0 else "СТОП-ЛОСС"
        text = (
            f"{emoji} <b>[ВИХІД: {tag}]</b> #{symbol}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💵 <b>Ціна виходу:</b> <code>${exit_price:,.4f}</code>\n"
            f"📊 <b>Чистий PnL:</b> <b>{net_pnl:+.2f} USDT</b> (<code>{pnl_pct:+.2f}%</code>)\n"
            f"🎯 <b>Причина:</b> <code>{reason}</code>"
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_message(text))
        except RuntimeError:
            self._sync_post(text)

    def notify_arbitrage_opportunity(self, symbol: str, route: str, gross_pct: float, net_pct: float, best_buy: str, buy_price: float, best_sell: str, sell_price: float) -> None:
        """Сповіщення про виявлене арбітражне вікно."""
        if not self.enabled:
            return
        text = (
            f"⚡ <b>[АРБІТРАЖНЕ ВІКНО: {net_pct:+.2f}% NET]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>Пара:</b> <code>{symbol}</code>\n"
            f"🔄 <b>Маршрут:</b> <b>{route}</b>\n"
            f"🛒 <b>Купівля:</b> {best_buy} @ <code>${buy_price:,.4f}</code>\n"
            f"🏷️ <b>Продаж:</b> {best_sell} @ <code>${sell_price:,.4f}</code>\n"
            f"📈 <b>Gross спред:</b> <code>{gross_pct:+.2f}%</code>\n"
            f"💰 <b>Net прибуток:</b> <b>{net_pct:+.2f}%</b>"
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_message(text))
        except RuntimeError:
            self._sync_post(text)

    def notify_funding_opportunity(self, symbol: str, delta_neutral_apy: float, binance_rate: float, bybit_rate: float) -> None:
        """Сповіщення про дохідність дельта-нейтрального фандингу."""
        if not self.enabled:
            return
        text = (
            f"💰 <b>[АРБІТРАЖ ФАНДИНГУ: {delta_neutral_apy:.1f}% APY]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 <b>Пара:</b> <code>{symbol}</code>\n"
            f"🏦 <b>Binance 8h:</b> <code>{binance_rate*100:+.4f}%</code>\n"
            f"🏛️ <b>Bybit 8h:</b> <code>{bybit_rate*100:+.4f}%</code>\n"
            f"🛡️ <b>Стратегія:</b> Long Spot + Short Futures (0 ризик ціни)\n"
            f"💵 <b>Річна дохідність:</b> <b>+{delta_neutral_apy:.1f}% APY</b>"
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_message(text))
        except RuntimeError:
            self._sync_post(text)
