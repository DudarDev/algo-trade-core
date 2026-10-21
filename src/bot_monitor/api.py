import os
import json
import csv
import io
from pathlib import Path
from ninja import Router
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict
from django.db.models import Sum, Avg
from django.http import HttpResponse

from .models import Trade, Wallet, ActivePosition
from .services import BotControlService

router = Router()
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data_storage"

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
    free_cash: float = 0.0
    locked_cash: float = 0.0
    winning_trades: int = 0
    losing_trades: int = 0
    error: Optional[str] = None

class BotControlRequest(BaseModel):
    command: str

class ActivePositionSchema(BaseModel):
    symbol: str
    amount: float
    entry_price: float
    highest_price: float
    cost: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    opened_at: Optional[str] = None

class ClosePositionRequest(BaseModel):
    symbol: str

class ConfigUpdateRequest(BaseModel):
    confidence_threshold: float = 0.30
    risk_reward_ratio: float = 1.5
    max_positions: int = 3
    trade_fraction: float = 0.04
    min_adx_trend: float = 25.0

# --- ЕНДПОІНТИ API ---

@router.get("/ping")
def ping(request):
    return {"status": "ok"}


@router.get("/status")
def bot_status(request):
    status = BotControlService.get_current_status()
    return {"status": status, "bot_status": status}


@router.post("/bot_control")
@router.post("/control")
def bot_control(request, payload: BotControlRequest):
    if payload.command not in ['start', 'stop']:
        return {"status": "error", "message": "Invalid command"}
    new_status = BotControlService.change_status(payload.command)
    return {"status": "success", "bot_status": new_status}


