from pathlib import Path
import json
from datetime import datetime

BASE = Path("/Users/Owner/weather_ai")
POSITION_FILE = BASE / "position.json"
DASH_FILE = BASE / "web" / "dashboard.json"
WEATHER_FILE = BASE / "latest_weather.txt"
LOG_FILE = BASE / "trade_log.csv"

def extract_detail_price(lines, prefix):
    for line in lines:
        if line.startswith(prefix):
            parts = line.split("終値=")
            if len(parts) < 2:
                return ""
            price_text = parts[1].split(",")[0].strip()
            return price_text
    return ""

def main():
    position = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
    dash = json.loads(DASH_FILE.read_text(encoding="utf-8"))
    weather_text = WEATHER_FILE.read_text(encoding="utf-8")
    lines = [x.strip() for x in weather_text.splitlines() if x.strip()]

    alloc = position.get("allocations", {})

    nikkei_price = extract_detail_price(lines, "日経ETF:")
    semi_price = extract_detail_price(lines, "半導体ETF:")

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        str(dash.get("score", "")),
        str(position.get("total_position", "")),
        str(alloc.get("nikkei_etf", "")),
        str(alloc.get("semi_etf", "")),
        str(dash.get("capital", "")),
        nikkei_price,
        semi_price,
        ""
    ]

    line = ",".join(row)

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    print("logged:", line)

if __name__ == "__main__":
    main()
