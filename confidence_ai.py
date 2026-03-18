import json
from pathlib import Path

WEATHER_FILE = Path("/Users/Owner/weather_ai/latest_weather.txt")
OPEN_FILE = Path("/Users/Owner/weather_ai/open.json")
OUT_FILE = Path("/Users/Owner/weather_ai/confidence.json")

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
    danger = extract_value(lines, "危険度：")
    up = to_number(extract_value(lines, "上昇確率："), 50)
    down = to_number(extract_value(lines, "下落確率："), 50)

    open_data = json.loads(OPEN_FILE.read_text(encoding="utf-8"))
    bias = open_data.get("gap_bias", "NEUTRAL")

    confidence = 50

    # スコア強度
    confidence += abs(score) * 5

    # 確率差
    confidence += abs(up - down) * 0.3

    # 危険度
    if danger == "HIGH":
        confidence -= 10

    # 寄り付き一致
    if score < 0 and bias == "DOWN":
        confidence += 10
    elif score > 0 and bias == "UP":
        confidence += 10
    else:
        confidence -= 10

    # 範囲制限
    if confidence > 100:
        confidence = 100
    if confidence < 0:
        confidence = 0

    level = "LOW"
    if confidence > 70:
        level = "HIGH"
    elif confidence > 50:
        level = "MID"

    out = {
        "confidence": round(confidence,1),
        "level": level
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
