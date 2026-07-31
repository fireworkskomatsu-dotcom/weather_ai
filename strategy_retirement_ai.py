import json
from pathlib import Path
BASE=Path("/Users/Owner/weather_ai")

def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d

rank=r("strategy_shadow_rank.json",{}).get("ranking",[])

retired=[]
for s in rank:
    if s["shadow_pnl"]<-5:
        retired.append(s["strategy"])

out={
    "retired_strategies":retired
}

(BASE/"strategy_retirement.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
