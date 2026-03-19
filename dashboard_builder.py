import json
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/Owner/weather_ai")
WEB = BASE / "web"

WEATHER_FILE = BASE / "latest_weather.txt"
POSITION_FILE = BASE / "position.json"
OPEN_FILE = BASE / "open.json"
CONF_FILE = BASE / "confidence.json"
OUT_FILE = WEB / "dashboard.json"

CAPITAL = 500000

def extract_value(lines, prefix):
    for line in lines:
        if line.startswith(prefix):
            return line.replace(prefix, "").strip()
    return ""

def main():
    weather_text = WEATHER_FILE.read_text(encoding="utf-8")
    lines = [x.strip() for x in weather_text.splitlines() if x.strip()]

    position = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
    open_data = json.loads(OPEN_FILE.read_text(encoding="utf-8"))
    conf = json.loads(CONF_FILE.read_text(encoding="utf-8"))

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
        "position": position,
        "open": open_data,
        "confidence": conf
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
