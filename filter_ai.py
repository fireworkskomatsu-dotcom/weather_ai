import json
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/Owner/weather_ai")

CONF_FILE = BASE / "confidence.json"
STREAK_FILE = BASE / "streak.json"
OPEN_FILTER_FILE = BASE / "open_filter.json"
CAPITAL_FILE = BASE / "capital.json"
POSITION_FILE = BASE / "position.json"
OUT_FILE = BASE / "filter.json"

def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except:
        return default

def main():
    conf = read_json(CONF_FILE, {"confidence": 0})
    streak = read_json(STREAK_FILE, {"consecutive_losses": 0})
    open_filter = read_json(OPEN_FILTER_FILE, {"open_filter": "GO", "reason": "通常"})
    capital = read_json(CAPITAL_FILE, {"boost": 1.0})
    pos = read_json(POSITION_FILE, {"total_position": 0})

    confidence = float(conf.get("confidence", 0))
    losses = int(streak.get("consecutive_losses", 0))
    boost = float(capital.get("boost", 1.0))
    total = float(pos.get("total_position", 0))
    current_time = datetime.now().strftime("%H:%M")
    reason = str(open_filter.get("reason", ""))

    # 方向制御
    short_block = "ショート危険" in reason
    long_block = "ロング危険" in reason

    allowed_direction = "BOTH"
    if short_block:
        allowed_direction = "LONG_ONLY"
    if long_block:
        allowed_direction = "SHORT_ONLY"

    # 寄り危険
    if open_filter.get("open_filter") == "SKIP" and current_time < "09:15":
        out = {
            "decision": "SKIP",
            "size": 0,
            "confidence": confidence,
            "allowed_direction": allowed_direction,
            "reason": "寄り危険（09:15まで待機）"
        }
        OUT_FILE.write_text(json.dumps(out, indent=2))
        print(out)
        return

    # 方向禁止
    if short_block and total < 0:
        out = {
            "decision": "SKIP",
            "size": 0,
            "confidence": confidence,
            "allowed_direction": allowed_direction,
            "reason": "ショート禁止"
        }
        OUT_FILE.write_text(json.dumps(out, indent=2))
        print(out)
        return

    if long_block and total > 0:
        out = {
            "decision": "SKIP",
            "size": 0,
            "confidence": confidence,
            "allowed_direction": allowed_direction,
            "reason": "ロング禁止"
        }
        OUT_FILE.write_text(json.dumps(out, indent=2))
        print(out)
        return

    # 連敗停止
    if losses >= 3:
        out = {
            "decision": "SKIP",
            "size": 0,
            "confidence": confidence,
            "allowed_direction": allowed_direction,
            "reason": "連敗停止"
        }
        OUT_FILE.write_text(json.dumps(out, indent=2))
        print(out)
        return

    # 弱い
    if confidence < 60:
        out = {
            "decision": "SKIP",
            "size": 0,
            "confidence": confidence,
            "allowed_direction": allowed_direction,
            "reason": "信頼度低い"
        }
        OUT_FILE.write_text(json.dumps(out, indent=2))
        print(out)
        return

    # 強い
    if confidence > 90:
        size = round(1.0 * boost, 2)
        out = {
            "decision": "BOOST",
            "size": size,
            "confidence": confidence,
            "allowed_direction": allowed_direction,
            "reason": f"高信頼 + 資金({boost})"
        }
        OUT_FILE.write_text(json.dumps(out, indent=2))
        print(out)
        return

    # 通常
    size = round(0.5 * boost, 2)
    out = {
        "decision": "LIGHT",
        "size": size,
        "confidence": confidence,
        "allowed_direction": allowed_direction,
        "reason": f"通常 + 資金({boost})"
    }

    OUT_FILE.write_text(json.dumps(out, indent=2))
    print(out)

if __name__ == "__main__":
    main()