@router.get("/stats", response=StatsSchema)
def get_stats(request):
    wallet = Wallet.objects.first()
    free_balance = wallet.usdt_balance if wallet else 1000.0
    active_positions = ActivePosition.objects.all()
    locked_balance = sum((pos.amount * pos.entry_price) for pos in active_positions)
    total_equity = free_balance + locked_balance

    all_trades = Trade.objects.all()
    total_trades = all_trades.count()
    
    if total_trades == 0:
        return {
            "total_pnl": 0.0,
            "total_trades": 0,
            "profit_factor": 0.0, 
            "win_rate": 0.0,
            "balance": round(total_equity, 2),
            "free_cash": round(free_balance, 2),
            "locked_cash": round(locked_balance, 2),
            "winning_trades": 0,
            "losing_trades": 0,
            "error": "No trades found yet."
        }
        
    winning_trades = all_trades.filter(pnl__gt=0).count()
    losing_trades = all_trades.filter(pnl__lt=0).count()
    
    total_pnl = all_trades.aggregate(total=Sum('pnl'))['total'] or 0.0
    win_rate = (winning_trades / total_trades * 100)
    
    avg_win = all_trades.filter(pnl__gt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0
    avg_loss = all_trades.filter(pnl__lt=0).aggregate(avg=Avg('pnl'))['avg'] or 0.0
    
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else (999.0 if avg_win > 0 else 0.0)
    
    return {
        "total_pnl": round(total_pnl, 2),
        "total_trades": total_trades,
        "profit_factor": round(profit_factor, 2),
        "win_rate": round(win_rate, 1),
        "balance": round(total_equity, 2),
        "free_cash": round(free_balance, 2),
        "locked_cash": round(locked_balance, 2),
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
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


@router.get("/active_positions", response=List[ActivePositionSchema])
def get_active_positions(request):
    """Отримання списку відкритих позицій з розрахунком плаваючого PnL у реальному часі."""
    positions_qs = ActivePosition.objects.all()
    
    # Спробуємо підтягнути актуальні ціни з market_radar.json
    radar_prices = {}
    radar_file = DATA_DIR / "market_radar.json"
    if radar_file.exists():
        try:
            with open(radar_file, "r", encoding="utf-8") as f:
                radar_list = json.load(f)
                for item in radar_list:
                    radar_prices[item.get("symbol")] = float(item.get("price", 0.0))
        except Exception:
            pass

    result = []
    for pos in positions_qs:
        curr_price = radar_prices.get(pos.symbol, float(pos.highest_price or pos.entry_price))
        entry_price = float(pos.entry_price)
        amount = float(pos.amount)
        cost = float(pos.cost)
        
        unrealized_pnl = (curr_price - entry_price) * amount if entry_price > 0 else 0.0
        unrealized_pnl_pct = ((curr_price - entry_price) / entry_price * 100.0) if entry_price > 0 else 0.0

        opened_str = pos.opened_at.strftime("%d.%m %H:%M") if pos.opened_at else ""

        result.append({
            "symbol": pos.symbol,
            "amount": amount,
            "entry_price": round(entry_price, 4),
            "highest_price": round(float(pos.highest_price), 4),
            "cost": round(cost, 2),
            "current_price": round(curr_price, 4),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            "opened_at": opened_str
        })
    return result


@router.post("/close_position")
def close_position(request, payload: ClosePositionRequest):
    """Ручне закриття обраної відкритої позиції з дашборду."""
    cmd_file = DATA_DIR / "command_queue.json"
    try:
        with open(cmd_file, "w", encoding="utf-8") as f:
            json.dump({"action": "close_position", "symbol": payload.symbol}, f)
        return {"status": "success", "message": f"Команду закриття {payload.symbol} надіслано рушію"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/close_all")
def close_all_positions(request):
    """Екстрене закриття ВСІХ відкритих позицій (Panic Exit)."""
    cmd_file = DATA_DIR / "command_queue.json"
    try:
        with open(cmd_file, "w", encoding="utf-8") as f:
            json.dump({"action": "close_all"}, f)
        return {"status": "success", "message": "Команду екстреного закриття всіх позицій надіслано рушію"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/market_scanner")
def get_market_scanner(request):
    """Отримання живих результатів сканування 20 пар, рішень ШІ та режимів ринку."""
    radar_file = DATA_DIR / "market_radar.json"
    if radar_file.exists():
        try:
            with open(radar_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


@router.get("/config")
def get_config(request):
    """Отримання поточних налаштувань алгоритму."""
    cfg_file = DATA_DIR / "runtime_config.json"
    default_cfg = {
        "confidence_threshold": 0.30,
        "risk_reward_ratio": 1.5,
        "max_positions": 3,
        "trade_fraction": 0.04,
        "min_adx_trend": 25.0
    }
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_cfg.update(saved)
        except Exception:
            pass
    return default_cfg


@router.post("/config")
def update_config(request, payload: ConfigUpdateRequest):
    """Збереження оновлених налаштувань алгоритму на льоту."""
    cfg_file = DATA_DIR / "runtime_config.json"
    cfg_dict = payload.model_dump()
    try:
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f, indent=2)
        return {"status": "success", "message": "Налаштування успішно збережено та застосовано", "config": cfg_dict}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/engine_logs")
def get_engine_logs(request):
    """Отримання останніх 80 рядків реальних логів рушія."""
    log_file = DATA_DIR / "engine.log"
    if not log_file.exists():
        return {"logs": ["Лог-файл ініціалізується..."]}
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            tail = [line.strip() for line in lines[-80:] if line.strip()]
            return {"logs": tail}
    except Exception as e:
        return {"logs": [f"Помилка читання логів: {e}"]}


@router.post("/reset_account")
def reset_account(request):
    """Скидання демо-депозиту до $1,000 та очищення історії для нового тестування."""
    try:
        Trade.objects.all().delete()
        ActivePosition.objects.all().delete()
        Wallet.objects.update_or_create(id=1, defaults={"usdt_balance": 1000.0})
        return {"status": "success", "message": "Баланс успішно скинуто до 1,000 USDT"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/export_trades_csv")
def export_trades_csv(request):
    """Експорт історії виконаних угод у CSV-файл."""
    trades = Trade.objects.order_by("-timestamp")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "Symbol", "Side", "Price", "Amount", "Cost_USDT", "PnL_USDT"])
    for t in trades:
        writer.writerow([t.id, t.timestamp, t.symbol, t.side, t.price, t.amount, t.cost, t.pnl])
    
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="trades_history.csv"'
    return response