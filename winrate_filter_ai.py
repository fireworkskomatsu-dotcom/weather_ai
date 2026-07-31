import json
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/Owner/weather_ai")

FILTER = BASE / "filter.json"
PERF = BASE / "performance_dashboard.json"
LOSS = BASE / "loss_analysis.json"
OUT = BASE / "winrate_filter.json"

def read(p,d):
    try:
        return json.loads(p.read_text())
    except:
        return d

def main():
    f = read(FILTER,{})
    perf = read(PERF,{})
    loss = read(LOSS,{})

    decision = f.get("decision","SKIP")
    direction = f.get("allowed_direction","BOTH")
    size = f.get("size",0)

    blocked = False
    reason = "OK"

    wr = perf.get("win_rate",0)
    closed = perf.get("closed",0)

    if closed < 30:

        # 学習期間は小ロットのみ許可
        if size > 0.05:
            size = 0.05

        blocked = False
        reason = "学習モード / 小ロット許可"

    if direction == "LONG_ONLY" and perf.get("long_win_rate",0) < 50 and closed >= 10:
        blocked = True
        reason = "LONG勝率不足"

    if direction == "SHORT_ONLY" and perf.get("short_win_rate",0) < 50 and closed >= 10:
        blocked = True
        reason = "SHORT勝率不足"

    for w in loss.get("warnings",[]):
        if direction.startswith(w.get("side","")):
            blocked = True
            reason = f"{w.get('side')}負け率高め"

    out = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "original_decision": decision,
        "allowed_direction": direction,
        "original_size": size,
        "blocked": blocked,
        "final_decision": "SKIP" if blocked else decision,
        "final_size": 0 if blocked else size,
        "reason": reason,
        "closed": closed,
        "win_rate": wr
    }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(out)

if __name__ == "__main__":
    main()
