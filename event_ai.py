import json
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")
WEATHER_FILE = BASE / "latest_weather.txt"
OUT_FILE = BASE / "event.json"

KEYWORDS_HIGH = [
    "FOMC", "CPI", "雇用統計", "日銀", "BOJ", "NVIDIA", "NVDA"
]

KEYWORDS_MID = [
    "PCE", "ISM", "GDP", "SQ", "MSQ"
]

def main():
    text = ""
    if WEATHER_FILE.exists():
        text = WEATHER_FILE.read_text(encoding="utf-8")

    level = "LOW"
    reason = "通常日"

    for k in KEYWORDS_HIGH:
        if k in text:
            level = "HIGH"
            reason = f"重要イベント検知: {k}"
            break

    if level == "LOW":
        for k in KEYWORDS_MID:
            if k in text:
                level = "MID"
                reason = f"中規模イベント検知: {k}"
                break

    out = {
        "event_level": level,
        "event_reason": reason
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
