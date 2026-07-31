import json
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/Owner/weather_ai")
GAP = BASE / "decision_gap_log.json"
PRICE = BASE / "live_price.json"
OUT = BASE / "signal_outcome.json"

def read(p,d):
    try:
        return json.loads(p.read_text())
    except:
        return d

log = read(GAP,[])
price = read(PRICE,{})

current = price.get("price")
evaluated = []

for x in log:
    sig = x.get("meta_decision")
    entry = x.get("price")

    if sig not in ["LONG","SHORT"] or not entry or not current:
        continue

    pnl_pct = 0
    if sig == "LONG":
        pnl_pct = (current - entry) / entry
    elif sig == "SHORT":
        pnl_pct = (entry - current) / entry

    evaluated.append({
        **x,
        "current_price": current,
        "virtual_pnl_pct": round(pnl_pct, 5),
        "result": "WIN" if pnl_pct > 0 else "LOSS" if pnl_pct < 0 else "FLAT"
    })

out = {
    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "evaluated_signals": len(evaluated),
    "signals": evaluated[-50:]
}

OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
