import json
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")

PNL_FILE = BASE / "pnl.json"
OUT_FILE = BASE / "sl.json"

def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except:
        return default

def main():
    pnl = read_json(PNL_FILE, {}).get("pnl", 0)

    stop = False
    reason = "なし"

    # 損切り
    if pnl < -3000:
        stop = True
        reason = "損切りライン"

    out = {
        "stop_loss": stop,
        "reason": reason
    }

    OUT_FILE.write_text(json.dumps(out, indent=2))
    print(out)

if __name__ == "__main__":
    main()
