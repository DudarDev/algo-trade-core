import logging
import asyncio
from typing import Dict, List, Any, Optional

from src.shared.config import Settings

try:
    from bot_monitor.models import Wallet, ActivePosition
except Exception:
    try:
        from src.bot_monitor.models import Wallet, ActivePosition
    except Exception:
        Wallet = None
        ActivePosition = None

from src.engine.infrastructure.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Мультивалютний менеджер капіталу та оптимізатор біржових комісій (BNB Fee Optimizer).
    
    Можливості:
    1. Облік мультивалютних балансів (USDT, BTC, ETH, SOL, BNB тощо).
    2. Конвертація всього портфеля у базову валюту (USDT) за живими котируваннями.
    3. Розрахунок процентного розподілу активів (Asset Allocation).
    4. BNB Fee Optimizer: перевірка утримання BNB для автоматичної 25% знижки на комісіях Binance
       (зниження з 0.100% до 0.075%, що безпосередньо підвищує Net PnL та вінрейт).
    """

    def __init__(self, settings: Optional[Settings] = None, exchange_manager: Optional[ExchangeManager] = None):
        self.settings = settings or Settings()
        self.exchange_manager = exchange_manager

    async def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Повертає повний стан капіталу, розподіл монет та статус BNB-оптимізатора.
        """
        free_usdt = 1000.0
        try:
            w = Wallet.objects.first()
            if w:
                free_usdt = float(w.usdt_balance)
        except Exception:
            pass

        assets: List[Dict[str, Any]] = [
            {
                "asset": "USDT",
                "amount": round(free_usdt, 2),
                "value_usdt": round(free_usdt, 2),
                "is_cash": True
            }
        ]

        # Отримуємо відкриті позиції з БД
        open_positions = []
        try:
            open_positions = list(ActivePosition.objects.all())
        except Exception:
            open_positions = []

        total_crypto_value = 0.0
        for pos in open_positions:
            coin = pos.symbol.split('/')[0]
            curr_price = pos.entry_price
            if self.exchange_manager:
                try:
                    p = await self.exchange_manager.fetch_current_price(pos.symbol)
                    if p and p > 0:
                        curr_price = p
                except Exception:
                    pass

            val_usdt = float(pos.amount * curr_price)
            total_crypto_value += val_usdt
            assets.append({
                "asset": coin,
                "symbol": pos.symbol,
                "amount": round(pos.amount, 4),
                "current_price": round(curr_price, 4),
                "value_usdt": round(val_usdt, 2),
                "is_cash": False
            })

        # Перевірка біржового балансу BNB при наявності приватного клієнта
        bnb_balance = 0.0
        bnb_price = 600.0
        if self.exchange_manager and self.exchange_manager.private_exchange:
            try:
                bals = await self.exchange_manager.private_exchange.fetch_balance()
                bnb_balance = float(bals.get('free', {}).get('BNB', 0.0))
            except Exception as e:
                logger.debug(f"Не вдалося отримати баланс BNB з API: {e}")

        if self.exchange_manager:
            try:
                bp = await self.exchange_manager.fetch_current_price("BNB/USDT")
                if bp and bp > 0:
                    bnb_price = bp
            except Exception:
                pass

        bnb_value_usdt = bnb_balance * bnb_price
        if bnb_balance > 0:
            assets.append({
                "asset": "BNB",
                "symbol": "BNB/USDT",
                "amount": round(bnb_balance, 4),
                "current_price": round(bnb_price, 2),
                "value_usdt": round(bnb_value_usdt, 2),
                "is_cash": False
            })

        total_portfolio_usdt = free_usdt + total_crypto_value + bnb_value_usdt

        # Розраховуємо % частку кожного активу
        for a in assets:
            a["allocation_pct"] = round((a["value_usdt"] / max(total_portfolio_usdt, 1.0)) * 100.0, 1)

        # BNB Fee Discount Optimizer Logic
        has_bnb_discount = (bnb_value_usdt >= 5.0)
        optimizer_info = {
            "bnb_balance": round(bnb_balance, 4),
            "bnb_value_usdt": round(bnb_value_usdt, 2),
            "discount_active": has_bnb_discount,
            "current_fee_rate_pct": 0.075 if has_bnb_discount else 0.100,
            "savings_pct": 25.0 if has_bnb_discount else 0.0,
            "status_message": (
                "✅ 25% VIP-знижка на комісіях Binance АКТИВНА (0.075% замість 0.100%)"
                if has_bnb_discount else
                "⚠️ Рекомендація: поповніть ≥ 5 USDT в BNB для активації 25% знижки на комісіях біржі!"
            )
        }

        return {
            "total_portfolio_usdt": round(total_portfolio_usdt, 2),
            "free_cash_usdt": round(free_usdt, 2),
            "allocated_crypto_usdt": round(total_crypto_value, 2),
            "assets_count": len(assets),
            "assets": assets,
            "bnb_optimizer": optimizer_info
        }
