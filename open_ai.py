import json
from pathlib import Path

WEATHER_FILE = Path("/Users/Owner/weather_ai/latest_weather.txt")
OUT_FILE = Path("/Users/Owner/weather_ai/open.json")

def extract_value(lines, prefix):
    for line in lines:
        if line.startswith(prefix):
            return line.replace(prefix, "").strip()
    return ""

def to_number(text, default=0):
    try:
        return float(text.replace("%","").strip())
    except:
        return default

def main():
    text = WEATHER_FILE.read_text(encoding="utf-8")
    lines = [x.strip() for x in text.splitlines() if x.strip()]

    score = to_number(extract_value(lines, "スコア："), 0)
    up = to_number(extract_value(lines, "上昇確率："), 50)
    down = to_number(extract_value(lines, "下落確率："), 50)

    bias = "NEUTRAL"

    if score <= -3 and down > 60:
        bias = "DOWN"
    elif score >= 3 and up > 60:
        bias = "UP"

    open_up = max(0, min(100, up + score * 2))
    open_down = max(0, min(100, down - score * 2))

    out = {
        "open_up_prob": round(open_up,1),
        "open_down_prob": round(open_down,1),
        "gap_bias": bias
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
