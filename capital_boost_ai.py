import csv
from pathlib import Path
import json

LOG_FILE = Path("/Users/Owner/weather_ai/trade_log.csv")
OUT_FILE = Path("/Users/Owner/weather_ai/capital.json")

def main():
    if not LOG_FILE.exists():
        out = {"boost": 1.0, "status": "NO_DATA"}
        OUT_FILE.write_text(json.dumps(out, indent=2))
        print(out)
        return

    rows = list(csv.DictReader(LOG_FILE.open(encoding="utf-8")))
    
    pnl_list = []
    for r in rows:
        try:
            pnl = float(r.get("paper_pnl", ""))
            pnl_list.append(pnl)
        except:
            pass

    if not pnl_list:
        out = {"boost": 1.0, "status": "NO_PNL"}
        OUT_FILE.write_text(json.dumps(out, indent=2))
        print(out)
        return

    total = sum(pnl_list)

    if total > 0:
        boost = 1.2
        status = "WINNING"
    elif total < 0:
        boost = 0.7
        status = "LOSING"
    else:
        boost = 1.0
        status = "FLAT"

    out = {
        "boost": boost,
        "status": status,
        "total_pnl": round(total,2)
    }

    OUT_FILE.write_text(json.dumps(out, indent=2))
    print(out)

if __name__ == "__main__":
    main()
