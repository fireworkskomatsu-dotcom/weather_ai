import json
import re
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/Owner/weather_ai")

WEATHER_TEXT_FILE = BASE / "latest_weather.txt"
FILTER_FILE = BASE / "filter.json"
POSITION_FILE = BASE / "position.json"
CONF_FILE = BASE / "confidence.json"
STATE_FILE = BASE / "entry_state.json"
OUT_FILE = BASE / "entry.json"

def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except:
        return default

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def extract_nikkei_rsi(text: str) -> float:
    m = re.search(r"日経ETF:.*?RSI=([0-9.]+)", text, re.DOTALL)
    if not m:
        return 50.0
    try:
        return float(m.group(1))
    except:
        return 50.0

def main():
    filt = read_json(FILTER_FILE, {})
    pos = read_json(POSITION_FILE, {})
    conf = read_json(CONF_FILE, {})
    state = read_json(STATE_FILE, {"last_size": 0})

    try:
        weather_text = WEATHER_TEXT_FILE.read_text(encoding="utf-8")
    except:
        weather_text = ""

    decision = filt.get("decision", "SKIP")
    direction = filt.get("allowed_direction", "BOTH")
    confidence = float(conf.get("confidence", 0))
    nikkei_rsi = extract_nikkei_rsi(weather_text)
    current_pos = float(pos.get("total_position", 0))
    score = float(pos.get("score", 0))

    entry = False
    side = None
    add_size = 0.0
    reason = "条件未達"
    target = current_pos

    if decision == "SKIP" and direction == "BOTH":
        out = {
            "entry": False,
            "side": None,
            "size": 0.0,
            "nikkei_rsi": nikkei_rsi,
            "current_pos": current_pos,
            "reason": "完全停止"
        }
        write_json(OUT_FILE, out)
        print(out)
        return

    if direction == "LONG_ONLY" and confidence >= 80:
        if score >= -3:
            if nikkei_rsi <= 40:
                target = 0.3
            if nikkei_rsi <= 38:
                target = 0.6
            if nikkei_rsi <= 35:
                target = 1.0

            if target > current_pos:
                add_size = round(target - current_pos, 2)
                add_size = min(add_size, 1.0)
                side = "LONG"
                reason = f"積み増し {current_pos} → {target}"
            else:
                reason = "すでにポジションあり"
        else:
            reason = "トレンド弱い"

    elif direction == "SHORT_ONLY" and confidence >= 80:
        if score <= 3:
            if nikkei_rsi >= 60:
                target = -0.3
            if nikkei_rsi >= 65:
                target = -0.6
            if nikkei_rsi >= 70:
                target = -1.0

            if target < current_pos:
                add_size = round(abs(target - current_pos), 2)
                add_size = min(add_size, 1.0)
                side = "SHORT"
                reason = f"積み増し {current_pos} → {target}"
            else:
                reason = "すでにポジションあり"
        else:
            reason = "トレンド強い"

    last_size = float(state.get("last_size", 0))

    if add_size > 0 and add_size != last_size:
        entry = True
        state["last_size"] = add_size
        state["last_time"] = datetime.now().isoformat()
        write_json(STATE_FILE, state)
    elif add_size > 0:
        reason = "同一シグナル抑制"

    out = {
        "entry": entry,
        "side": side,
        "size": add_size,
        "nikkei_rsi": nikkei_rsi,
        "current_pos": current_pos,
        "reason": reason
    }

    write_json(OUT_FILE, out)
    print(out)

if __name__ == "__main__":
    main()
