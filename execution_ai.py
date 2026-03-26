import json
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")

ENTRY_FILE = BASE / "entry.json"
TP_FILE = BASE / "tp.json"
SL_FILE = BASE / "sl.json"
OUT_FILE = BASE / "execution.json"

def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except:
        return default

def main():
    entry = read_json(ENTRY_FILE, {})
    tp = read_json(TP_FILE, {})
    sl = read_json(SL_FILE, {})

    action = "HOLD"
    side = None
    size = 0
    reason = "待機"

    if sl.get("stop_loss"):
        action = "EXIT"
        reason = "損切り"

    elif tp.get("take_profit"):
        action = "EXIT"
        reason = "利確"

    elif entry.get("entry"):
        action = "ENTER"
        side = entry.get("side")
        size = entry.get("size", 0)
        reason = entry.get("reason", "エントリー")

    out = {
        "action": action,
        "side": side,
        "size": size,
        "reason": reason
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(out)

if __name__ == "__main__":
    main()
