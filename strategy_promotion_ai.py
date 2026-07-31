import json
from pathlib import Path
BASE=Path("/Users/Owner/weather_ai")

def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d

rank=r("strategy_shadow_rank.json",{}).get("ranking",[])

promoted=[]
for s in rank:
    if s["shadow_pnl"]>0:
        promoted.append(s["strategy"])

out={
    "promoted_strategies":promoted
}

(BASE/"strategy_promotion.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
