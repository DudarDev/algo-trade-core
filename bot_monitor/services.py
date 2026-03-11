import pandas as pd
from typing import Dict, Any, Tuple
from .models import Trade, Wallet

class MetricsCalculatorService:
    """Сервіс для розрахунку торгових метрик (Business Logic Layer)"""
    
    INITIAL_BALANCE = 1000.0

    @staticmethod
    def _calculate_risk_metrics(trades_df: pd.DataFrame, equity_curve: list) -> Tuple[float, float, float, float]:
        max_drawdown = 0.0
        if equity_curve:
            equity_series = pd.Series(equity_curve)
            running_max = equity_series.cummax()
            drawdown = (equity_series - running_max) / running_max
            max_drawdown = drawdown.min() * 100 

        if not trades_df.empty:
            closed = trades_df[trades_df['side'] == 'SELL']
            avg_win = closed[closed['pnl'] > 0]['pnl'].mean()
            avg_loss = closed[closed['pnl'] <= 0]['pnl'].mean()
            
            avg_win = 0 if pd.isna(avg_win) else avg_win
            avg_loss = 0 if pd.isna(avg_loss) else avg_loss
        else:
            avg_win, avg_loss = 0, 0

        if abs(avg_loss) > 0:
            rr_ratio = round(avg_win / abs(avg_loss), 2)
        else:
            rr_ratio = round(avg_win, 2) if avg_win > 0 else 0

        return round(abs(max_drawdown), 2), rr_ratio, round(avg_win, 2), round(avg_loss, 2)

    def get_dashboard_data(self) -> Dict[str, Any]:
        # 1. Отримання балансу
        try:
            wallet = Wallet.objects.first()
            balance = wallet.usdt_balance if wallet else self.INITIAL_BALANCE
        except Exception: 
            balance = self.INITIAL_BALANCE

        # 2. Отримання угод
        trades_qs = Trade.objects.all().order_by('-timestamp')
        trades_data = list(trades_qs.values('timestamp', 'symbol', 'side', 'price', 'amount', 'pnl'))
        
        context = {
            'balance': round(balance, 2),
            'trades': trades_qs[:20], # Останні 20 угод для таблиці
        }

        if not trades_data:
            return context

        # 3. Обчислення через Pandas
        df = pd.DataFrame(trades_data)
        closed_trades = df[df['side'] == 'SELL']
        total_closed = len(closed_trades)
        wins_count = len(closed_trades[closed_trades['pnl'] > 0])
        
        win_rate = (wins_count / total_closed * 100) if total_closed > 0 else 0
        
        # 4. Побудова графіка Equity
        chart_labels, chart_data, chart_colors, chart_radius = [], [], [], []
        simulated_equity = self.INITIAL_BALANCE 
        gross_profit, gross_loss = 0.0, 0.0

        df_sorted = df.sort_values('timestamp')

        for _, t in df_sorted.iterrows():
            if t['side'] == 'SELL' and pd.notnull(t['pnl']):
                trade_val = float(t['amount']) * float(t['price'])
                profit_usd = trade_val * (float(t['pnl']) / 100.0)
                
                if profit_usd > 0:
                    gross_profit += profit_usd
                    point_color = '#00C853' 
                else:
                    gross_loss += abs(profit_usd)
                    point_color = '#FF3D00' 

                simulated_equity += profit_usd
                
                chart_labels.append(t['timestamp'].strftime("%d %b %H:%M"))
                chart_data.append(round(simulated_equity, 2))
                chart_colors.append(point_color)
                chart_radius.append(2) 

        # 5. Підрахунок PnL та Profit Factor
        total_pnl_usd = round(gross_profit - gross_loss, 2)
        total_pnl_percent = round((total_pnl_usd / self.INITIAL_BALANCE) * 100, 2)

        mdd, rr_ratio, avg_win, avg_loss = self._calculate_risk_metrics(df, chart_data)

        if gross_loss == 0:
            profit_factor = round(gross_profit, 2) if gross_profit > 0 else 0.0
        else:
            profit_factor = round(gross_profit / gross_loss, 2)

        pf_color = '#00C853' if profit_factor >= 1.5 else ('#FFD600' if profit_factor >= 1.1 else '#FF3D00')

        # Додаємо обчислені дані в контекст
        context.update({
            'total_trades': len(df),
            'win_rate': round(win_rate, 1),
            'profit_factor': profit_factor,
            'pf_color': pf_color,
            'total_pnl_usd': total_pnl_usd,
            'total_pnl_percent': total_pnl_percent,
            'max_drawdown': mdd,
            'risk_reward': rr_ratio,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'chart_labels': chart_labels,
            'chart_data': chart_data,
            'chart_colors': chart_colors,
            'chart_radius': chart_radius, 
        })
        
        return context