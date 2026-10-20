import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import urllib.request
import json

base_url = "http://127.0.0.1:8000"
endpoints = [
    "/api/status",
    "/api/stats",
    "/api/active_positions",
    "/api/market_scanner",
    "/api/engine_logs",
    "/api/config",
    "/api/recent_trades"
]

for ep in endpoints:
    url = base_url + ep
    try:
        with urllib.request.urlopen(url) as resp:
            data = resp.read().decode()
            parsed = json.loads(data)
            count = len(parsed) if isinstance(parsed, list) else len(parsed.keys())
            print(f"✅ {ep:<25} -> HTTP {resp.status} (Items/Keys: {count})")
    except Exception as e:
        print(f"❌ {ep:<25} -> ERROR: {e}")
