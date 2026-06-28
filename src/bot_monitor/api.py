from ninja import Router
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from django.db.models import Sum, Avg

from .models import Trade, Wallet, ActivePosition

router = Router()

# --- СХЕМИ PYDANTIC ---

class TradeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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


# --- ЕНДПОІНТИ API ---

@router.get("/ping")
def ping(request):
    return {"status": "ok"}


@router.get("/status")
def bot_status(request):
    # Повертаємо статус running, щоб фронтенд малював зелену кнопку ACTIVE
    return {"status": "running"}


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
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    avg_win = all_trades.filter(pnl__gt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0
    avg_loss = all_trades.filter(pnl__lt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0
    
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else (999.0 if avg_win > 0 else 0.0)
    
    # --- РОЗРАХУНОК РЕАЛЬНОГО КАПІТАЛУ (TOTAL EQUITY) ---
    wallet = Wallet.objects.first()
    free_balance = wallet.usdt_balance if wallet else 0.0
    
    # Додаємо гроші, які зараз "заморожені" в активних угодах
    active_positions = ActivePosition.objects.all()
    locked_balance = sum(pos.amount for pos in active_positions)
    
    total_equity = free_balance + locked_balance
    
    return {
        "total_pnl": round(total_pnl, 2),
        "total_trades": total_trades,
        "profit_factor": round(profit_factor, 2),
        "win_rate": round(win_rate, 1),
        "balance": round(total_equity, 2),
        "error": None
    }


@router.get("/recent_trades", response=List[TradeSchema])
def get_recent_trades(request):
    """Отримання останніх 50 угод для таблиці історії (залізобетонний метод)"""
    trades_qs = Trade.objects.order_by('-timestamp')[:50]
    
    trades_list = []
    for t in trades_qs:
        trades_list.append({
            "symbol": t.symbol,
            "side": t.side,
            "price": float(t.price),
            "amount": float(t.amount),
            "pnl": float(t.pnl) if t.pnl else 0.0,
            "timestamp": t.timestamp
        })
        
    return trades_list