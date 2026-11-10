"""
Demo Video Logs Generator for Fiverr Screencasts & Promo Reels.
Produces institutional-grade, cinematic colorized HFT trading logs
ideal for screen recording (VS Code Terminal, OBS Studio, CapCut).
"""
import sys
import time
import random
from datetime import datetime

# ANSI Color codes for cross-platform aesthetic terminal rendering
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

GREEN = "\033[38;5;46m"
BRIGHT_GREEN = "\033[38;5;82m"
CYAN = "\033[38;5;51m"
BLUE = "\033[38;5;39m"
PURPLE = "\033[38;5;141m"
YELLOW = "\033[38;5;220m"
ORANGE = "\033[38;5;208m"
RED = "\033[38;5;196m"
WHITE = "\033[38;5;255m"
GRAY = "\033[38;5;244m"
BG_DARK = "\033[48;5;234m"

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "AVAX/USDT", "LINK/USDT", "NEAR/USDT", "DOGE/USDT", "ADA/USDT"]
EXCHANGES = ["Binance", "Bybit", "OKX"]

def print_banner():
    print(f"\n{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{CYAN}{BOLD}║   AlgoTrade PRO v4.2  │  INSTITUTIONAL QUANTITATIVE SCALPER & ARBITRAGE CORE         ║{RESET}")
    print(f"{CYAN}{BOLD}║   Sub-20ms WebSocket Stream  │  Dual Ensemble AI (RF+LGBM)  │  Maker Fee Optimizer     ║{RESET}")
    print(f"{CYAN}{BOLD}╚══════════════════════════════════════════════════════════════════════════════════════════════╝{RESET}\n")
    time.sleep(1.0)
    print(f"{GRAY}[SYS_INIT] Loading Redis in-memory cache... {GREEN}OK (redis://127.0.0.1:6379/0){RESET}")
    time.sleep(0.3)
    print(f"{GRAY}[SYS_INIT] Initializing Dual AI Ensemble (RandomForest v4.1 + LightGBM v2.0)... {GREEN}READY{RESET}")
    time.sleep(0.3)
    print(f"{GRAY}[SYS_INIT] Connecting ultra-low latency WebSockets (Binance & Bybit Spot BBO)... {BRIGHT_GREEN}CONNECTED (<18ms){RESET}")
    time.sleep(0.3)
    print(f"{GRAY}[SYS_INIT] Execution Engine: {YELLOW}MAKER LIMIT POST-ONLY (-73.3% Exchange Fees){RESET}")
    time.sleep(0.5)
    print(f"\n{BOLD}{WHITE}>>> COMMENCING HIGH-FREQUENCY TICK STREAM & RISK ENGINE <<<{RESET}\n")
    time.sleep(0.8)

def generate_event():
    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
    sym = random.choice(SYMBOLS)
    event_type = random.choices(
        ["ws_tick", "ai_score", "maker_order", "arbitrage", "take_profit", "risk_guard", "metrics"],
        weights=[35, 20, 12, 10, 10, 8, 5]
    )[0]

    if event_type == "ws_tick":
        lat = round(random.uniform(14.2, 22.8), 1)
        bid = round(random.uniform(20.0, 75000.0), 2 if "BTC" in sym or "ETH" in sym else 4)
        ask = round(bid * 1.0001, 2 if "BTC" in sym or "ETH" in sym else 4)
        print(f"{GRAY}{ts}{RESET} {BLUE}⚡ [WS-FEED]{RESET} {sym:<9} {GRAY}BBO:{RESET} {bid} / {ask} {DIM}│{RESET} {GREEN}Ping: {lat}ms{RESET} {DIM}│ Ticks: {random.randint(110000, 125000)}{RESET}")

    elif event_type == "ai_score":
        rf_conf = round(random.uniform(0.72, 0.91), 2)
        lgbm_conf = round(random.uniform(0.74, 0.93), 2)
        ensemble = round(rf_conf * 0.55 + lgbm_conf * 0.45, 3)
        adx = round(random.uniform(28.0, 42.0), 1)
        print(f"{GRAY}{ts}{RESET} {PURPLE}🧠 [AI-ENSEMBLE]{RESET} {sym:<9} {WHITE}RF:{rf_conf} + LGBM:{lgbm_conf}{RESET} ➔ {BOLD}{GREEN}CONSENSUS BUY ({ensemble*100:.1f}%){RESET} {DIM}│ ADX: {adx} Trend Lock{RESET}")

    elif event_type == "maker_order":
        oid = random.randint(1048201, 9984920)
        px = round(random.uniform(50.0, 75000.0), 2)
        size = round(random.uniform(80.0, 150.0), 1)
        print(f"{GRAY}{ts}{RESET} {YELLOW}🚀 [ORDER-EXEC]{RESET} {BOLD}{GREEN}BUY MAKER LIMIT{RESET} #{oid} {sym} @ {px} | Vol: ${size} USDT {DIM}│{RESET} {CYAN}Fee: 0.02% (Saved $0.09){RESET}")

    elif event_type == "arbitrage":
        spr = round(random.uniform(0.52, 0.98), 2)
        net = round(spr - 0.20, 2)
        e1, e2 = random.sample(EXCHANGES, 2)
        print(f"{GRAY}{ts}{RESET} {ORANGE}📡 [ARBITRAGE]{RESET} {BOLD}{WHITE}{sym}{RESET} {e1} ➔ {e2} {DIM}│{RESET} Gross: {spr:+0.2f}% ➔ {BOLD}{BRIGHT_GREEN}NET: +{net:.2f}% ARBITRAGE SPREAD{RESET}")

    elif event_type == "take_profit":
        pnl = round(random.uniform(8.40, 32.50), 2)
        pct = round(random.uniform(1.20, 3.40), 2)
        print(f"{GRAY}{ts}{RESET} {BRIGHT_GREEN}💰 [TAKE PROFIT]{RESET} {BOLD}{sym} TP1 Hit (50% Scaled Out){RESET} @ Market ➔ {BOLD}{GREEN}+${pnl} USDT (+{pct}%){RESET} {DIM}│ Breakeven Locked{RESET}")

    elif event_type == "risk_guard":
        trail = round(random.uniform(0.35, 0.85), 2)
        print(f"{GRAY}{ts}{RESET} {CYAN}🛡️ [QUANT GUARD]{RESET} {sym:<9} Breakeven Lock Active | Trailing Stop: {GREEN}+{trail}% in Profit{RESET} (Zero Risk)")

    elif event_type == "metrics":
        pnl_tot = round(random.uniform(320.0, 480.0), 2)
        wr = round(random.uniform(76.0, 84.0), 1)
        pf = round(random.uniform(2.10, 2.65), 2)
        print(f"{GRAY}{ts}{RESET} {WHITE}{BOLD}📊 [PORTFOLIO MATRIX]{RESET} Equity: {GREEN}$1,248.50{RESET} │ Realized 24h: {GREEN}+${pnl_tot} USDT{RESET} │ WinRate: {GREEN}{wr}%{RESET} │ ProfitFactor: {GREEN}{pf}{RESET}")

def main():
    print_banner()
    try:
        while True:
            generate_event()
            # Fast, cinematic scrolling speed (5-15 events per second)
            time.sleep(random.uniform(0.08, 0.22))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[DEMO_STOPPED] Terminal logs demo paused.{RESET}\n")

if __name__ == "__main__":
    main()
