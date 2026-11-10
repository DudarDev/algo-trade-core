import os
import sys
from pathlib import Path

# Add project root and src to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_panel.settings")

try:
    import django
    django.setup()
    from bot_monitor.models import Trade, SystemState
    
    trades = list(Trade.objects.filter(side="SELL").order_by("timestamp"))
    total_trades = len(trades)
    print(f"=== TRADE JOURNAL AUDIT ({total_trades} TRADES) ===")
    
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    evens = [t for t in trades if t.pnl == 0]
    
    total_win_amt = sum(t.pnl for t in wins)
    total_loss_amt = abs(sum(t.pnl for t in losses))
    net_pnl = total_win_amt - total_loss_amt
    win_rate = (len(wins) / total_trades * 100) if total_trades else 0
    profit_factor = (total_win_amt / total_loss_amt) if total_loss_amt > 0 else 0
    
    print(f"Win Rate: {win_rate:.1f}% ({len(wins)}W / {len(losses)}L / {len(evens)}BE)")
    print(f"Gross Profits: +${total_win_amt:.2f} | Gross Losses: -${total_loss_amt:.2f} | Net PnL: {net_pnl:+.2f}")
    print(f"Profit Factor: {profit_factor:.2f}")
    if wins:
        print(f"Avg Win: +${total_win_amt/len(wins):.2f}")
    if losses:
        print(f"Avg Loss: -${total_loss_amt/len(losses):.2f}")
        
    # By symbol
    by_sym = {}
    for t in trades:
        s = t.symbol
        if s not in by_sym:
            by_sym[s] = {"count": 0, "pnl": 0.0, "wins": 0, "losses": 0}
        by_sym[s]["count"] += 1
        by_sym[s]["pnl"] += t.pnl
        if t.pnl > 0:
            by_sym[s]["wins"] += 1
        elif t.pnl < 0:
            by_sym[s]["losses"] += 1
            
    print("\n--- PERFORMANCE BY SYMBOL (WORST FIRST) ---")
    sorted_syms = sorted(by_sym.items(), key=lambda x: x[1]["pnl"])
    for sym, data in sorted_syms:
        print(f"{sym:<10} PnL: {data['pnl']:+6.2f} USDT | {data['wins']}W / {data['losses']}L (Total: {data['count']})")
        
    # By exit reason
    reasons = {}
    for t in trades:
        r = getattr(t, 'exit_reason', 'unknown') or 'unknown'
        reasons[r] = reasons.get(r, 0) + 1
    print("\n--- EXIT REASONS ---")
    for r, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"{r}: {count}")

except Exception as e:
    print(f"Error during audit: {e}", file=sys.stderr)
