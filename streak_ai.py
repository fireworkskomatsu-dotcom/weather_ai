import json
import csv
from pathlib import Path

BASE = Path("/Users/Owner/weather_ai")
LOG_FILE = BASE / "trade_log.csv"
OUT_FILE = BASE / "streak.json"

def main():
    consecutive_losses = 0
    consecutive_wins = 0
    last_results = []

    if LOG_FILE.exists():
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

        last_results = pnl_values[-10:]

        for x in reversed(pnl_values):
            if x < 0:
                consecutive_losses += 1
            else:
                break

        for x in reversed(pnl_values):
            if x > 0:
                consecutive_wins += 1
            else:
                break

    penalty = 1.0
    decision = "NORMAL"
    reason = "通常運転"

    if consecutive_losses >= 3:
        penalty = 0.0
        decision = "STOP"
        reason = "3連敗で強制停止"
    elif consecutive_losses >= 2:
        penalty = 0.5
        decision = "REDUCE"
        reason = "2連敗で半分に縮小"

    out = {
        "consecutive_losses": consecutive_losses,
        "consecutive_wins": consecutive_wins,
        "penalty": penalty,
        "decision": decision,
        "reason": reason,
        "last_results": last_results
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
