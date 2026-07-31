import json
from pathlib import Path
BASE=Path("/Users/Owner/weather_ai")

def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d

runs=r("strategy_shadow_runner.json",{}).get("shadow_runs",[])

results=[]
for x in runs:
    results.append({
        "strategy":x["strategy"],
        "shadow_pnl":0,
        "status":"LEARNING"
    })

out={
    "strategy_results":results
}

(BASE/"strategy_shadow_pnl.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
