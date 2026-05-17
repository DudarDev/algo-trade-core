import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List
from pydantic import BaseModel
from django.db import transaction
from .models import Trade, Wallet, BotConfig

logger = logging.getLogger(__name__)

# --- DTO для Дашборду ---
class DashboardMetricsDTO(BaseModel):
    balance: float
    total_trades: int
    win_rate: float
    profit_factor: float
    pf_color: str
    total_pnl_usd: float
    total_pnl_percent: float
    max_drawdown: float
    risk_reward: float
    avg_win: float
    avg_loss: float
    chart_labels: List[str]
    chart_data: List[float]
    chart_colors: List[str]


class BotControlService:
    @staticmethod
    def get_current_status() -> str:
        try:
            config = BotConfig.objects.first() # Безпечніше, ніж хардкод id=1
            return config.status if config else 'stopped'
        except Exception as e:
            logger.error(f"DB Error fetching status: {e}")
            return "active"

    @staticmethod
    @transaction.atomic
    def change_status(command: Literal['start', 'stop']) -> str:
        target_status = "active" if command == "start" else "stopped"
        
        # Get the first config or create one if table is empty
        config = BotConfig.objects.select_for_update().first()
        if not config:
            config = BotConfig.objects.create(status='stopped')

        if config.status != target_status:
            config.status = target_status
            config.save(update_fields=['status'])
            logger.info(f"Bot state changed to '{target_status}'")
            
        return target_status


class MetricsCalculatorService:
    INITIAL_BALANCE = 1000.0

    @classmethod
    def get_dashboard_data(cls) -> DashboardMetricsDTO:
        wallet = Wallet.objects.first()
        balance = wallet.usdt_balance if wallet else cls.INITIAL_BALANCE

        trades_qs = Trade.objects.all().order_by('timestamp') # Одразу сортуємо в БД (швидше)
        trades_data = list(trades_qs.values('timestamp', 'symbol', 'side', 'price', 'amount', 'pnl'))

        # Базовий порожній DTO
        default_metrics = DashboardMetricsDTO(
            balance=round(balance, 2), total_trades=0, win_rate=0.0, profit_factor=0.0,
            pf_color='#FF3D00', total_pnl_usd=0.0, total_pnl_percent=0.0, max_drawdown=0.0,
            risk_reward=0.0, avg_win=0.0, avg_loss=0.0, chart_labels=[], chart_data=[], chart_colors=[]
        )

        if not trades_data:
            return default_metrics

        df = pd.DataFrame(trades_data)
        
        # Фільтруємо лише закриті угоди
        closed_trades = df[df['side'] == 'SELL'].copy()
        if closed_trades.empty:
            return default_metrics

        total_closed = len(closed_trades)
        
        # --- ВЕКТОРИЗАЦІЯ (Без iterrows!) ---
        # Припускаємо, що pnl в базі — це відсотки (напр. 5.5 = 5.5%)
        closed_trades['trade_value'] = closed_trades['amount'].astype(float) * closed_trades['price'].astype(float)
        closed_trades['profit_usd'] = closed_trades['trade_value'] * (closed_trades['pnl'].astype(float) / 100.0)
        
        # Симуляція еквіті
        closed_trades['equity'] = cls.INITIAL_BALANCE + closed_trades['profit_usd'].cumsum()
        
        # Метрики виграшів/програшів
        wins = closed_trades[closed_trades['profit_usd'] > 0]
        losses = closed_trades[closed_trades['profit_usd'] <= 0]
        
        gross_profit = wins['profit_usd'].sum()
        gross_loss = abs(losses['profit_usd'].sum())
        
        avg_win = wins['profit_usd'].mean() if not wins.empty else 0.0
        avg_loss = losses['profit_usd'].mean() if not losses.empty else 0.0
        
        # Risk / Reward
        rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else (avg_win if avg_win > 0 else 0)
        
        # Drawdown 
        running_max = closed_trades['equity'].cummax()
        drawdown = (closed_trades['equity'] - running_max) / running_max
        max_drawdown = abs(drawdown.min() * 100)

        # Profit Factor
        profit_factor = (gross_profit / gross_loss) if gross_loss != 0 else gross_profit
        pf_color = '#00C853' if profit_factor >= 1.5 else ('#FFD600' if profit_factor >= 1.1 else '#FF3D00')

        # Формування графіку
        chart_labels = closed_trades['timestamp'].dt.strftime("%d %b %H:%M").tolist()
        chart_data = closed_trades['equity'].round(2).tolist()
        chart_colors = np.where(closed_trades['profit_usd'] > 0, '#00C853', '#FF3D00').tolist()

        return DashboardMetricsDTO(
            balance=round(balance, 2),
            total_trades=total_closed,
            win_rate=round((len(wins) / total_closed) * 100, 1),
            profit_factor=round(profit_factor, 2),
            pf_color=pf_color,
            total_pnl_usd=round(gross_profit - gross_loss, 2),
            total_pnl_percent=round(((gross_profit - gross_loss) / cls.INITIAL_BALANCE) * 100, 2),
            max_drawdown=round(max_drawdown, 2),
            risk_reward=round(rr_ratio, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            chart_labels=chart_labels,
            chart_data=chart_data,
            chart_colors=chart_colors
        )