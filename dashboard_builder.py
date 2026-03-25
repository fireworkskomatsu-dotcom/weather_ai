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
EVENT_FILE = BASE / "event.json"
NEWS_FILE = BASE / "news.json"
STREAK_FILE = BASE / "streak.json"
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

def safe_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            return default
    return default

def main():
    weather_text = WEATHER_FILE.read_text(encoding="utf-8") if WEATHER_FILE.exists() else ""
    lines = [x.strip() for x in weather_text.splitlines() if x.strip()]

    position = safe_json(POSITION_FILE, {})
    open_data = safe_json(OPEN_FILE, {})
    conf = safe_json(CONF_FILE, {})
    filt = safe_json(FILTER_FILE, {})
    event_data = safe_json(EVENT_FILE, {})
    news_data = safe_json(NEWS_FILE, {})
    streak_data = safe_json(STREAK_FILE, {})
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
        "filter": filt,
        "event": event_data,
        "news": news_data,
        "streak": streak_data
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
