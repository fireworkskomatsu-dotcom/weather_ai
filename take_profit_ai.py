import json
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")

POSITION_FILE = BASE / "position.json"
PNL_FILE = BASE / "pnl.json"
OUT_FILE = BASE / "tp.json"

def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except:
        return default

def main():
    pos = read_json(POSITION_FILE, {})
    pnl = read_json(PNL_FILE, {}).get("pnl", 0)

    total = float(pos.get("total_position", 0))

    take = False
    reason = "なし"

    # 利益確定
    if pnl > 5000:
        take = True
        reason = "利益確定ライン"

    # ポジション大きすぎ
    if abs(total) >= 1.0:
        take = True
        reason = "最大ポジ到達"

    out = {
        "take_profit": take,
        "reason": reason
    }

    OUT_FILE.write_text(json.dumps(out, indent=2))
    print(out)

if __name__ == "__main__":
    main()
