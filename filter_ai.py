import json
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")

CONF_FILE = BASE / "confidence.json"
OPEN_FILE = BASE / "open.json"
WEATHER_FILE = BASE / "latest_weather.txt"
EVENT_FILE = BASE / "event.json"
NEWS_FILE = BASE / "news.json"
OUT_FILE = BASE / "filter.json"

def extract_value(lines, prefix):
    for line in lines:
        if line.startswith(prefix):
            return line.replace(prefix, "").strip()
    return ""

def to_float(x, default=0.0):
    try:
        return float(str(x).replace("%", "").strip())
    except:
        return default

def safe_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            return default
    return default

def main():
    conf = safe_json(CONF_FILE, {"confidence": 50})
    open_data = safe_json(OPEN_FILE, {"gap_bias": "NEUTRAL"})
    event_data = safe_json(EVENT_FILE, {"event_level": "LOW", "event_reason": "通常日"})
    news_data = safe_json(NEWS_FILE, {"news_level": "LOW", "news_reason": "通常ニュースフロー", "news_score": 0})

    lines = []
    if WEATHER_FILE.exists():
        lines = [x.strip() for x in WEATHER_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]

    score = to_float(extract_value(lines, "スコア："), 0)
    danger = extract_value(lines, "危険度：")
    confidence = to_float(conf.get("confidence", 50), 50)
    bias = open_data.get("gap_bias", "NEUTRAL")
    event_level = event_data.get("event_level", "LOW")
    event_reason = event_data.get("event_reason", "通常日")
    news_level = news_data.get("news_level", "LOW")
    news_reason = news_data.get("news_reason", "通常ニュースフロー")

    decision = "SKIP"
    size = 0.0
    reasons = []

    if confidence >= 80 and abs(score) >= 4:
        decision = "EXECUTE"
        size = 1.0
        reasons.append("高信頼・高スコア")
    elif confidence >= 65 and abs(score) >= 2:
        decision = "LIGHT"
        size = 0.5
        reasons.append("中信頼・中スコア")
    else:
        decision = "SKIP"
        size = 0.0
        reasons.append("信頼度またはスコア不足")

    if danger == "HIGH" and size > 0:
        size *= 0.5
        reasons.append("危険度HIGHで半減")

    if (score > 0 and bias != "UP") or (score < 0 and bias != "DOWN"):
        if size > 0:
            size *= 0.5
            reasons.append("寄り付きバイアス不一致で半減")

    if event_level == "HIGH":
        size *= 0.5
        reasons.append(f"イベントHIGHで半減: {event_reason}")
    elif event_level == "MID":
        size *= 0.75
        reasons.append(f"イベントMIDで縮小: {event_reason}")

    if news_level == "HIGH":
        size *= 0.5
        reasons.append(f"ニュースHIGHで半減: {news_reason}")
    elif news_level == "MID":
        size *= 0.75
        reasons.append(f"ニュースMIDで縮小: {news_reason}")

    size = round(size, 2)

    if size >= 0.75:
        decision = "EXECUTE"
    elif size >= 0.25:
        decision = "LIGHT"
    else:
        decision = "SKIP"
        size = 0.0
        reasons.append("最終サイズが小さすぎるため見送り")

    out = {
        "decision": decision,
        "size": size,
        "confidence": confidence,
        "event_level": event_level,
        "event_reason": event_reason,
        "news_level": news_level,
        "news_reason": news_reason,
        "reason": " / ".join(reasons)
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
