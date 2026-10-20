import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import urllib.request
import json

base_url = "http://127.0.0.1:8000"

# Test POST /api/config
req = urllib.request.Request(
    base_url + "/api/config",
    data=json.dumps({
        "confidence_threshold": 0.30,
        "risk_reward_ratio": 1.5,
        "max_positions": 3,
        "trade_fraction": 0.04,
        "min_adx_trend": 25.0
    }).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req) as resp:
    print("POST /api/config:", resp.read().decode())

# Test GET /api/export_trades_csv
with urllib.request.urlopen(base_url + "/api/export_trades_csv") as resp:
    print("GET /api/export_trades_csv lines:", len(resp.read().decode().splitlines()))
