import json
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")

OPEN_FILE = BASE / "open.json"
POSITION_FILE = BASE / "position.json"
OUT_FILE = BASE / "open_filter.json"

def main():
    open_data = json.loads(OPEN_FILE.read_text())
    pos = json.loads(POSITION_FILE.read_text())

    up = float(open_data.get("open_up_prob", 50))
    down = float(open_data.get("open_down_prob", 50))
    bias = open_data.get("gap_bias", "")

    position = float(pos.get("total_position", 0))

    decision = "GO"
    reason = "通常"

    # ギャップ強すぎ → 危険
    if abs(up - down) > 70:
        decision = "SKIP"
        reason = "ギャップ強すぎ"

    # 下方向ギャップ + ショート → 危険（踏み上げ）
    if bias == "DOWN" and position < 0:
        decision = "SKIP"
        reason = "下ギャップ×ショート危険"

    # 上方向ギャップ + ロング → 危険
    if bias == "UP" and position > 0:
        decision = "SKIP"
        reason = "上ギャップ×ロング危険"

    out = {
        "open_filter": decision,
        "reason": reason
    }

    OUT_FILE.write_text(json.dumps(out, indent=2))
    print(out)

if __name__ == "__main__":
    main()
