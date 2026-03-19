import json
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")

POSITION_FILE = BASE / "position.json"
CONF_FILE = BASE / "confidence.json"
OPEN_FILE = BASE / "open.json"
WEATHER_FILE = BASE / "latest_weather.txt"
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

def main():
    position = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
    conf = json.loads(CONF_FILE.read_text(encoding="utf-8"))
    open_data = json.loads(OPEN_FILE.read_text(encoding="utf-8"))

    lines = [x.strip() for x in WEATHER_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]

    score = to_float(extract_value(lines, "スコア："), 0)
    danger = extract_value(lines, "危険度：")
    confidence = to_float(conf.get("confidence", 50), 50)
    bias = open_data.get("gap_bias", "NEUTRAL")

    decision = "SKIP"
    size = 0.0
    reason = []

    if confidence >= 80 and abs(score) >= 4:
        decision = "EXECUTE"
        size = 1.0
        reason.append("高信頼・高スコア")
    elif confidence >= 65 and abs(score) >= 2:
        decision = "LIGHT"
        size = 0.5
        reason.append("中信頼・中スコア")
    else:
        decision = "SKIP"
        size = 0.0
        reason.append("信頼度またはスコア不足")

    if danger == "HIGH" and size > 0:
        size *= 0.5
        reason.append("危険度HIGHで半減")

    if (score > 0 and bias != "UP") or (score < 0 and bias != "DOWN"):
        if size > 0:
            size *= 0.5
            reason.append("寄り付きバイアス不一致で半減")

    size = round(size, 2)

    # 最終的にサイズがかなり小さければ見送り
    if size < 0.25:
        decision = "SKIP"
        size = 0.0
        reason.append("最終サイズが小さすぎるため見送り")

    out = {
        "decision": decision,
        "size": size,
        "confidence": confidence,
        "reason": " / ".join(reason)
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
