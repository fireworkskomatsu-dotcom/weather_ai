import json
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")

POSITION_FILE = BASE / "position.json"
OUT_FILE = BASE / "risk.json"

def main():
    pos = json.loads(POSITION_FILE.read_text())

    total = float(pos.get("total_position", 0))

    stop = False
    reason = "正常"

    # ポジション大きすぎ
    if abs(total) > 0.5:
        stop = True
        reason = "ポジション過大"

    out = {
        "stop": stop,
        "reason": reason
    }

    OUT_FILE.write_text(json.dumps(out, indent=2))
    print(out)

if __name__ == "__main__":
    main()
