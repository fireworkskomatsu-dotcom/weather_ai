import json
from pathlib import Path

WEATHER_FILE = Path("/Users/Owner/weather_ai/latest_weather.txt")
OUT_FILE = Path("/Users/Owner/weather_ai/position.json")

def extract_value(lines, prefix):
    for line in lines:
        if line.startswith(prefix):
            return line.replace(prefix, "").strip()
    return ""

def to_number(text, default=0.0):
    try:
        return float(text.replace("%", "").strip())
    except:
        return default

def main():
    text = WEATHER_FILE.read_text(encoding="utf-8")
    lines = [x.strip() for x in text.splitlines() if x.strip()]

    weather = extract_value(lines, "天気：JP=")
    score = to_number(extract_value(lines, "スコア："), 0)
    danger = extract_value(lines, "危険度：")
    up = to_number(extract_value(lines, "上昇確率："), 50)
    down = to_number(extract_value(lines, "下落確率："), 50)

    base = 0.0

    if weather.startswith("青"):
        base = 0.6
    elif weather.startswith("赤"):
        base = -0.6
    else:
        if score >= 2:
            base = 0.25
        elif score <= -2:
            base = -0.25
        else:
            base = 0.0

    if danger == "HIGH":
        base *= 0.5

    edge = (up - down) / 100.0
    position = round(base + edge * 0.5, 2)

    if position > 1:
        position = 1.0
    if position < -1:
        position = -1.0

    nikkei = round(position * 0.7, 2)
    semi = round(position * 0.3 if abs(position) >= 0.4 else 0.0, 2)
    cash = round(1.0 - abs(nikkei) - abs(semi), 2)
    if cash < 0:
        cash = 0.0

    out = {
        "weather": weather,
        "score": score,
        "danger": danger,
        "up_prob": up,
        "down_prob": down,
        "total_position": position,
        "allocations": {
            "nikkei_etf": nikkei,
            "semi_etf": semi,
            "cash": cash
        }
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
