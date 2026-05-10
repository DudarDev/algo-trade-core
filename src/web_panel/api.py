from typing import List
from ninja import Router
from .models import Trade, Wallet
from .schemas import TradeSchema, WalletSchema

# Створюємо роутер для нашого додатку
router = Router()

@router.get("/wallet", response=WalletSchema)
def get_wallet(request):
    """Повертає поточний баланс гаманця"""
    wallet = Wallet.objects.first()
    if not wallet:
        return {"usdt_balance": 0.0}
    return wallet

@router.get("/trades", response=List[TradeSchema])
def get_recent_trades(request, limit: int = 10):
    """Повертає останні закриті угоди (за замовчуванням 10)"""
    return Trade.objects.order_by("-timestamp")[:limit]

# Заглушка для майбутньої кнопки "Зупинити/Запустити бота"
@router.post("/toggle")
def toggle_bot(request):
    """Екстрена зупинка або запуск торгового алгоритму"""
    # ТУТ БУДЕ ЛОГІКА ЗВ'ЯЗКУ З ENGINE
    return {"status": "success", "bot_active": True}