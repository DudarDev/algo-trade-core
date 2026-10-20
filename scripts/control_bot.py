import sys
import json
import urllib.request

def control(command: str):
    url = "http://127.0.0.1:8000/api/bot_control"
    data = json.dumps({"command": command}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print("Response:", resp.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTPError:", e.code, e.read().decode())

def get_status():
    url = "http://127.0.0.1:8000/api/status"
    try:
        with urllib.request.urlopen(url) as resp:
            print("Status:", resp.read().decode())
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "status":
        get_status()
    else:
        control(cmd)
