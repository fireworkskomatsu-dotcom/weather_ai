import json
import csv
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/Owner/weather_ai")
WEB = BASE / "web"

WEATHER_FILE = BASE / "latest_weather.txt"
POSITION_FILE = BASE / "position.json"
OPEN_FILE = BASE / "open.json"
CONF_FILE = BASE / "confidence.json"
FILTER_FILE = BASE / "filter.json"
LOG_FILE = BASE / "trade_log.csv"
OUT_FILE = WEB / "dashboard.json"

CAPITAL = 500000

def extract_value(lines, prefix):
    for line in lines:
        if line.startswith(prefix):
            return line.replace(prefix, "").strip()
    return ""

def load_pnl_stats():
    if not LOG_FILE.exists():
        return {
            "last_pnl": "",
            "cumulative_pnl": 0.0,
            "win_count": 0,
            "loss_count": 0,
            "trade_count": 0,
            "win_rate": ""
        }

    rows = list(csv.DictReader(LOG_FILE.open(encoding="utf-8")))
    pnl_values = []

    for row in rows:
        pnl = str(row.get("paper_pnl", "")).strip()
        if pnl == "":
            continue
        try:
            pnl_values.append(float(pnl))
        except:
            pass

    if not pnl_values:
        return {
            "last_pnl": "",
            "cumulative_pnl": 0.0,
            "win_count": 0,
            "loss_count": 0,
            "trade_count": 0,
            "win_rate": ""
        }

    win_count = sum(1 for x in pnl_values if x > 0)
    loss_count = sum(1 for x in pnl_values if x < 0)
    trade_count = len(pnl_values)
    cumulative_pnl = round(sum(pnl_values), 2)
    win_rate = round((win_count / trade_count) * 100, 1) if trade_count > 0 else ""

    return {
        "last_pnl": str(pnl_values[-1]),
        "cumulative_pnl": cumulative_pnl,
        "win_count": win_count,
        "loss_count": loss_count,
        "trade_count": trade_count,
        "win_rate": win_rate
    }

def main():
    weather_text = WEATHER_FILE.read_text(encoding="utf-8")
    lines = [x.strip() for x in weather_text.splitlines() if x.strip()]

    position = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
    open_data = json.loads(OPEN_FILE.read_text(encoding="utf-8"))
    conf = json.loads(CONF_FILE.read_text(encoding="utf-8"))
    filt = json.loads(FILTER_FILE.read_text(encoding="utf-8"))
    pnl_stats = load_pnl_stats()

    out = {
        "weather": extract_value(lines, "天気：JP="),
        "score": extract_value(lines, "スコア："),
        "danger": extract_value(lines, "危険度："),
        "market_temp": extract_value(lines, "市場温度："),
        "action": extract_value(lines, "売買判断："),
        "up_prob": extract_value(lines, "上昇確率："),
        "down_prob": extract_value(lines, "下落確率："),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "capital": CAPITAL,
        "pnl_stats": pnl_stats,
        "position": position,
        "open": open_data,
        "confidence": conf,
        "filter": filt
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
