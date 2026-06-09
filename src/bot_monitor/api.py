from ninja import Router
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from django.db.models import Sum, Avg

from .models import Trade, Wallet, ActivePosition

router = Router()

class TradeSchema(BaseModel):
    symbol: str
    side: str
    price: float
    amount: float
    pnl: float
    timestamp: datetime

class StatsSchema(BaseModel):
    total_pnl: float
    total_trades: int
    profit_factor: float
    win_rate: float
    balance: float
    error: Optional[str] = None

@router.get("/ping")
def ping(request):
    return {"status": "ok"}

# Додаємо статус бота, який шукає JS!
@router.get("/bot_status")
def bot_status(request):
    return {"status": "active"}

@router.get("/stats", response=StatsSchema)
def get_stats(request):
    all_trades = Trade.objects.all()
    total_trades = all_trades.count()
    
    if total_trades == 0:
         return {
             "total_pnl": 0.0, "total_trades": 0, "profit_factor": 0.0, 
             "win_rate": 0.0, "balance": 0.0, "error": "No trades found yet."
         }
         
    winning_trades = all_trades.filter(pnl__gt=0).count()
    losing_trades = all_trades.filter(pnl__lt=0).count()
    
    total_pnl = all_trades.aggregate(total=Sum('pnl'))['total'] or 0.0
    win_rate = (winning_trades / total_trades * 100)
    
    avg_win = all_trades.filter(pnl__gt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0
    avg_loss = all_trades.filter(pnl__lt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0
    
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else (999.0 if avg_win > 0 else 0.0)
    
    wallet = Wallet.objects.first()
    balance = wallet.usdt_balance if wallet else 0.0
    
    return {
        "total_pnl": round(total_pnl, 2),
        "total_trades": total_trades,
        "profit_factor": round(profit_factor, 2),
        "win_rate": round(win_rate, 1),
        "balance": round(balance, 2),
        "error": None
    }

@router.get("/recent_trades", response=List[TradeSchema])
def get_recent_trades(request):
    trades = Trade.objects.order_by('-timestamp')[:50]
    return trades